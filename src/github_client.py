import os
import base64
import logging
from datetime import datetime, timezone
import requests
from typing import Dict, List, Optional, Callable
from fastapi import APIRouter, Request, HTTPException, BackgroundTasks

logger = logging.getLogger(__name__)

class GitHubClient:
    def __init__(self, username: str, token: Optional[str] = None):
        self.username = username
        self.token = token
        self.base_url = "https://api.github.com"
        
        self.headers = {
            "Accept": "application/vnd.github.v3+json",
        }
        if self.token:
            self.headers["Authorization"] = f"token {self.token}"

    def _get(self, url: str) -> requests.Response:
        """Helper to make GET requests with standard headers."""
        response = requests.get(url, headers=self.headers)
        response.raise_for_status()
        return response

    def fetch_user_repos(self) -> List[Dict]:
        """Fetches all public repositories for the user, sorted by creation date."""
        url = f"{self.base_url}/users/{self.username}/repos?sort=created&direction=desc"
        try:
            response = self._get(url)
            return response.json()
        except Exception as e:
            logger.error(f"Failed to fetch repositories for user {self.username}: {e}")
            return []

    def fetch_repo_languages(self, repo_name: str) -> List[str]:
        """Fetches list of languages used in the repository."""
        url = f"{self.base_url}/repos/{self.username}/{repo_name}/languages"
        try:
            response = self._get(url)
            languages_dict = response.json()
            # Return languages sorted by code size (highest first)
            return sorted(languages_dict.keys(), key=lambda k: languages_dict[k], reverse=True)
        except Exception as e:
            logger.error(f"Failed to fetch languages for repo {repo_name}: {e}")
            return []

    def fetch_repo_readme(self, repo_name: str) -> str:
        """Fetches the raw content of the README.md file in the repository."""
        # Try common readme variants
        readme_variants = ["README.md", "readme.md", "README", "readme"]
        for variant in readme_variants:
            url = f"{self.base_url}/repos/{self.username}/{repo_name}/contents/{variant}"
            try:
                response = self._get(url)
                data = response.json()
                if "content" in data and data.get("encoding") == "base64":
                    decoded_bytes = base64.b64decode(data["content"])
                    return decoded_bytes.decode("utf-8", errors="ignore")
            except requests.HTTPError as e:
                if e.response.status_code == 404:
                    continue  # Try next variant
                logger.error(f"HTTP error fetching readme variant {variant} for {repo_name}: {e}")
            except Exception as e:
                logger.error(f"Error fetching readme variant {variant} for {repo_name}: {e}")
        
        logger.warning(f"No README file found for repository {repo_name}.")
        return ""

    def get_repo_metadata(self, repo_dict: Dict) -> Dict:
        """Compiles detailed metadata for a repository."""
        repo_name = repo_dict.get("name", "")
        description = repo_dict.get("description") or ""
        html_url = repo_dict.get("html_url", "")
        created_at_str = repo_dict.get("created_at", "")
        
        # Parse datetime
        created_at = None
        if created_at_str:
            # Handle standard ISO formats, e.g. "2026-06-27T19:40:48Z" -> convert Z to +00:00
            if created_at_str.endswith("Z"):
                created_at_str = created_at_str[:-1] + "+00:00"
            created_at = datetime.fromisoformat(created_at_str)

        languages = self.fetch_repo_languages(repo_name)
        readme_content = self.fetch_repo_readme(repo_name)

        return {
            "name": repo_name,
            "description": description,
            "url": html_url,
            "created_at": created_at,
            "languages": languages,
            "readme": readme_content
        }

    def poll_new_repositories(self, since_time: datetime) -> List[Dict]:
        """Polls user's repositories and returns metadata of repos created since since_time."""
        logger.info(f"Polling repos for user '{self.username}' since {since_time}...")
        repos = self.fetch_user_repos()
        new_repos = []

        for repo in repos:
            created_at_str = repo.get("created_at", "")
            if not created_at_str:
                continue
            if created_at_str.endswith("Z"):
                created_at_str = created_at_str[:-1] + "+00:00"
            
            created_at = datetime.fromisoformat(created_at_str)
            
            if created_at > since_time:
                logger.info(f"Detected new repository: {repo.get('name')}")
                # Fetch detailed metadata
                metadata = self.get_repo_metadata(repo)
                new_repos.append(metadata)
                
        return new_repos


def get_webhook_router(github_client: GitHubClient, callback: Callable[[Dict], None]) -> APIRouter:
    """Creates a FastAPI router for handling GitHub webhook events."""
    router = APIRouter()

    @router.post("/webhook")
    async def webhook_receiver(request: Request, background_tasks: BackgroundTasks):
        # Read payload
        try:
            payload = await request.json()
        except Exception as e:
            logger.error(f"Invalid webhook JSON payload: {e}")
            raise HTTPException(status_code=400, detail="Invalid JSON")

        event_type = request.headers.get("X-GitHub-Event", "")
        logger.info(f"Received GitHub webhook event: '{event_type}'")

        # Handle 'repository' event (specifically when a repository is created or made public)
        if event_type == "repository":
            action = payload.get("action", "")
            repository = payload.get("repository", {})
            owner = repository.get("owner", {}).get("login", "")
            
            # Check if this repository is owned by the user
            if owner.lower() != github_client.username.lower():
                return {"status": "ignored", "reason": f"Repository owner '{owner}' does not match configured user '{github_client.username}'."}
                
            if action in ("created", "publicized"):
                repo_name = repository.get("name")
                logger.info(f"Repository webhook '{action}' event triggered for '{repo_name}'")
                
                # Fetch full metadata in background task to avoid blocking webhook response
                background_tasks.add_task(_process_webhook_repo, github_client, repository, callback)
                return {"status": "processing", "event": f"repository.{action}"}

        # Handle 'push' event (when a new repository is created, its initial push might trigger this)
        elif event_type == "push":
            ref = payload.get("ref", "")
            # Check if it's a push to the default branch (e.g. main/master)
            repository = payload.get("repository", {})
            default_branch = repository.get("default_branch", "main")
            owner = repository.get("owner", {}).get("login", "")
            
            if owner.lower() != github_client.username.lower():
                return {"status": "ignored", "reason": f"Push owner '{owner}' does not match configured user '{github_client.username}'."}

            if f"refs/heads/{default_branch}" in ref:
                # To prevent spamming, we can double check if we need to sync
                # Usually we want to sync when the repository is newly created or majorly updated
                repo_name = repository.get("name")
                logger.info(f"Push event triggered for '{repo_name}' on branch '{default_branch}'")
                
                background_tasks.add_task(_process_webhook_repo, github_client, repository, callback)
                return {"status": "processing", "event": "push"}

        return {"status": "ignored", "reason": f"Unhandled event type '{event_type}' or action"}

    return router


def _process_webhook_repo(github_client: GitHubClient, repo_payload: Dict, callback: Callable[[Dict], None]):
    """Background task to fetch full repository details and fire the callback."""
    try:
        metadata = github_client.get_repo_metadata(repo_payload)
        callback(metadata)
    except Exception as e:
        logger.exception(f"Error processing webhook repo payload: {e}")
