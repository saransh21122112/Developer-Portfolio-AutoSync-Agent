import os
import logging
import requests
from dataclasses import dataclass, field
from typing import List, Dict

logger = logging.getLogger(__name__)

@dataclass
class ProjectPublished:
    name: str
    description: str
    url: str
    languages: List[str] = field(default_factory=list)
    date: str = ""


class BaseDispatcherPlugin:
    def on_publish(self, event: ProjectPublished):
        """Hook called when a new project is successfully synced."""
        pass


class LinkedInConnector(BaseDispatcherPlugin):
    def on_publish(self, event: ProjectPublished):
        logger.info("LinkedInConnector triggered.")
        # Draft a LinkedIn post
        hashtags = " ".join([f"#{lang.lower()}" for lang in event.languages[:3]])
        post_draft = (
            f"🚀 Excited to announce that I have published a new project: **{event.name}**!\n\n"
            f"{event.description}\n\n"
            f"🔗 Check out the project repository: {event.url}\n\n"
            f"Built with: {', '.join(event.languages)}\n\n"
            f"{hashtags} #portfolio #developer #softwareengineer"
        )
        logger.info(f"Drafted LinkedIn Post for project '{event.name}':\n"
                    f"----------------------------------------\n"
                    f"{post_draft}\n"
                    f"----------------------------------------")
        # In a real integration, we would POST to the LinkedIn API here.
        # But this acts as a robust hook.


class DiscordWebhookConnector(BaseDispatcherPlugin):
    def __init__(self, webhook_url: str = None):
        self.webhook_url = webhook_url or os.getenv("DISCORD_WEBHOOK_URL", "")

    def on_publish(self, event: ProjectPublished):
        logger.info("DiscordWebhookConnector triggered.")
        if not self.webhook_url or "placeholder" in self.webhook_url:
            logger.warning("Discord webhook URL not configured. Skipping Discord notification.")
            return

        payload = {
            "content": "🚀 **New Project Added to Portfolio!**",
            "embeds": [
                {
                    "title": event.name,
                    "description": event.description,
                    "url": event.url,
                    "color": 3447003,  # Soft blue color
                    "fields": [
                        {
                            "name": "Technologies 🛠️",
                            "value": ", ".join(event.languages) if event.languages else "N/A",
                            "inline": True
                        },
                        {
                            "name": "Release Date 📅",
                            "value": event.date or "N/A",
                            "inline": True
                        }
                    ],
                    "footer": {
                        "text": "Automated via PortfolioSyncAgent"
                    }
                }
            ]
        }

        try:
            response = requests.post(self.webhook_url, json=payload, timeout=10)
            if response.status_code in (200, 204):
                logger.info(f"Successfully sent Discord notification for project '{event.name}'.")
            else:
                logger.error(f"Failed to send Discord webhook: HTTP {response.status_code} - {response.text}")
        except Exception as e:
            logger.error(f"Error firing Discord webhook: {e}")


class EventDispatcher:
    def __init__(self):
        self._listeners: List[BaseDispatcherPlugin] = []

    def register(self, listener: BaseDispatcherPlugin):
        """Registers an event listener plugin."""
        self._listeners.append(listener)
        logger.info(f"Registered plugin listener: {listener.__class__.__name__}")

    def dispatch(self, event: ProjectPublished):
        """Dispatches an event to all registered listener plugins."""
        logger.info(f"Dispatching ProjectPublished event for '{event.name}'...")
        for listener in self._listeners:
            try:
                listener.on_publish(event)
            except Exception as e:
                logger.error(f"Error running dispatcher plugin {listener.__class__.__name__}: {e}")
