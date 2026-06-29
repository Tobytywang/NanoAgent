"""
Web search tool using curl and Bing search engine.
"""

import subprocess
import urllib.parse
from ..base import BaseTool, ToolResult
from ..standard_output import StandardToolOutput, OutputFormat
from ...core.types import RiskLevel


class WebSearchTool(BaseTool):
    """Web search tool for retrieving current information from the internet."""

    name = "web_search"
    description = "Search the web for current information. Use this when you need up-to-date information about news, weather, facts, or any topic that requires real-time data."
    risk_level = RiskLevel.MODERATE  # Makes external network requests
    can_offload = True
    has_builtin_timeout = True  # Uses subprocess.run(timeout=...)

    def __init__(self, timeout: int = 15):
        """
        Initialize the web search tool.

        Args:
            timeout: Maximum time in seconds for the search request
        """
        self._timeout = timeout

    @property
    def parameters_schema(self):
        return {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "The search query (e.g., 'Python latest version', '今天北京天气')",
                }
            },
            "required": ["query"],
        }

    def execute(self, query: str) -> ToolResult:
        """
        Execute a web search.

        Args:
            query: The search query

        Returns:
            ToolResult with search results
        """
        # Encode the query for URL
        encoded_query = urllib.parse.quote(query, safe="")

        # Build the search URL (Bing China)
        search_url = f"https://cn.bing.com/search?q={encoded_query}"

        # Build curl command
        curl_cmd = [
            "curl",
            "-s",
            "-L",
            "--max-time",
            str(self._timeout),
            "-H",
            "User-Agent: Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            search_url,
        ]

        try:
            result = subprocess.run(
                curl_cmd, capture_output=True, timeout=self._timeout + 5
            )

            if result.returncode != 0:
                return ToolResult(
                    success=False,
                    error=f"Search request failed: {result.stderr.decode('utf-8', errors='replace')}",
                )

            # Decode stdout with error handling for malformed UTF-8
            stdout = result.stdout.decode("utf-8", errors="replace")

            # Parse the HTML to extract search results
            output, structured = self._parse_search_results(stdout)

            if not output:
                return ToolResult(
                    success=True,
                    output=f"Search completed but no clear results found. The search was for: {query}",
                )

            standard_output = StandardToolOutput(
                format=OutputFormat.LIST,
                data={
                    "items": structured,
                    "total": len(structured),
                    "max_display": 5,
                },
                summary=f"Found {len(structured)} results for '{query}'",
            )
            return ToolResult(
                success=True,
                output=output,
                metadata={"standard_output": standard_output},
            )

        except subprocess.TimeoutExpired:
            return ToolResult(
                success=False,
                error=f"Search request timed out after {self._timeout} seconds",
            )
        except Exception as e:
            return ToolResult(success=False, error=f"Search failed: {str(e)}")

    def _parse_search_results(self, html: str) -> tuple[str, list[dict]]:
        """Parse HTML to extract search results.

        Returns:
            (formatted_text, structured_items) tuple
        """
        import re

        results = []
        structured_items = []

        algo_pattern = r'<li class="b_algo"[^>]*>(.*?)</li>'
        algo_matches = re.findall(algo_pattern, html, re.DOTALL | re.IGNORECASE)

        for match in algo_matches[:5]:
            title_pattern = r"<h2[^>]*><a[^>]*>(.*?)</a></h2>"
            title_match = re.search(title_pattern, match, re.DOTALL | re.IGNORECASE)
            title = self._clean_html(title_match.group(1)) if title_match else ""

            desc_pattern = (
                r'<p[^>]*>(.*?)</p>|<span class="news_dt"[^>]*>.*?</span>\s*([^.]+\.)'
            )
            desc_match = re.search(desc_pattern, match, re.DOTALL | re.IGNORECASE)
            description = (
                self._clean_html(desc_match.group(1) or desc_match.group(2))
                if desc_match
                else ""
            )

            url_pattern = r"<cite[^>]*>(.*?)</cite>"
            url_match = re.search(url_pattern, match, re.DOTALL | re.IGNORECASE)
            url = self._clean_html(url_match.group(1)) if url_match else ""

            if title or description:
                result_text = f"【{title}】"
                if description:
                    result_text += f"\n{description}"
                if url:
                    result_text += f"\n来源: {url}"
                results.append(result_text)
                structured_items.append(
                    {"title": title, "snippet": description[:100], "url": url}
                )

        # Fallback
        if not results:
            clean_html_text = re.sub(
                r"<(script|style)[^>]*>.*?</\\1>",
                "",
                html,
                flags=re.DOTALL | re.IGNORECASE,
            )
            text = re.sub(r"<[^>]+>", " ", clean_html_text)
            text = re.sub(r"\s+", " ", text).strip()
            sentences = re.findall(r"[^\s.!?]{20,}[.!?]", text)
            if sentences:
                results = sentences[:5]
                structured_items = [
                    {"title": s[:50], "snippet": s} for s in sentences[:5]
                ]

        formatted = "\n\n".join(results) if results else ""
        return formatted, structured_items

    def _clean_html(self, text: str) -> str:
        """Remove HTML tags and clean up text."""
        import re

        # Remove HTML tags
        text = re.sub(r"<[^>]+>", "", text)
        # Decode HTML entities
        text = text.replace("&amp;", "&")
        text = text.replace("&lt;", "<")
        text = text.replace("&gt;", ">")
        text = text.replace("&quot;", '"')
        text = text.replace("&#39;", "'")
        text = text.replace("&nbsp;", " ")
        # Clean up whitespace
        text = re.sub(r"\s+", " ", text).strip()
        return text
