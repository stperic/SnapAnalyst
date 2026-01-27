"""
Command Handlers Package

Organizes all slash commands into logical modules:
- data_commands: Data loading and file operations
- info_commands: System information and status
- memory_commands: AI memory/ChromaDB management
- utility_commands: Export, samples, notes, etc.
"""

from .router import handle_command

__all__ = ["handle_command"]
