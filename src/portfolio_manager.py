import os
import json
import logging
from pathlib import Path
from datetime import datetime
# pyrefly: ignore [missing-import]
import git
from src.config import Config
from src.llm_router import BaseLLMConnector

logger = logging.getLogger(__name__)

class PortfolioManager:
    def __init__(self, config: Config, llm_connector: BaseLLMConnector):
        self.config = config
        self.llm_connector = llm_connector
        self.local_path = Path(config.portfolio_local_path)
        self.target_file_path = self.local_path / config.portfolio_file_path

    def _get_authenticated_url(self) -> str:
        """Injects github token into the repo URL if config has a token and URL is HTTPS."""
        url = self.config.portfolio_repo_url
        token = self.config.github_token
        if token and url.startswith("https://github.com/"):
            return url.replace("https://github.com/", f"https://oauth2:{token}@github.com/")
        return url

    def checkout_configured_branch(self, repo: git.Repo):
        """Checks out the configured branch, creating it from the active branch if it doesn't exist."""
        branch_name = self.config.portfolio_branch
        logger.info(f"Ensuring branch '{branch_name}' is checked out...")
        
        has_origin = False
        try:
            if "origin" in [r.name for r in repo.remotes]:
                has_origin = True
                repo.remotes.origin.fetch()
        except Exception as e:
            logger.warning(f"Could not fetch from origin: {e}")

        # Check if local branch exists
        if branch_name in repo.heads:
            repo.git.checkout(branch_name)
            logger.info(f"Switched to existing local branch '{branch_name}'.")
        else:
            # Local branch doesn't exist, check if origin has it
            remote_branch_ref = f"origin/{branch_name}"
            remote_branch_exists = False
            
            if has_origin:
                try:
                    for ref in repo.references:
                        if ref.name == remote_branch_ref:
                            remote_branch_exists = True
                            break
                except Exception as e:
                    logger.warning(f"Error checking remote references: {e}")

            if remote_branch_exists:
                repo.git.checkout("-b", branch_name, remote_branch_ref)
                logger.info(f"Switched to and tracked remote branch '{remote_branch_ref}'.")
            else:
                repo.git.checkout("-b", branch_name)
                logger.info(f"Created and switched to brand new local branch '{branch_name}'.")

    def ensure_repository_local(self) -> git.Repo:
        """Ensures the repository exists locally, cloning it if necessary."""
        if not self.local_path.exists():
            self.local_path.mkdir(parents=True, exist_ok=True)
            
        try:
            # Check if it is a valid git repository
            repo = git.Repo(self.local_path)
            logger.info(f"Existing Git repository found at {self.local_path}")
        except (git.InvalidGitRepositoryError, git.NoSuchPathError):
            logger.info(f"No git repository at {self.local_path}. Cloning from {self.config.portfolio_repo_url}...")
            if not self.config.portfolio_repo_url:
                raise ValueError("Portfolio repository URL is required to clone the repository.")
            
            auth_url = self._get_authenticated_url()
            repo = git.Repo.clone_from(auth_url, self.local_path)
            logger.info("Successfully cloned portfolio repository.")
            
        self.checkout_configured_branch(repo)
        return repo

    def sync_local_repo(self, repo: git.Repo):
        """Pulls the latest changes from origin to ensure local is up to date."""
        branch_name = self.config.portfolio_branch
        
        has_origin = False
        try:
            if "origin" in [r.name for r in repo.remotes]:
                has_origin = True
        except Exception as e:
            logger.warning(f"Could not check remotes: {e}")

        if not has_origin:
            logger.warning("No remote 'origin' configured for portfolio repository. Skipping pull.")
            return

        try:
            logger.info(f"Pulling latest changes from remote '{branch_name}'...")
            origin = repo.remote(name="origin")
            
            auth_url = self._get_authenticated_url()
            if auth_url != origin.url:
                origin.set_url(auth_url)
                
            repo.git.pull("origin", branch_name)
            logger.info("Local repository pulled successfully.")
        except Exception as e:
            if "has no tracking information" in str(e) or "Couldn't find remote ref" in str(e) or "does not appear to be a git repository" in str(e):
                logger.warning(f"Remote branch '{branch_name}' might not exist on origin yet. Skipping pull: {e}")
            else:
                logger.error(f"Git pull failed: {e}")
                raise

    def is_project_already_added(self, project_metadata: dict) -> bool:
        """Checks if the project already exists in the portfolio (by name or URL)."""
        original_content = self.read_target_file()
        project_name = project_metadata.get("name", "").strip()
        project_url = project_metadata.get("url", "").strip()

        if not project_name and not project_url:
            return False

        if self.config.portfolio_structure_type == "json":
            try:
                data = json.loads(original_content)
                projects = []
                if isinstance(data, list):
                    projects = data
                elif isinstance(data, dict) and "projects" in data:
                    projects = data["projects"]
                
                for p in projects:
                    p_name = p.get("name", "").strip().lower()
                    p_url = p.get("url", "").strip().lower()
                    
                    if project_name and p_name == project_name.lower():
                        return True
                    if project_url and p_url == project_url.lower():
                        return True
                    
                    if project_url and p_url:
                        url1 = project_url.lower().rstrip("/")
                        if url1.endswith(".git"):
                            url1 = url1[:-4]
                        url2 = p_url.rstrip("/")
                        if url2.endswith(".git"):
                            url2 = url2[:-4]
                        if url1 == url2:
                            return True
            except Exception as e:
                logger.error(f"Error parsing JSON for duplicate check: {e}")
        else:
            # Markdown check
            if project_url:
                url_clean = project_url.rstrip("/")
                if url_clean.endswith(".git"):
                    url_clean = url_clean[:-4]
                
                if project_url in original_content or url_clean in original_content:
                    return True
            
            if project_name:
                name_patterns = [
                    f"[{project_name}]",
                    f"**{project_name}**",
                    f"#{project_name}",
                    f"## {project_name}"
                ]
                for pattern in name_patterns:
                    if pattern in original_content:
                        return True
                        
        return False

    def read_target_file(self) -> str:
        """Reads the target portfolio file (projects.json or README.md)."""
        if not self.target_file_path.exists():
            logger.warning(f"Target file {self.target_file_path} does not exist. Initializing empty content.")
            if self.config.portfolio_structure_type == "json":
                return "[]"
            else:
                return "# Projects\n\nNo projects listed yet.\n"
        
        with open(self.target_file_path, "r", encoding="utf-8") as f:
            return f.read()

    def generate_updated_content(self, original_content: str, project_metadata: dict) -> str:
        """Constructs prompts and requests the LLM to update the portfolio content."""
        date_str = project_metadata.get("created_at")
        if isinstance(date_str, datetime):
            date_str = date_str.strftime("%Y-%m-%d")
        else:
            date_str = datetime.now().strftime("%Y-%m-%d")

        project_info = {
            "name": project_metadata.get("name"),
            "description": project_metadata.get("description"),
            "url": project_metadata.get("url"),
            "languages": project_metadata.get("languages", []),
            "date": date_str
        }

        if self.config.portfolio_structure_type == "json":
            system_prompt = (
                "You are an expert system that updates an existing portfolio JSON file containing project metadata.\n"
                "Your task is to insert the new project into the project list.\n"
                "You MUST return ONLY valid JSON. Do not include any explanation or markdown formatting code blocks (like ```json ... ```).\n"
                "The project list is typically an array of objects (or an object with a 'projects' array key). "
                "Insert the new project at the beginning of the list (reverse chronological order).\n"
                "Do NOT modify, delete, or reformat any of the other existing project entries. "
                "Keep all keys, values, and casing of the existing entries exactly as they are.\n"
            )
            user_content = (
                f"Existing JSON File:\n```json\n{original_content}\n```\n\n"
                f"New Project Metadata to Add:\n{json.dumps(project_info, indent=2)}\n\n"
                f"Please output the updated JSON content."
            )
        else:
            system_prompt = (
                "You are an expert technical writer and web developer.\n"
                "Your task is to update a portfolio markdown file (typically README.md) by adding a new project to the projects section.\n"
                "Examine the structure of the existing markdown. Identify the projects section (e.g., under a header like '# Projects' or '## Projects').\n"
                "Insert the new project at the beginning of the list, table, or section (reverse chronological order) "
                "matching the exact formatting style of the other project entries.\n"
                "Do NOT modify, delete, or reorder any other sections or existing projects. Keep the rest of the markdown exactly the same.\n"
                "Return the complete updated markdown text. Do not wrap it in any extra code block syntax unless it is part of the document itself."
            )
            user_content = (
                f"Existing Markdown File:\n---\n{original_content}\n---\n\n"
                f"New Project Metadata to Add:\n"
                f"Name: {project_info['name']}\n"
                f"Description: {project_info['description']}\n"
                f"URL: {project_info['url']}\n"
                f"Languages/Technologies: {', '.join(project_info['languages'])}\n"
                f"Created Date: {project_info['date']}\n\n"
                f"Please output the updated Markdown content."
            )

        updated_content = self.llm_connector.execute_prompt(system_prompt, user_content)
        
        # Clean up any potential markdown fences returned by the LLM (e.g. ```json ... ```)
        if self.config.portfolio_structure_type == "json":
            updated_content = updated_content.strip()
            if updated_content.startswith("```json"):
                updated_content = updated_content[7:]
            elif updated_content.startswith("```"):
                updated_content = updated_content[3:]
            if updated_content.endswith("```"):
                updated_content = updated_content[:-3]
            updated_content = updated_content.strip()
            
        return updated_content

    def validate_content(self, content: str) -> bool:
        """Validates that the content is formatted correctly according to configuration."""
        if self.config.portfolio_structure_type == "json":
            try:
                json.loads(content)
                return True
            except json.JSONDecodeError as e:
                logger.error(f"Updated content is not valid JSON: {e}\nContent snippet:\n{content[:200]}")
                return False
        return len(content.strip()) > 0

    def write_target_file(self, content: str):
        """Writes the updated content back to the target file."""
        self.target_file_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.target_file_path, "w", encoding="utf-8") as f:
            f.write(content)
        logger.info(f"Successfully updated target file at {self.target_file_path}")

    def commit_and_push(self, repo: git.Repo, project_name: str) -> bool:
        """Commits and pushes changes to the remote repository."""
        branch_name = self.config.portfolio_branch
        try:
            if not repo.is_dirty(untracked_files=True):
                logger.info("No changes detected in the repository after update.")
                return False

            relative_target_path = self.config.portfolio_file_path
            repo.git.add(relative_target_path)
            
            commit_message = f"Auto-update portfolio: Added {project_name}"
            repo.index.commit(commit_message)
            logger.info(f"Committed changes with message: '{commit_message}'")

            # Check if remote "origin" exists
            has_origin = False
            try:
                if "origin" in [r.name for r in repo.remotes]:
                    has_origin = True
            except:
                pass

            if not has_origin:
                logger.warning("No remote 'origin' configured. Skipping remote push.")
                return True

            logger.info(f"Pushing changes to remote branch '{branch_name}'...")
            origin = repo.remote(name="origin")
            
            auth_url = self._get_authenticated_url()
            if auth_url != origin.url:
                origin.set_url(auth_url)
                
            repo.git.push("-u", "origin", branch_name)
            logger.info("Successfully pushed changes to remote repository.")
            return True
        except Exception as e:
            logger.error(f"Failed to commit and push changes: {e}")
            raise

    def synchronize_project(self, project_metadata: dict) -> bool:
        """Orchestrates the entire synchronization flow for a project repository."""
        project_name = project_metadata.get("name", "Unknown Project")
        logger.info(f"Starting portfolio synchronization for: {project_name}")

        # 1. Ensure local repo copy exists and is clone/pull aligned
        repo = self.ensure_repository_local()
        self.sync_local_repo(repo)

        # 2. Check if project is already added
        if self.is_project_already_added(project_metadata):
            logger.info(f"Project '{project_name}' is already present in the portfolio. Skipping synchronization.")
            return False

        # 3. Read target file
        original_content = self.read_target_file()

        # 4. Generate updated content using LLM
        updated_content = self.generate_updated_content(original_content, project_metadata)

        # 5. Validate output
        if not self.validate_content(updated_content):
            logger.error("Generated content failed validation. Aborting file update.")
            return False

        # 6. Overwrite the file
        self.write_target_file(updated_content)

        # 7. Commit and Push
        success = self.commit_and_push(repo, project_name)
        return success
