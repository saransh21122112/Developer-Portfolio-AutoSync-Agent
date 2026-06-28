import argparse
import sys
import time
import logging
import difflib
import urllib.parse
import webbrowser
import requests
import threading
from datetime import datetime, timezone, timedelta
from pathlib import Path
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
import uvicorn

from src.config import config
from src.github_client import GitHubClient, get_webhook_router
from src.llm_router import get_llm_connector
from src.portfolio_manager import PortfolioManager
from src.dispatcher import EventDispatcher, ProjectPublished, LinkedInConnector, DiscordWebhookConnector
from src.mailer import Mailer

# Setup Logging
log_formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
root_logger = logging.getLogger()
root_logger.setLevel(logging.INFO)

# Console Handler
console_handler = logging.StreamHandler(sys.stdout)
console_handler.setFormatter(log_formatter)
root_logger.addHandler(console_handler)

# File Handler
file_handler = logging.FileHandler("portfolio_sync.log", encoding="utf-8")
file_handler.setFormatter(log_formatter)
root_logger.addHandler(file_handler)


class VercelLogHandler(logging.Handler):
    """Logging handler that forwards log records to the Next.js Vercel dashboard API."""
    def __init__(self, vercel_url: str):
        super().__init__()
        self.vercel_url = vercel_url.rstrip("/")

    def emit(self, record):
        try:
            payload = {
                "timestamp": datetime.fromtimestamp(record.created, timezone.utc).isoformat(),
                "level": record.levelname,
                "name": record.name,
                "message": record.getMessage()
            }
            # Fire-and-forget request to Vercel API with 2s timeout
            requests.post(f"{self.vercel_url}/api/logs", json=payload, timeout=2)
        except Exception:
            pass


logger = logging.getLogger("PortfolioSyncAgent")

LAST_CHECKED_FILE = Path("last_checked.txt")


def get_last_checked_time() -> datetime:
    """Reads the last checked timestamp from a local file, defaulting to 24h ago if missing."""
    if LAST_CHECKED_FILE.exists():
        try:
            with open(LAST_CHECKED_FILE, "r") as f:
                content = f.read().strip()
                return datetime.fromisoformat(content).replace(tzinfo=timezone.utc)
        except Exception as e:
            logger.warning(f"Could not parse last_checked.txt: {e}. Defaulting to past 24 hours.")
    
    return datetime.now(timezone.utc) - timedelta(days=1)


def save_last_checked_time(dt: datetime):
    """Saves the last checked timestamp to a local file in ISO format."""
    try:
        with open(LAST_CHECKED_FILE, "w") as f:
            f.write(dt.isoformat())
    except Exception as e:
        logger.error(f"Failed to save last checked time to file: {e}")


def dispatch_success_notifications(repo_metadata: dict, dispatcher: EventDispatcher):
    """Fires post-publish plugin hooks upon successful portfolio modification."""
    created_at = repo_metadata.get("created_at")
    if isinstance(created_at, datetime):
        date_str = created_at.strftime("%Y-%m-%d")
    else:
        date_str = datetime.now().strftime("%Y-%m-%d")

    event = ProjectPublished(
        name=repo_metadata.get("name"),
        description=repo_metadata.get("description", ""),
        url=repo_metadata.get("url"),
        languages=repo_metadata.get("languages", []),
        date=date_str
    )
    dispatcher.dispatch(event)


def ask_cli_approval(diff: str, project_name: str) -> bool:
    """Prompts the CLI user to approve or reject the proposed changes."""
    print(f"\n{'='*25} PROPOSED DIFF FOR '{project_name}' {'='*25}")
    print(diff)
    print("=" * (52 + len(project_name)))
    
    # Try opening the browser for visual inspection even in CLI mode
    try:
        temp_html_path = Path("pending_updates") / f"{project_name}_review.html"
        temp_html_path.parent.mkdir(exist_ok=True)
        
        # Colorize the diff lines for visual help
        diff_lines_html = ""
        for line in diff.splitlines():
            if line.startswith("+") and not line.startswith("+++"):
                diff_lines_html += f'<div style="color: #28a745; background-color: #e8f5e9; font-family: monospace;">{line}</div>'
            elif line.startswith("-") and not line.startswith("---"):
                diff_lines_html += f'<div style="color: #dc3545; background-color: #ffebee; font-family: monospace;">{line}</div>'
            else:
                diff_lines_html += f'<div style="font-family: monospace; color: #333;">{line}</div>'
                
        html_view = f"""
        <html>
        <body style="font-family: Arial, sans-serif; padding: 20px; background-color: #fdfdfd;">
            <h2>Review Proposed Changes for {project_name}</h2>
            <div style="border: 1px solid #ccc; padding: 20px; background-color: white; border-radius: 6px; overflow-x: auto; white-space: pre;">
                {diff_lines_html}
            </div>
            <p><strong>Action Required:</strong> Switch back to your terminal window to Approve [y] or Reject [N] this sync.</p>
        </body>
        </html>
        """
        with open(temp_html_path, "w") as f:
            f.write(html_view)
            
        webbrowser.open(temp_html_path.resolve().as_uri())
        logger.info(f"Opened visual diff file in browser for review: {temp_html_path}")
    except Exception as e:
        logger.warning(f"Could not open local browser for CLI review diff: {e}")

    try:
        sys.stdout.write(f"Do you want to commit and push these changes to branch '{config.portfolio_branch}'? [y/N]: ")
        sys.stdout.flush()
        choice = sys.stdin.readline().strip().lower()
        return choice in ("y", "yes")
    except Exception as e:
        logger.error(f"Failed to read interactive input from CLI console: {e}")
        return False


def handle_new_repository(repo_metadata: dict, portfolio_manager: PortfolioManager, dispatcher: EventDispatcher, pending_cache: dict = None):
    """Callback function executed when a new repository is detected (via polling or webhook)."""
    repo_name = repo_metadata.get("name")
    logger.info(f"Orchestrating flow for new repository '{repo_name}'")
    
    try:
        # 1. Ensure local repository checkout
        repo = portfolio_manager.ensure_repository_local()
        portfolio_manager.sync_local_repo(repo)

        # 2. Check for duplication
        if portfolio_manager.is_project_already_added(repo_metadata):
            logger.info(f"Project '{repo_name}' already exists in portfolio. Skipping sync.")
            return

        # 3. Read target portfolio structure
        original_content = portfolio_manager.read_target_file()

        # 4. Generate updated content via LLM
        updated_content = portfolio_manager.generate_updated_content(original_content, repo_metadata)

        # 5. Validate output structure
        if not portfolio_manager.validate_content(updated_content):
            logger.error(f"Generated portfolio content for '{repo_name}' failed validation. Aborting.")
            return

        # 6. Apply human approval logic or direct push
        if config.approval_human_check:
            # Generate diff
            original_lines = original_content.splitlines(keepends=True)
            updated_lines = updated_content.splitlines(keepends=True)
            diff = "".join(difflib.unified_diff(original_lines, updated_lines, fromfile="original", tofile="updated"))

            # Determine date formatting for emails/logs
            created_at = repo_metadata.get("created_at")
            date_str = created_at.strftime("%Y-%m-%d") if isinstance(created_at, datetime) else datetime.now().strftime("%Y-%m-%d")

            # Route 1: Vercel Dashboard Approval Flow (takes priority if configured)
            if config.vercel_dashboard_url:
                serializable_metadata = {}
                for k, v in repo_metadata.items():
                    if isinstance(v, datetime):
                        serializable_metadata[k] = v.isoformat()
                    else:
                        serializable_metadata[k] = v

                payload = {
                    "project": repo_name,
                    "metadata": serializable_metadata,
                    "content": updated_content,
                    "diff": diff
                }
                try:
                    logger.info(f"Pushing pending approval to Vercel Dashboard: {config.vercel_dashboard_url}")
                    requests.post(f"{config.vercel_dashboard_url}/api/approvals", json=payload, timeout=5)
                except Exception as ev:
                    logger.error(f"Failed to push pending approval to Vercel: {ev}")

                poll_url = f"{config.vercel_dashboard_url}/api/approvals/{urllib.parse.quote(repo_name)}/status"
                logger.info(f"Awaiting manual confirmation on Vercel Dashboard...")
                
                decision = "pending"
                while decision == "pending":
                    try:
                        r = requests.get(poll_url, timeout=5)
                        if r.status_code == 200:
                            decision = r.json().get("status", "pending")
                    except Exception as ep:
                        logger.warning(f"Error checking Vercel approval status: {ep}")
                    time.sleep(3)

                if decision == "approved":
                    logger.info(f"Vercel Dashboard approved change for '{repo_name}'. Proceeding with sync.")
                    portfolio_manager.write_target_file(updated_content)
                    success = portfolio_manager.commit_and_push(repo, repo_name)
                    if success:
                        dispatch_success_notifications(repo_metadata, dispatcher)
                        try:
                            requests.post(poll_url, json={"status": "completed"}, timeout=5)
                        except Exception:
                            pass
                    else:
                        try:
                            requests.post(poll_url, json={"status": "failed"}, timeout=5)
                        except Exception:
                            pass
                else:
                    logger.info(f"Vercel Dashboard rejected/discarded change for '{repo_name}'. Skipping sync.")

            # Route 2: Webhook Server Mode with local memory cache
            elif pending_cache is not None:
                # Store update details in the memory cache
                pending_cache[repo_name] = {
                    "pm": portfolio_manager,
                    "repo": repo,
                    "metadata": repo_metadata,
                    "content": updated_content
                }
                logger.info(f"Update for '{repo_name}' stored in pending approvals cache.")

                # Open browser page automatically for local Macbook verification
                review_url = f"{config.email_base_url.rstrip('/')}/review?project={urllib.parse.quote(repo_name)}"
                logger.info(f"Opening browser review page: {review_url}")
                try:
                    webbrowser.open(review_url)
                except Exception as eb:
                    logger.warning(f"Could not open browser automatically: {eb}")

                # Fire Email approval
                if config.email_enabled:
                    mailer = Mailer(config)
                    mailer.send_approval_request(
                        project_name=repo_name,
                        description=repo_metadata.get("description", ""),
                        repo_url=repo_metadata.get("url", ""),
                        languages=repo_metadata.get("languages", []),
                        date_str=date_str,
                        diff=diff
                    )
                else:
                    logger.warning(f"Human check is active, but SMTP email notifications are disabled. "
                                   f"Approve this update via the server endpoint: {review_url}")
            
            else:
                # CLI/Interactive poll mode
                is_interactive = sys.stdin.isatty()
                if is_interactive:
                    if ask_cli_approval(diff, repo_name):
                        portfolio_manager.write_target_file(updated_content)
                        success = portfolio_manager.commit_and_push(repo, repo_name)
                        if success:
                            dispatch_success_notifications(repo_metadata, dispatcher)
                    else:
                        logger.info(f"Changes for '{repo_name}' discarded by user.")
                else:
                    # Non-interactive CLI (e.g. cron run)
                    logger.warning(f"Non-interactive terminal detected. Cannot prompt for approval of '{repo_name}'.")
                    
                    # Fire Email approval if configured
                    if config.email_enabled:
                        mailer = Mailer(config)
                        mailer.send_approval_request(
                            project_name=repo_name,
                            description=repo_metadata.get("description", ""),
                            repo_url=repo_metadata.get("url", ""),
                            languages=repo_metadata.get("languages", []),
                            date_str=date_str,
                            diff=diff
                        )
                        logger.info(f"Approval request email dispatched for non-interactive task.")
                    else:
                        # Write diff to a temp file in scratch or current directory for audit
                        temp_diff_path = Path("pending_updates") / f"{repo_name}_diff.txt"
                        temp_diff_path.parent.mkdir(exist_ok=True)
                        with open(temp_diff_path, "w") as f:
                            f.write(diff)
                        logger.warning(f"SMTP disabled and non-interactive environment. "
                                       f"Wrote pending changes diff to {temp_diff_path}")
                        
                        # Open browser locally to review
                        try:
                            temp_html_path = Path("pending_updates") / f"{repo_name}_review.html"
                            # Colorize the diff lines for visual help
                            diff_lines_html = ""
                            for line in diff.splitlines():
                                if line.startswith("+") and not line.startswith("+++"):
                                    diff_lines_html += f'<div style="color: #28a745; background-color: #e8f5e9; font-family: monospace;">{line}</div>'
                                elif line.startswith("-") and not line.startswith("---"):
                                    diff_lines_html += f'<div style="color: #dc3545; background-color: #ffebee; font-family: monospace;">{line}</div>'
                                else:
                                    diff_lines_html += f'<div style="font-family: monospace; color: #333;">{line}</div>'
                                    
                            html_view = f"""
                            <html>
                            <body style="font-family: Arial, sans-serif; padding: 20px; background-color: #fdfdfd;">
                                <h2>Review Pending Update: {repo_name}</h2>
                                <div style="border: 1px solid #ccc; padding: 20px; background-color: white; border-radius: 6px; overflow-x: auto; white-space: pre;">
                                    {diff_lines_html}
                                </div>
                            </body>
                            </html>
                            """
                            with open(temp_html_path, "w") as f:
                                f.write(html_view)
                            webbrowser.open(temp_html_path.resolve().as_uri())
                        except Exception as e:
                            logger.warning(f"Could not open browser diff review: {e}")
        else:
            # Automatic sync (no human check)
            portfolio_manager.write_target_file(updated_content)
            success = portfolio_manager.commit_and_push(repo, repo_name)
            if success:
                dispatch_success_notifications(repo_metadata, dispatcher)
            
    except Exception as e:
        logger.error(f"Failed to process new repository '{repo_name}': {e}", exc_info=True)


def run_poll(github_client: GitHubClient, portfolio_manager: PortfolioManager, dispatcher: EventDispatcher):
    """Runs a single GitHub repository polling check."""
    logger.info("Executing one-off poll execution.")
    since_time = get_last_checked_time()
    current_check_time = datetime.now(timezone.utc)
    
    new_repos = github_client.poll_new_repositories(since_time)
    
    if new_repos:
        logger.info(f"Found {len(new_repos)} new repositories since {since_time}.")
        for repo in reversed(new_repos):
            handle_new_repository(repo, portfolio_manager, dispatcher)
    else:
        logger.info("No new repositories detected since last poll.")
        
    save_last_checked_time(current_check_time)
    logger.info("One-off poll execution completed.")


def check_remote_sync_request() -> bool:
    """Checks if there is a pending sync request on the Vercel/local dashboard."""
    if not config.vercel_dashboard_url:
        return False
    try:
        url = f"{config.vercel_dashboard_url}/api/sync-request"
        r = requests.get(url, timeout=5)
        if r.status_code == 200:
            data = r.json()
            if data.get("sync_pending"):
                logger.info("Sync request detected from dashboard. Resetting flag and starting sync...")
                # Reset the flag to False so we don't trigger it repeatedly
                requests.post(url, json={"sync_pending": False}, timeout=5)
                return True
    except Exception as e:
        logger.debug(f"Could not connect to dashboard sync-request endpoint: {e}")
    return False


def run_daemon(github_client: GitHubClient, portfolio_manager: PortfolioManager, dispatcher: EventDispatcher):
    """Runs a polling loop daemon according to the poll_interval configuration."""
    interval = config.poll_interval
    logger.info(f"Starting background daemon mode. Poll interval: {interval} seconds.")
    
    try:
        while True:
            try:
                run_poll(github_client, portfolio_manager, dispatcher)
            except Exception as e:
                logger.error(f"Error in daemon polling cycle: {e}", exc_info=True)
                
            logger.info(f"Sleeping for {interval} seconds (checking for dashboard sync requests every 10s)...")
            
            elapsed = 0
            while elapsed < interval:
                if check_remote_sync_request():
                    logger.info("Instantly running sync triggered from dashboard.")
                    break
                time.sleep(10)
                elapsed += 10
    except KeyboardInterrupt:
        logger.info("Daemon execution stopped by user (KeyboardInterrupt).")


def run_webhook_server(github_client: GitHubClient, portfolio_manager: PortfolioManager, dispatcher: EventDispatcher, host: str, port: int):
    """Runs a FastAPI webhook receiver server with approve/reject link routing."""
    logger.info(f"Starting FastAPI webhook server on {host}:{port}")
    
    app = FastAPI(title="PortfolioSyncAgent Webhook Server")
    app.state.pending_updates = {}
    
    def webhook_callback(repo_metadata: dict):
        handle_new_repository(repo_metadata, portfolio_manager, dispatcher, pending_cache=app.state.pending_updates)
        
    webhook_router = get_webhook_router(github_client, webhook_callback)
    app.include_router(webhook_router)
    
    @app.get("/health")
    def health_check():
        return {"status": "healthy", "time": datetime.now(timezone.utc).isoformat()}

    @app.get("/review", response_class=HTMLResponse)
    def review_project(project: str):
        pending = app.state.pending_updates.get(project)
        if not pending:
            return f"""
            <html>
                <body style="font-family: sans-serif; text-align: center; padding-top: 50px;">
                    <h2 style="color: #dc3545;">Error</h2>
                    <p>No pending update found for project '{project}'. It may have already been approved or rejected.</p>
                </body>
            </html>
            """
        
        metadata = pending["metadata"]
        content = pending["content"]
        pm = pending["pm"]
        
        original_content = pm.read_target_file()
        
        # Colorize and build Diff
        import difflib
        original_lines = original_content.splitlines()
        updated_lines = content.splitlines()
        diff = "\n".join(difflib.unified_diff(original_lines, updated_lines, fromfile="original", tofile="updated"))
        
        encoded_project = urllib.parse.quote(project)
        approve_link = f"/approve?project={encoded_project}"
        reject_link = f"/reject?project={encoded_project}"

        html_page = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Review Portfolio Update - {project}</title>
            <style>
                body {{
                    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
                    background: linear-gradient(135deg, #0f172a, #1e1b4b);
                    color: #f8fafc;
                    margin: 0;
                    padding: 40px 20px;
                    display: flex;
                    justify-content: center;
                    min-height: 100vh;
                    box-sizing: border-box;
                }}
                .card {{
                    background: rgba(255, 255, 255, 0.03);
                    backdrop-filter: blur(16px);
                    border: 1px solid rgba(255, 255, 255, 0.08);
                    border-radius: 16px;
                    padding: 30px;
                    width: 100%;
                    max-width: 900px;
                    box-shadow: 0 10px 30px rgba(0,0,0,0.5);
                }}
                h1 {{
                    font-size: 24px;
                    margin-top: 0;
                    background: linear-gradient(to right, #38bdf8, #818cf8);
                    -webkit-background-clip: text;
                    -webkit-text-fill-color: transparent;
                }}
                .meta {{
                    display: grid;
                    grid-template-columns: repeat(2, 1fr);
                    gap: 15px;
                    margin-bottom: 25px;
                    background: rgba(255, 255, 255, 0.02);
                    padding: 15px;
                    border-radius: 8px;
                    border: 1px solid rgba(255, 255, 255, 0.05);
                }}
                .meta-item {{
                    font-size: 14px;
                }}
                .meta-label {{
                    font-weight: bold;
                    color: #94a3b8;
                }}
                .diff-container {{
                    background: #020617;
                    border: 1px solid #1e293b;
                    border-radius: 8px;
                    padding: 20px;
                    font-family: Consolas, Monaco, monospace;
                    font-size: 13px;
                    white-space: pre;
                    overflow-x: auto;
                    color: #cbd5e1;
                    max-height: 400px;
                    overflow-y: auto;
                    margin-bottom: 30px;
                }}
                .added {{ color: #4ade80; background: rgba(74, 222, 128, 0.08); padding: 2px 4px; border-radius: 2px; }}
                .removed {{ color: #f87171; background: rgba(248, 113, 113, 0.08); padding: 2px 4px; border-radius: 2px; }}
                .actions {{
                    display: flex;
                    gap: 15px;
                }}
                .btn {{
                    flex: 1;
                    padding: 14px;
                    border-radius: 8px;
                    font-weight: bold;
                    text-align: center;
                    text-decoration: none;
                    font-size: 16px;
                    transition: transform 0.2s, opacity 0.2s;
                    cursor: pointer;
                }}
                .btn:hover {{
                    transform: translateY(-2px);
                }}
                .btn-approve {{
                    background: linear-gradient(to right, #10b981, #059669);
                    color: white;
                }}
                .btn-reject {{
                    background: rgba(255, 255, 255, 0.05);
                    border: 1px solid rgba(255, 255, 255, 0.1);
                    color: #f1f5f9;
                }}
                .btn-reject:hover {{
                    background: rgba(239, 68, 68, 0.2);
                    border-color: #ef4444;
                }}
            </style>
        </head>
        <body>
            <div class="card">
                <h1>Review Portfolio Sync</h1>
                <p style="color: #94a3b8; font-size: 15px;">Review proposed updates for: <strong>{project}</strong></p>
                
                <div class="meta">
                    <div class="meta-item"><span class="meta-label">Project Name:</span> {metadata.get("name")}</div>
                    <div class="meta-item"><span class="meta-label">Source URL:</span> <a href="{metadata.get("url")}" target="_blank" style="color: #38bdf8; text-decoration: none;">GitHub Repo 🔗</a></div>
                    <div class="meta-item"><span class="meta-label">Languages:</span> {", ".join(metadata.get("languages", [])) if metadata.get("languages") else "None detected"}</div>
                    <div class="meta-item"><span class="meta-label">Created Date:</span> {metadata.get("created_at").strftime("%Y-%m-%d") if isinstance(metadata.get("created_at"), datetime) else ""}</div>
                </div>

                <h3>Diff View</h3>
                <div class="diff-container">"""
        
        for line in diff.splitlines():
            if line.startswith("+") and not line.startswith("+++"):
                html_page += f'<div class="added">{line}</div>'
            elif line.startswith("-") and not line.startswith("---"):
                html_page += f'<div class="removed">{line}</div>'
            else:
                html_page += f"<div>{line}</div>"

        html_page += f"""</div>

                <div class="actions">
                    <a href="{approve_link}" class="btn btn-approve">Approve & Push to det</a>
                    <a href="{reject_link}" class="btn btn-reject">Discard Changes</a>
                </div>
            </div>
        </body>
        </html>
        """
        return html_page

    @app.get("/approve", response_class=HTMLResponse)
    def approve_project(project: str):
        pending = app.state.pending_updates.get(project)
        if not pending:
            return f"""
            <html>
                <body style="font-family: sans-serif; text-align: center; padding-top: 50px;">
                    <h2 style="color: #dc3545;">Error</h2>
                    <p>No pending update found for project '{project}'. It may have already been approved or rejected.</p>
                </body>
            </html>
            """
            
        try:
            pm = pending["pm"]
            repo = pending["repo"]
            metadata = pending["metadata"]
            content = pending["content"]
            
            pm.write_target_file(content)
            success = pm.commit_and_push(repo, project)
            
            if success:
                dispatch_success_notifications(metadata, dispatcher)
                del app.state.pending_updates[project]
                return f"""
                <html>
                    <body style="font-family: sans-serif; text-align: center; padding-top: 50px; background-color: #f4fdf7;">
                        <h2 style="color: #28a745;">Success!</h2>
                        <p>Project <strong>{project}</strong> has been successfully approved, committed, and pushed to branch <code>{config.portfolio_branch}</code>.</p>
                    </body>
                </html>
                """
            else:
                del app.state.pending_updates[project]
                return f"""
                <html>
                    <body style="font-family: sans-serif; text-align: center; padding-top: 50px; background-color: #fffde8;">
                        <h2 style="color: #ffc107;">No Changes</h2>
                        <p>Approved, but no content changes were detected in the portfolio file.</p>
                    </body>
                </html>
                """
        except Exception as e:
            logger.exception(f"Error executing approval for '{project}': {e}")
            return f"""
            <html>
                <body style="font-family: sans-serif; text-align: center; padding-top: 50px; background-color: #fdf2f2;">
                    <h2 style="color: #dc3545;">Execution Failed</h2>
                    <p>Failed to commit/push approved updates: {e}</p>
                </body>
            </html>
            """

    @app.get("/reject", response_class=HTMLResponse)
    def reject_project(project: str):
        if project in app.state.pending_updates:
            del app.state.pending_updates[project]
            logger.info(f"Pending update for '{project}' was rejected and discarded.")
            return f"""
            <html>
                <body style="font-family: sans-serif; text-align: center; padding-top: 50px; background-color: #fdf2f2;">
                    <h2>Rejected</h2>
                    <p>Pending updates for project <strong>{project}</strong> have been discarded.</p>
                </body>
            </html>
            """
        return f"""
        <html>
            <body style="font-family: sans-serif; text-align: center; padding-top: 50px;">
                <h2 style="color: #dc3545;">Error</h2>
                <p>No pending update found for project '{project}'.</p>
            </body>
        </html>
        """
    # Start the daemon thread to handle periodic polling and remote trigger checking in the background
    daemon_thread = threading.Thread(
        target=run_daemon,
        args=(github_client, portfolio_manager, dispatcher),
        daemon=True
    )
    daemon_thread.start()
    logger.info("Background daemon thread started successfully inside webhook server.")
        
    uvicorn.run(app, host=host, port=port)


def main():
    parser = argparse.ArgumentParser(description="PortfolioSyncAgent - Automate developer portfolio updates.")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--poll", action="store_true", help="Perform a one-off GitHub poll and update.")
    group.add_argument("--daemon", action="store_true", help="Run as a daemon loop polling GitHub periodically.")
    group.add_argument("--serve", action="store_true", help="Run FastAPI webhook receiver server.")
    
    parser.add_argument("--host", type=str, default="0.0.0.0", help="Webhook server binding host (default: 0.0.0.0)")
    parser.add_argument("--port", type=int, default=8000, help="Webhook server port (default: 8000)")
    
    args = parser.parse_args()

    # 1. Validate Configurations
    validation_errors = config.validate()
    if validation_errors:
        logger.error("Configuration validation failed:")
        for error in validation_errors:
            logger.error(f"  - {error}")
        sys.exit(1)
        
    # Register Vercel logger handler if configured
    if config.vercel_dashboard_url:
        vercel_handler = VercelLogHandler(config.vercel_dashboard_url)
        vercel_handler.setFormatter(log_formatter)
        root_logger.addHandler(vercel_handler)
        logger.info(f"Vercel Log Handler registered targeting: {config.vercel_dashboard_url}")
        
    logger.info("Configuration validated successfully.")
    logger.info(f"Active Provider: {config.llm_provider.upper()} | Portfolio Branch: {config.portfolio_branch} | Format: {config.portfolio_structure_type.upper()}")

    # 2. Initialize Components
    github_client = GitHubClient(username=config.github_username, token=config.github_token)
    llm_connector = get_llm_connector(config)
    portfolio_manager = PortfolioManager(config, llm_connector)
    
    # Setup dispatchers
    dispatcher = EventDispatcher()
    dispatcher.register(LinkedInConnector())
    dispatcher.register(DiscordWebhookConnector())

    # 3. Route Execution
    if args.poll:
        run_poll(github_client, portfolio_manager, dispatcher)
    elif args.daemon:
        run_daemon(github_client, portfolio_manager, dispatcher)
    elif args.serve:
        run_webhook_server(github_client, portfolio_manager, dispatcher, args.host, args.port)


if __name__ == "__main__":
    main()
