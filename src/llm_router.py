import subprocess
import logging
import json
from abc import ABC, abstractmethod
from typing import Optional
from openai import OpenAI
from src.config import Config

logger = logging.getLogger(__name__)

class BaseLLMConnector(ABC):
    @abstractmethod
    def execute_prompt(self, system_prompt: str, user_content: str) -> str:
        """Executes a prompt against the configured LLM provider and returns the string response."""
        pass


class OpenAIConnector(BaseLLMConnector):
    def __init__(self, api_key: str, model: str = "gpt-4o", response_json: bool = False):
        self.client = OpenAI(api_key=api_key)
        self.model = model
        self.response_json = response_json

    def execute_prompt(self, system_prompt: str, user_content: str) -> str:
        logger.info(f"Executing prompt via OpenAI (Model: {self.model}, JSON mode: {self.response_json})")
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content}
        ]
        
        kwargs = {
            "model": self.model,
            "messages": messages,
            "temperature": 0.2
        }
        
        if self.response_json:
            kwargs["response_format"] = {"type": "json_object"}

        try:
            response = self.client.chat.completions.create(**kwargs)
            result = response.choices[0].message.content
            return result or ""
        except Exception as e:
            logger.error(f"OpenAI API call failed: {e}")
            raise RuntimeError(f"OpenAI Connector failure: {e}") from e


class ClaudeCliConnector(BaseLLMConnector):
    def __init__(self, cli_command: str = "claude"):
        self.cli_command = cli_command

    def execute_prompt(self, system_prompt: str, user_content: str) -> str:
        logger.info(f"Executing prompt via local Claude CLI command: '{self.cli_command}'")
        
        # Combine prompt elements
        combined_input = f"System Instruction:\n{system_prompt}\n\nUser Input:\n{user_content}"
        
        try:
            # Execute Claude CLI via subprocess passing prompt through stdin
            process = subprocess.Popen(
                [self.cli_command],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                shell=True # Supports commands with flags/aliases in some shells
            )
            
            stdout, stderr = process.communicate(input=combined_input)
            
            if process.returncode != 0:
                logger.error(f"Claude CLI returned non-zero exit code: {process.returncode}. Stderr: {stderr}")
                raise RuntimeError(f"Claude CLI process failed with code {process.returncode}: {stderr}")
                
            return stdout.strip()
        except FileNotFoundError as e:
            logger.error(f"Claude CLI command '{self.cli_command}' not found on local PATH: {e}")
            raise RuntimeError(f"Claude CLI not found: {e}") from e
        except Exception as e:
            logger.exception(f"Unexpected error running Claude CLI: {e}")
            raise RuntimeError(f"Claude CLI Connector failure: {e}") from e


class MockConnector(BaseLLMConnector):
    def __init__(self, portfolio_type: str = "json"):
        self.portfolio_type = portfolio_type

    def execute_prompt(self, system_prompt: str, user_content: str) -> str:
        logger.info("Executing prompt via Mock LLM Connector.")
        
        # Parse user content to extract repo info for mock output
        # Usually user_content will contain the existing file contents and the new project metadata
        # Let's try to extract new repo info if it is passed in user_content
        # For mock purposes, we return a simulated success payload
        if self.portfolio_type == "json":
            # Let's return a mock updated JSON list
            try:
                # We expect the user content to contain the original JSON, let's try to parse it
                # If we find existing JSON in the prompt, let's try to append a mock project
                import re
                parsed = None
                existing_data = []
                # Find content between ```json and ```
                json_blocks = re.findall(r"```json\s*([\s\S]*?)\s*```", user_content)
                if json_blocks:
                    try:
                        parsed = json.loads(json_blocks[0])
                        if isinstance(parsed, list):
                            existing_data = parsed
                        elif isinstance(parsed, dict) and "projects" in parsed:
                            existing_data = parsed["projects"]
                    except Exception as e:
                        logger.warning(f"Failed to parse json block in mock: {e}")
                
                # Mock new project metadata
                mock_project = {
                    "name": "AutoSyncAgent",
                    "description": "An automated portfolio syncer that extracts metadata and syncs it to github.",
                    "url": "https://github.com/mockuser/AutoSyncAgent",
                    "languages": ["Python", "HTML"],
                    "date": "2026-06"
                }
                
                updated_projects = [mock_project] + existing_data
                if parsed and isinstance(parsed, dict) and "projects" in parsed:
                    return json.dumps({"projects": updated_projects}, indent=2)
                return json.dumps(updated_projects, indent=2)
            except Exception as e:
                logger.warning(f"Mock JSON generation failed, returning hardcoded mock: {e}")
                return json.dumps([
                    {
                        "name": "AutoSyncAgent",
                        "description": "An automated portfolio syncer that extracts metadata and syncs it to github.",
                        "url": "https://github.com/mockuser/AutoSyncAgent",
                        "languages": ["Python"],
                        "date": "2026-06"
                    }
                ], indent=2)
        else:
            # Markdown update mock
            mock_item = "\n- **[AutoSyncAgent](https://github.com/mockuser/AutoSyncAgent)**: An automated portfolio syncer that extracts metadata and syncs it to github. (Python)\n"
            return f"# Projects\n{mock_item}\n{user_content[:200]}..."


def get_llm_connector(config: Config) -> BaseLLMConnector:
    """Factory to retrieve the appropriate LLM connector instance."""
    provider = config.llm_provider
    if provider == "openai":
        response_json = (config.portfolio_structure_type == "json")
        return OpenAIConnector(
            api_key=config.openai_api_key,
            model=config.openai_model,
            response_json=response_json
        )
    elif provider == "claude_cli":
        return ClaudeCliConnector(cli_command=config.claude_cli_command)
    elif provider == "mock":
        return MockConnector(portfolio_type=config.portfolio_structure_type)
    else:
        logger.warning(f"Unknown LLM provider '{provider}', falling back to mock.")
        return MockConnector(portfolio_type=config.portfolio_structure_type)
