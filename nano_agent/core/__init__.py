"""
Core module - shared infrastructure for NanoAgent.
"""

from .registry import BaseRegistry

# AgentBuilder is imported lazily to avoid circular imports
# Use: from nano_agent.core.builder import AgentBuilder

__all__ = ["BaseRegistry"]
