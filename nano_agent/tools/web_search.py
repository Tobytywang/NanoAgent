"""
Web search tool using curl and Bing search engine.
"""

import subprocess
import urllib.parse
from .base import BaseTool, ToolResult


class WebSearchTool(BaseTool):
    """Web search tool for retrieving current information from the internet."""

    name = "web_search"
    description = "Search the web for current information. Use this when you need up-to-date information about news, weather, facts, or any topic that requires real-time data."

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
                    "description": "The search query (e.g., 'Python latest version', '今天北京天气')"
                }
            },
            "required": ["query"]
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
            "curl", "-s", "-L",
            "--max-time", str(self._timeout),
            "-H", "User-Agent: Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            search_url
        ]

        try:
            result = subprocess.run(
                curl_cmd,
                capture_output=True,
                text=True,
                timeout=self._timeout + 5
            )

            if result.returncode != 0:
                return ToolResult(
                    success=False,
                    error=f"Search request failed: {result.stderr}"
                )

            # Parse the HTML to extract search results
            output = self._parse_search_results(result.stdout)

            if not output:
                return ToolResult(
                    success=True,
                    output=f"Search completed but no clear results found. The search was for: {query}"
                )

            return ToolResult(
                success=True,
                output=output
            )

        except subprocess.TimeoutExpired:
            return ToolResult(
                success=False,
                error=f"Search request timed out after {self._timeout} seconds"
            )
        except Exception as e:
            return ToolResult(
                success=False,
                error=f"Search failed: {str(e)}"
            )

    def _parse_search_results(self, html: str) -> str:
        """
        Parse HTML to extract search results.

        Args:
            html: The HTML response from the search engine

        Returns:
            Extracted text from search results
        """
        import re

        results = []

        # Extract results from <li class="b_algo"> elements (Bing format)
        # Pattern to match result containers
        algo_pattern = r'<li class="b_algo"[^>]*>(.*?)</li>'
        algo_matches = re.findall(algo_pattern, html, re.DOTALL | re.IGNORECASE)

        for match in algo_matches[:5]:  # Limit to top 5 results
            # Extract title
            title_pattern = r'<h2[^>]*><a[^>]*>(.*?)</a></h2>'
            title_match = re.search(title_pattern, match, re.DOTALL | re.IGNORECASE)
            title = self._clean_html(title_match.group(1)) if title_match else ""

            # Extract snippet/description
            desc_pattern = r'<p[^>]*>(.*?)</p>|<span class="news_dt"[^>]*>.*?</span>\s*([^.]+\.)'
            desc_match = re.search(desc_pattern, match, re.DOTALL | re.IGNORECASE)
            description = self._clean_html(desc_match.group(1) or desc_match.group(2)) if desc_match else ""

            # Extract URL
            url_pattern = r'<cite[^>]*>(.*?)</cite>'
            url_match = re.search(url_pattern, match, re.DOTALL | re.IGNORECASE)
            url = self._clean_html(url_match.group(1)) if url_match else ""

            if title or description:
                result_text = f"【{title}】"
                if description:
                    result_text += f"\n{description}"
                if url:
                    result_text += f"\n来源: {url}"
                results.append(result_text)

        # Fallback: try to extract any meaningful text
        if not results:
            # Remove scripts and styles
            clean_html = re.sub(r'<(script|style)[^>]*>.*?</\1>', '', html, flags=re.DOTALL | re.IGNORECASE)
            # Extract text from common result patterns
            text = re.sub(r'<[^>]+>', ' ', clean_html)
            text = re.sub(r'\s+', ' ', text).strip()

            # Look for meaningful sentences
            sentences = re.findall(r'[^\s.!?]{20,}[.!?]', text)
            if sentences:
                results = sentences[:5]

        return "\n\n".join(results) if results else ""

    def _clean_html(self, text: str) -> str:
        """Remove HTML tags and clean up text."""
        import re
        # Remove HTML tags
        text = re.sub(r'<[^>]+>', '', text)
        # Decode HTML entities
        text = text.replace("&amp;", "&")
        text = text.replace("&lt;", "<")
        text = text.replace("&gt;", ">")
        text = text.replace("&quot;", '"')
        text = text.replace("&#39;", "'")
        text = text.replace("&nbsp;", " ")
        # Clean up whitespace
        text = re.sub(r'\s+', ' ', text).strip()
        return text