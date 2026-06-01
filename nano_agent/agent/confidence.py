"""
Confidence parser for extracting confidence information from LLM responses.

This module provides utilities to parse confidence markers from LLM output
and determine if early stopping is appropriate.
"""

import re
from dataclasses import dataclass


@dataclass
class ConfidenceResult:
    """Result of confidence parsing."""

    confidence: float  # 0.0 - 1.0
    can_answer: bool  # Whether LLM has enough info
    cleaned_response: str  # Response with confidence markers removed
    found_markers: bool  # Whether confidence markers were found


class ConfidenceParser:
    """
    Parser for extracting confidence information from LLM responses.

    Parses confidence markers in the format:
    [CONFIDENCE: X.XX] [CAN_ANSWER: yes/no]
    """

    # Regex patterns for confidence markers
    CONFIDENCE_PATTERN = re.compile(r"\[CONFIDENCE:\s*(-?[0-9.]+)\]", re.IGNORECASE)
    CAN_ANSWER_PATTERN = re.compile(r"\[CAN_ANSWER:\s*(yes|no)\]", re.IGNORECASE)

    def __init__(self, threshold: float = 0.9):
        """
        Initialize confidence parser.

        Args:
            threshold: Confidence threshold for early stopping
        """
        self.threshold = threshold

    def parse(self, response: str) -> ConfidenceResult:
        """
        Parse confidence information from LLM response.

        Args:
            response: LLM response text

        Returns:
            ConfidenceResult with parsed information
        """
        confidence = 1.0  # Default to high confidence
        can_answer = True  # Default to can answer
        found_markers = False

        # Extract confidence
        conf_match = self.CONFIDENCE_PATTERN.search(response)
        if conf_match:
            found_markers = True
            try:
                confidence = float(conf_match.group(1))
                # Clamp to valid range
                confidence = max(0.0, min(1.0, confidence))
            except ValueError:
                confidence = 1.0  # Default on parse error

        # Extract can_answer
        can_match = self.CAN_ANSWER_PATTERN.search(response)
        if can_match:
            found_markers = True
            can_answer = can_match.group(1).lower() == "yes"

        # Clean response by removing confidence markers
        cleaned = self.CONFIDENCE_PATTERN.sub("", response)
        cleaned = self.CAN_ANSWER_PATTERN.sub("", cleaned)
        # Clean up extra whitespace but preserve newlines
        # Only collapse multiple spaces on the same line
        lines = cleaned.split("\n")
        cleaned_lines = [re.sub(r"[ \t]+", " ", line).strip() for line in lines]
        cleaned = "\n".join(cleaned_lines).strip()

        return ConfidenceResult(
            confidence=confidence,
            can_answer=can_answer,
            cleaned_response=cleaned,
            found_markers=found_markers,
        )

    def should_stop_early(self, response: str) -> tuple[bool, ConfidenceResult]:
        """
        Determine if early stopping is appropriate.

        Args:
            response: LLM response text

        Returns:
            Tuple of (should_stop, confidence_result)
        """
        result = self.parse(response)

        # Early stop if confidence >= threshold AND can_answer is True
        should_stop = result.confidence >= self.threshold and result.can_answer

        return should_stop, result
