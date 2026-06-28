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
        elif self.config.portfolio_structure_type == "typescript":
            system_prompt = (
                "You are an expert front-end developer.\n"
                "Your task is to update a TypeScript file defining portfolio data by adding a new project to the projects array.\n"
                "Examine the structure of the existing file. Locate the projects array (typically export const projectsData: Project[] = [...]).\n"
                "You MUST follow these rules strictly:\n"
                "1. POSITION: Always insert the new project object at the beginning of the projectsData array (index 0 / first element of the array).\n"
                "2. RENUMBERING & SHIFTING:\n"
                "   - Set the newly added project's 'order' property to 'Project 1'.\n"
                "   - Shift the 'order' label of all pre-existing projects in the array up by one (e.g., previous 'Project 1' becomes 'Project 2', previous 'Project 2' becomes 'Project 3', etc.). Do not modify any other properties or values of the existing projects.\n"
                "3. HIGH-FIDELITY PROJECT DESCRIPTIONS:\n"
                "   - Do not simply copy the raw GitHub repository description or tagline.\n"
                "   - Compose a compelling, professional 2-3 sentence project summary. Detail the core problem the project solves, its main workflows/capabilities, and the key technologies used. Match the tone and depth of existing descriptions.\n"
                "4. TECH STACK ICON FILTERING:\n"
                "   - Select only 3-5 major languages, databases, or frameworks (e.g. 'typescript', 'openai', 'langchain', 'python', 'fastapi', 'docker', 'nodejs', 'aws', 'postgresql', 'gcp', 'anthropic').\n"
                "   - Do NOT include minor configuration/markup/scripting languages (such as HTML, CSS, Shell, HCL, MDX, Go templates, YAML) as they do not map to colored logos and will clutter the UI with generic letter badges.\n"
                "   - Use the lowercase mapped keys for the iconKey property (e.g., 'typescript', 'openai', 'langchain', 'docker').\n\n"
                "Construct the new project object matching the existing Project type schema:\n"
                "{\n"
                "  id: string (slugified lowercase project name, e.g. 'project-name'),\n"
                "  order: string,\n"
                "  title: string,\n"
                "  techIcons: TechIcon[],\n"
                "  description: string,\n"
                "  githubUrl: string,\n"
                "  liveUrl: string (optional)\n"
                "}\n\n"
                "Do NOT modify, delete, or reorder any other parts of the file (such as imports, other arrays, or other fields of existing projects).\n"
                "Keep all other formatting, indentation, syntax, and array items exactly unchanged.\n"
                "Return the complete updated TypeScript file content. Do NOT wrap the code in any markdown fences (like ```typescript ... ```)."
            )
            user_content = (
                f"Existing TypeScript File:\n---\n{original_content}\n---\n\n"
                f"New Project Metadata to Add:\n"
                f"Name: {project_info['name']}\n"
                f"Description: {project_info['description']}\n"
                f"URL: {project_info['url']}\n"
                f"Languages/Technologies: {', '.join(project_info['languages'])}\n"
                f"Created Date: {project_info['date']}\n\n"
                f"Please output the updated TypeScript content."
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
        
        # Clean up any potential markdown fences returned by the LLM
        if self.config.portfolio_structure_type in ("json", "typescript"):
            updated_content = updated_content.strip()
            if updated_content.startswith("```typescript"):
                updated_content = updated_content[13:]
            elif updated_content.startswith("```javascript"):
                updated_content = updated_content[13:]
            elif updated_content.startswith("```json"):
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

    def generate_project_visuals(self, project_id: str, project_name: str, project_description: str) -> dict:
        """Uses LLM to generate custom React SVG component and mapping entries for ProjectsSection.tsx."""
        system_prompt = (
            "You are an expert React developer and SVG designer.\n"
            "Your task is to design a custom, clean SVG illustration representing the project: '{name}'.\n"
            "Description of the project: '{description}'\n\n"
            "Examine the style of existing SVG components in the portfolio:\n"
            "- They use viewBox='0 0 80 80', width='72', height='72', fill='none'.\n"
            "- They feature neat outlines, circuit lines, trends, or badge shapes using solid white lines and semi-transparent white fills (e.g. rgba(255,255,255,0.15) or rgba(255,255,255,0.4)).\n\n"
            "Generate:\n"
            "1. A clean React SVG component function named '{ClassName}SVG()'. Use simple, valid React SVG tags.\n"
            "2. The key-value pair to add to the PROJECT_SVG dictionary.\n"
            "3. The key-value pair to add to the PROJECT_VISUALS dictionary with a premium linear-gradient background matching the project theme.\n\n"
            "You MUST format your output strictly as follows, with no additional explanation, commentary, or markdown blocks:\n"
            "===SVG_COMPONENT===\n"
            "function {ClassName}SVG() {{\n"
            "  return (\n"
            "    <svg viewBox=\"0 0 80 80\" width=\"72\" height=\"72\" fill=\"none\" xmlns=\"http://www.w3.org/2000/svg\">\n"
            "      ...\n"
            "    </svg>\n"
            "  );\n"
            "}}\n"
            "===PROJECT_SVG_ENTRY===\n"
            "  \"{project_id}\": <{ClassName}SVG />,\n"
            "===PROJECT_VISUALS_ENTRY===\n"
            "  \"{project_id}\": {{ gradient: \"linear-gradient(135deg, #color1 0%, #color2 100%)\" }},"
        ).format(
            name=project_name,
            description=project_description,
            ClassName="".join(x.capitalize() for x in project_id.replace("-", "_").split("_")),
            project_id=project_id
        )
        
        response = self.llm_connector.execute_prompt(system_prompt, "Please generate the component and entries.")
        
        # Parse the response
        result = {}
        current_key = None
        lines = []
        
        for line in response.splitlines():
            if line.strip().startswith("===SVG_COMPONENT==="):
                if current_key: result[current_key] = "\n".join(lines).strip()
                current_key = "svg_component"
                lines = []
            elif line.strip().startswith("===PROJECT_SVG_ENTRY==="):
                if current_key: result[current_key] = "\n".join(lines).strip()
                current_key = "project_svg_entry"
                lines = []
            elif line.strip().startswith("===PROJECT_VISUALS_ENTRY==="):
                if current_key: result[current_key] = "\n".join(lines).strip()
                current_key = "project_visuals_entry"
                lines = []
            else:
                lines.append(line)
                
        if current_key:
            result[current_key] = "\n".join(lines).strip()
            
        return result

    def update_projects_section_file(self, project_id: str, project_name: str, project_description: str):
        file_path = self.local_path / "app/components/ProjectsSection.tsx"
        if not file_path.exists():
            logger.warning(f"ProjectsSection.tsx not found at {file_path}. Skipping visual update.")
            return
            
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
            
        # Check if already added to avoid duplicates
        if f'"{project_id}":' in content or f"'{project_id}':" in content:
            logger.info(f"Visuals for project '{project_id}' already present in ProjectsSection.tsx. Skipping.")
            return
            
        visuals = self.generate_project_visuals(project_id, project_name, project_description)
        svg_comp = visuals.get("svg_component")
        svg_entry = visuals.get("project_svg_entry")
        visuals_entry = visuals.get("project_visuals_entry")
        
        if not svg_comp or not svg_entry or not visuals_entry:
            logger.error("Failed to generate complete visual assets for the project.")
            return
            
        # 1. Inject SVG component before PROJECT_SVG definition
        target_marker = "const PROJECT_SVG:"
        if target_marker in content:
            content = content.replace(target_marker, f"{svg_comp}\n\n{target_marker}")
            
        # 2. Inject entry in PROJECT_SVG mapping
        target_marker_2 = "const PROJECT_SVG: Record<string, React.ReactNode> = {"
        if target_marker_2 in content:
            content = content.replace(target_marker_2, f"{target_marker_2}\n  {svg_entry}")
            
        # 3. Inject entry in PROJECT_VISUALS mapping
        target_marker_3 = "const PROJECT_VISUALS: Record<string, { gradient: string }> = {"
        if target_marker_3 in content:
            content = content.replace(target_marker_3, f"{target_marker_3}\n  {visuals_entry}")
            
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(content)
            
        logger.info(f"Successfully updated ProjectsSection.tsx with visual illustration for {project_name}.")

    def commit_and_push(self, repo: git.Repo, project_name: str) -> bool:
        """Commits and pushes changes to the remote repository."""
        branch_name = self.config.portfolio_branch
        try:
            if not repo.is_dirty(untracked_files=True):
                logger.info("No changes detected in the repository after update.")
                return False

            relative_target_path = self.config.portfolio_file_path
            repo.git.add(relative_target_path)
            
            # Also stage ProjectsSection.tsx if it exists and was modified
            components_path = "app/components/ProjectsSection.tsx"
            if (self.local_path / components_path).exists():
                try:
                    repo.git.add(components_path)
                except Exception as e:
                    logger.warning(f"Could not stage components file: {e}")
            
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

        # 6b. Update ProjectsSection.tsx with custom SVG illustration
        if self.config.portfolio_structure_type == "typescript":
            try:
                self.update_projects_section_file(
                    project_metadata.get("id", project_name.lower().replace(" ", "-")),
                    project_name,
                    project_metadata.get("description", "")
                )
            except Exception as e:
                logger.error(f"Failed to update ProjectsSection.tsx: {e}")

        # 7. Commit and Push
        success = self.commit_and_push(repo, project_name)
        return success
