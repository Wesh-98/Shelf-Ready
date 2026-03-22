"""
ShelfReady Agents Package

Collection of specialized agents for image processing tasks.
"""

# Import Check-Pic agent for easy access
try:
    from .check_pic import CheckPicAgent, CheckPicConfig, QCResult
except ImportError:
    pass  # Agent may not be fully installed

__all__ = ['CheckPicAgent', 'CheckPicConfig', 'QCResult']
