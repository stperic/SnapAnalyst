"""
Command Handlers Package

Only /clear remains as a slash command.
All other functionality is accessed via the Settings toolbar button.
"""

from .router import handle_command

__all__ = ["handle_command"]
