"""
Budget management for agent execution.

This module provides multi-dimensional budget constraints to prevent
runaway execution in terms of iterations, tokens, and tool calls.
"""

from dataclasses import dataclass


@dataclass
class Budget:
    """
    Budget constraints for execution.

    Defines limits on various dimensions of execution to prevent
    runaway behavior and control costs.
    """

    max_iterations: int = 10
    max_tokens: int = 100000
    max_tool_calls: int = 50


class BudgetChecker:
    """
    Budget checker - enforces multi-dimensional constraints.

    This class checks whether execution can continue based on
    current resource consumption against defined budget limits.
    """

    def __init__(self, budget: Budget):
        """
        Initialize the budget checker.

        Args:
            budget: The budget constraints to enforce
        """
        self.budget = budget

    def can_continue(self, iterations: int, tokens_used: int, tool_calls: int) -> bool:
        """
        Check if execution can continue.

        Args:
            iterations: Current iteration count
            tokens_used: Total tokens consumed
            tool_calls: Total tool calls made

        Returns:
            True if all dimensions are within budget, False otherwise
        """
        return (
            iterations < self.budget.max_iterations
            and tokens_used < self.budget.max_tokens
            and tool_calls < self.budget.max_tool_calls
        )

    def check_iterations(self, iterations: int) -> bool:
        """Check if iteration count is within budget."""
        return iterations < self.budget.max_iterations

    def check_tokens(self, tokens_used: int) -> bool:
        """Check if token usage is within budget."""
        return tokens_used < self.budget.max_tokens

    def check_tool_calls(self, tool_calls: int) -> bool:
        """Check if tool call count is within budget."""
        return tool_calls < self.budget.max_tool_calls
