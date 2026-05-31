"""
Query prejudgment mechanism for token efficiency.

This module provides a lightweight LLM-based query complexity classifier
that supplements the rule-based QueryRouter. It uses a minimal prompt
(~50 tokens) to classify queries that the router cannot confidently
categorize, enabling simple questions to be answered directly without
entering the full ReAct loop.
"""

import re
from dataclasses import dataclass

from .router import QueryComplexity


@dataclass
class PrejudgmentResult:
    """Result of query prejudgment."""

    complexity: QueryComplexity
    answer: str | None  # LLM-generated answer when SIMPLE
    prejudgment_tokens: int  # Tokens consumed by prejudgment LLM call
    reason: str  # Classification reason for logging


class QueryPrejudgment:
    """
    LLM-based query complexity prejudgment.

    Uses a minimal prompt (~50 tokens) to classify query complexity
    before entering the ReAct loop. Only activates when the rule-based
    QueryRouter returns COMPLEX as a default (no pattern matched).
    """

    PREJUDGMENT_PROMPT = (
        "Classify this query's complexity. "
        "Reply with ONLY: [COMPLEXITY: simple/moderate/complex]\n"
        "- simple: greetings, thanks, factual Q&A, no tools needed. "
        "Then answer briefly.\n"
        "- moderate: single tool call likely sufficient\n"
        "- complex: multi-step reasoning, multiple tools, code changes\n\n"
        "Query: {query}"
    )

    COMPLEXITY_PATTERN = re.compile(
        r"\[COMPLEXITY:\s*(simple|moderate|complex)\]", re.IGNORECASE
    )

    COMPLEXITY_MAP = {
        "simple": QueryComplexity.SIMPLE,
        "moderate": QueryComplexity.MODERATE,
        "complex": QueryComplexity.COMPLEX,
    }

    def __init__(
        self,
        llm=None,
        simple_prompt: str = "",
        max_answer_tokens: int = 300,
    ):
        """
        Initialize query prejudgment.

        Args:
            llm: LLM instance for classification. If None, prejudge()
                 always returns COMPLEX fallback.
            simple_prompt: Optional custom system prompt for SIMPLE responses.
            max_answer_tokens: Max tokens for SIMPLE direct answer.
        """
        self.llm = llm
        self.simple_prompt = simple_prompt
        self.max_answer_tokens = max_answer_tokens

    def prejudge(self, query: str) -> PrejudgmentResult:
        """
        Prejudge query complexity using a lightweight LLM call.

        Args:
            query: User's input query

        Returns:
            PrejudgmentResult with complexity classification and
            optional answer (for SIMPLE queries).
        """
        if self.llm is None:
            return PrejudgmentResult(
                complexity=QueryComplexity.COMPLEX,
                answer=None,
                prejudgment_tokens=0,
                reason="LLM not available",
            )

        messages = [
            {"role": "user", "content": self.PREJUDGMENT_PROMPT.format(query=query)},
        ]

        try:
            response_text, _, usage = self.llm.chat(
                messages=messages,
                tools=None,
                system_stable=None,
            )
        except Exception as e:
            return PrejudgmentResult(
                complexity=QueryComplexity.COMPLEX,
                answer=None,
                prejudgment_tokens=0,
                reason=f"LLM call failed: {e}",
            )

        complexity, answer = self._parse_response(response_text)

        return PrejudgmentResult(
            complexity=complexity,
            answer=answer,
            prejudgment_tokens=usage.total_tokens if usage else 0,
            reason=f"Parsed from LLM response",
        )

    def _parse_response(
        self, response: str
    ) -> tuple[QueryComplexity, str | None]:
        """
        Parse complexity marker and optional answer from LLM response.

        Args:
            response: Raw LLM response text

        Returns:
            Tuple of (complexity, answer). Answer is None unless SIMPLE.
        """
        match = self.COMPLEXITY_PATTERN.search(response)
        if not match:
            return QueryComplexity.COMPLEX, None

        complexity_str = match.group(1).lower()
        complexity = self.COMPLEXITY_MAP.get(
            complexity_str, QueryComplexity.COMPLEX
        )

        # For SIMPLE queries, extract the answer after the marker
        answer = None
        if complexity == QueryComplexity.SIMPLE:
            after_marker = response[match.end():].strip()
            if after_marker:
                answer = after_marker

        return complexity, answer
