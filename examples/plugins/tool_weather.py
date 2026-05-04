"""
Example custom tool plugin.

This file demonstrates how to create a custom tool that can be
dynamically loaded by NanoAgent's plugin system.

To use this plugin, add to your config.yaml:

plugins:
  files:
    - examples/plugins/tool_weather.py
"""

from nano_agent.tools.base import BaseTool, ToolResult


class WeatherTool(BaseTool):
    """Get weather information for a city."""

    name = "get_weather"
    description = "Get current weather information for a specified city. Use this when the user asks about weather."

    @property
    def parameters_schema(self):
        return {
            "type": "object",
            "properties": {
                "city": {
                    "type": "string",
                    "description": "City name (e.g., Beijing, Shanghai, New York)"
                }
            },
            "required": ["city"]
        }

    def execute(self, city: str) -> ToolResult:
        """
        Execute weather lookup.

        In a real implementation, this would call a weather API.
        This example returns mock data.
        """
        # Mock weather data
        weather_data = {
            "beijing": "晴，温度 25°C，空气质量良好",
            "shanghai": "多云，温度 28°C",
            "guangzhou": "小雨，温度 30°C",
            "new york": "Sunny, 72°F",
            "london": "Cloudy, 15°C",
        }

        city_lower = city.lower()
        if city_lower in weather_data:
            return ToolResult(
                success=True,
                output=f"{city} 天气：{weather_data[city_lower]}"
            )
        else:
            return ToolResult(
                success=True,
                output=f"未找到 {city} 的天气信息。可用城市：北京、上海、广州、纽约、伦敦"
            )


class TimeTool(BaseTool):
    """Get current time."""

    name = "get_time"
    description = "Get current date and time. Use this when the user asks about the current time."

    @property
    def parameters_schema(self):
        return {
            "type": "object",
            "properties": {}
        }

    def execute(self) -> ToolResult:
        """Get current time."""
        from datetime import datetime
        now = datetime.now()
        return ToolResult(
            success=True,
            output=f"当前时间：{now.strftime('%Y-%m-%d %H:%M:%S')}"
        )