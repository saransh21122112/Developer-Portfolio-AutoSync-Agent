import smtplib
import logging
import urllib.parse
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from src.config import Config

logger = logging.getLogger(__name__)

class Mailer:
    def __init__(self, config: Config):
        self.config = config

    def send_approval_request(self, project_name: str, description: str, repo_url: str, languages: list, date_str: str, diff: str) -> bool:
        """Sends an HTML email with the project metadata and diff, plus approval endpoints."""
        if not self.config.email_enabled:
            logger.info("Email notifications are disabled. Skipping email transmission.")
            return False

        logger.info(f"Sending approval email for project: '{project_name}' to {self.config.email_recipient}")
        
        base_url = self.config.email_base_url.rstrip("/")
        encoded_project = urllib.parse.quote(project_name)
        approve_link = f"{base_url}/approve?project={encoded_project}"
        reject_link = f"{base_url}/reject?project={encoded_project}"

        subject = f"[PortfolioSyncAgent] Approval Required: {project_name}"
        
        html_content = f"""
        <html>
        <head>
            <style>
                body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; line-height: 1.6; color: #333; margin: 0; padding: 20px; background-color: #f8f9fa; }}
                .container {{ max-width: 600px; margin: 0 auto; padding: 30px; border: 1px solid #e9ecef; border-radius: 8px; background-color: #ffffff; box-shadow: 0 4px 6px rgba(0, 0, 0, 0.05); }}
                h2 {{ color: #007bff; margin-top: 0; border-bottom: 2px solid #e9ecef; padding-bottom: 10px; }}
                .btn {{ display: inline-block; padding: 12px 24px; text-decoration: none; border-radius: 4px; font-weight: bold; margin-right: 15px; margin-top: 15px; }}
                .btn-approve {{ background-color: #28a745; color: white !important; }}
                .btn-reject {{ background-color: #dc3545; color: white !important; }}
                .diff-box {{ background-color: #f8f9fa; border-left: 4px solid #6c757d; padding: 15px; font-family: "SFMono-Regular", Consolas, "Liberation Mono", Menlo, Courier, monospace; font-size: 13px; overflow-x: auto; white-space: pre-wrap; margin-top: 15px; border-radius: 4px; }}
                .meta-table {{ width: 100%; border-collapse: collapse; margin-bottom: 25px; margin-top: 20px; }}
                .meta-table td {{ padding: 10px; border-bottom: 1px solid #f1f3f5; font-size: 14px; }}
                .meta-table td.label {{ font-weight: bold; width: 150px; color: #495057; }}
            </style>
        </head>
        <body>
            <div class="container">
                <h2>Portfolio Update Pending Approval</h2>
                <p>The PortfolioSyncAgent has processed a new repository and is waiting for your authorization before making git changes.</p>
                
                <table class="meta-table">
                    <tr><td class="label">Project Name:</td><td>{project_name}</td></tr>
                    <tr><td class="label">Description:</td><td>{description}</td></tr>
                    <tr><td class="label">Repository URL:</td><td><a href="{repo_url}">{repo_url}</a></td></tr>
                    <tr><td class="label">Languages:</td><td>{', '.join(languages)}</td></tr>
                    <tr><td class="label">Date:</td><td>{date_str}</td></tr>
                </table>

                <h3>Proposed Content Changes</h3>
                <div class="diff-box">{diff}</div>

                <p style="margin-top: 30px;">
                    <a href="{approve_link}" class="btn btn-approve">Approve & Push</a>
                    <a href="{reject_link}" class="btn btn-reject">Reject & Discard</a>
                </p>
                
                <p style="font-size: 12px; color: #6c757d; margin-top: 30px; border-top: 1px solid #e9ecef; padding-top: 15px;">
                    If the links do not work, you can approve the change via the CLI or server endpoints.<br>
                    This is an automated message sent by PortfolioSyncAgent.
                </p>
            </div>
        </body>
        </html>
        """

        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = self.config.email_sender
        msg["To"] = self.config.email_recipient

        text_content = (
            f"Approval Required for project: {project_name}\n\n"
            f"Description: {description}\n"
            f"URL: {repo_url}\n"
            f"Languages: {', '.join(languages)}\n"
            f"Date: {date_str}\n\n"
            f"Proposed Diff:\n{diff}\n\n"
            f"Approve Link: {approve_link}\n"
            f"Reject Link: {reject_link}\n"
        )
        
        msg.attach(MIMEText(text_content, "plain"))
        msg.attach(MIMEText(html_content, "html"))

        try:
            with smtplib.SMTP(self.config.email_smtp_host, self.config.email_smtp_port) as server:
                server.starttls()
                server.login(self.config.smtp_username, self.config.smtp_password)
                server.sendmail(self.config.email_sender, self.config.email_recipient, msg.as_string())
            logger.info("Approval request email sent successfully.")
            return True
        except Exception as e:
            logger.error(f"Failed to send email via SMTP: {e}")
            return False
