"""Channel adapters."""

from .base import ChannelAdapter
from .cli import CLIChannel
from .discord_ import DiscordChannel
from .email import EmailChannel
from .slack import SlackChannel
from .telegram import TelegramChannel
from .whatsapp import WhatsAppChannel

__all__ = [
    "ChannelAdapter",
    "CLIChannel",
    "TelegramChannel",
    "DiscordChannel",
    "SlackChannel",
    "WhatsAppChannel",
    "EmailChannel",
]
