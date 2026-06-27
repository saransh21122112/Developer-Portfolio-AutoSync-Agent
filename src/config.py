import os
import logging
from pathlib import Path
import yaml
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

class Config:
    def __init__(self, config_path: str = "config.yaml"):
        # Load environment variables from .env if present
        load_dotenv()

        self.config_path = Path(config_path)
        self.raw_yaml = {}

        if self.config_path.exists():
            try:
                with open(self.config_path, "r") as f:
                    self.raw_yaml = yaml.safe_load(f) or {}
            except Exception as e:
                logger.error(f"Failed to load yaml config at {config_path}: {e}")
        else:
            logger.warning(f"Config file not found at {config_path}. Using environment variables only.")

        # Resolve properties (checking Env overrides first, then yaml, then defaults)
        
        # GitHub Configurations
        github_cfg = self.raw_yaml.get("github", {})
        self.github_username = os.getenv("GITHUB_USERNAME", github_cfg.get("username", ""))
        self.github_token = os.getenv("GITHUB_TOKEN", "")
        
        try:
            self.poll_interval = int(os.getenv("POLL_INTERVAL", github_cfg.get("poll_interval", 3600)))
        except ValueError:
            self.poll_interval = 3600

        # Portfolio Configurations
        portfolio_cfg = self.raw_yaml.get("portfolio", {})
        self.portfolio_local_path = os.getenv("PORTFOLIO_LOCAL_PATH", portfolio_cfg.get("local_path", ""))
        self.portfolio_repo_url = os.getenv("PORTFOLIO_REPO_URL", portfolio_cfg.get("repo_url", ""))
        self.portfolio_branch = os.getenv("PORTFOLIO_BRANCH", portfolio_cfg.get("branch", "det"))
        self.portfolio_structure_type = os.getenv("PORTFOLIO_STRUCTURE_TYPE", portfolio_cfg.get("structure_type", "json")).lower()
        self.portfolio_file_path = os.getenv("PORTFOLIO_FILE_PATH", portfolio_cfg.get("file_path", ""))

        # LLM Configurations
        llm_cfg = self.raw_yaml.get("llm", {})
        self.llm_provider = os.getenv("LLM_PROVIDER", llm_cfg.get("provider", "mock")).lower()
        self.openai_api_key = os.getenv("OPENAI_API_KEY", "")
        self.openai_model = os.getenv("OPENAI_MODEL", llm_cfg.get("openai_model", "gpt-4o"))
        self.claude_cli_command = os.getenv("CLAUDE_CLI_COMMAND", llm_cfg.get("claude_cli_command", "claude"))

        # Human Approval & Email Configurations
        approval_cfg = self.raw_yaml.get("approval", {})
        self.approval_human_check = os.getenv("APPROVAL_HUMAN_CHECK", str(approval_cfg.get("human_check", True))).lower() in ("true", "1", "yes")
        
        email_cfg = approval_cfg.get("email", {})
        self.email_enabled = os.getenv("EMAIL_ENABLED", str(email_cfg.get("enabled", False))).lower() in ("true", "1", "yes")
        self.email_smtp_host = os.getenv("EMAIL_SMTP_HOST", email_cfg.get("smtp_host", "smtp.gmail.com"))
        
        try:
            self.email_smtp_port = int(os.getenv("EMAIL_SMTP_PORT", email_cfg.get("smtp_port", 587)))
        except ValueError:
            self.email_smtp_port = 587
            
        self.email_sender = os.getenv("EMAIL_SENDER", email_cfg.get("sender", ""))
        self.email_recipient = os.getenv("EMAIL_RECIPIENT", email_cfg.get("recipient", ""))
        self.email_base_url = os.getenv("EMAIL_BASE_URL", email_cfg.get("base_url", "http://localhost:8000"))
        
        self.smtp_username = os.getenv("SMTP_USERNAME", "")
        self.smtp_password = os.getenv("SMTP_PASSWORD", "")
        
        # Vercel Configuration
        self.vercel_dashboard_url = os.getenv("VERCEL_DASHBOARD_URL", "").rstrip("/")

    def validate(self) -> list:
        """Validates configuration settings and returns a list of error messages."""
        errors = []
        if not self.github_username:
            errors.append("GitHub username is required (set GITHUB_USERNAME or github.username in config.yaml)")
        if not self.portfolio_local_path:
            errors.append("Portfolio local path is required (set PORTFOLIO_LOCAL_PATH or portfolio.local_path in config.yaml)")
        if self.llm_provider == "openai" and not self.openai_api_key:
            errors.append("OpenAI API key is required when using openai provider (set OPENAI_API_KEY)")
        if self.portfolio_structure_type not in ("json", "markdown"):
            errors.append(f"Invalid portfolio structure type: '{self.portfolio_structure_type}'. Must be 'json' or 'markdown'")
        if not self.portfolio_file_path:
            errors.append("Portfolio project file path is required")
        if self.email_enabled:
            if not self.email_sender:
                errors.append("SMTP Sender email is required when email notifications are enabled")
            if not self.email_recipient:
                errors.append("SMTP Recipient email is required when email notifications are enabled")
            if not self.smtp_username:
                errors.append("SMTP Username is required when email notifications are enabled (set SMTP_USERNAME)")
            if not self.smtp_password:
                errors.append("SMTP Password is required when email notifications are enabled (set SMTP_PASSWORD)")
        return errors

# Global config instance
config = Config()
