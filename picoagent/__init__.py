"""picoagent package."""

from . import hooks
from .config import AgentConfig

__version__ = "0.2.0"
__all__ = ["AgentConfig", "hooks", "__version__"]
