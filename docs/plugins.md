# 插件开发指南

NanoAgent 支持通过插件机制动态加载外部工具，无需修改框架代码。

## 快速开始

### 1. 创建工具文件

创建一个 Python 文件，定义你的工具类：

```python
# my_tools.py
from nano_agent.tools.base import BaseTool, ToolResult

class MyCustomTool(BaseTool):
    name = "my_tool"
    description = "我的自定义工具"

    @property
    def parameters_schema(self):
        return {
            "type": "object",
            "properties": {
                "input": {"type": "string"}
            },
            "required": ["input"]
        }

    def execute(self, input: str) -> ToolResult:
        result = f"处理结果: {input}"
        return ToolResult(success=True, output=result)
```

### 2. 配置加载

在 `config.yaml` 中添加插件配置：

```yaml
plugins:
  # 从文件加载
  files:
    - /path/to/my_tools.py

  # 从目录加载（自动加载 tool_*.py 文件）
  directories:
    - .nano_agent/plugins

  # 从 Python 模块加载
  modules:
    - my_package.tools
```

## 加载方式

### 从文件加载

```yaml
plugins:
  files:
    - /absolute/path/to/tools.py
    - ./relative/path/tools.py
```

### 从目录加载

目录中的文件需要遵循命名规范 `tool_*.py`：

```yaml
plugins:
  directories:
    - .nano_agent/plugins
```

目录结构：
```
.nano_agent/plugins/
├── tool_weather.py    # 会被自动加载
├── tool_calendar.py   # 会被自动加载
└── helper.py          # 不会被加载（不匹配 tool_*.py）
```

### 从模块加载

```yaml
plugins:
  modules:
    - my_package.tools
    - another_package.custom_tools
```

## 工具开发规范

### 必须实现的内容

1. **继承 `BaseTool`**
2. **定义 `name` 属性** - 工具唯一标识
3. **定义 `description` 属性** - 工具描述（Agent 会根据此判断何时使用）
4. **定义 `parameters_schema` 属性** - 参数 JSON Schema
5. **实现 `execute` 方法** - 工具逻辑

### 示例模板

```python
from nano_agent.tools.base import BaseTool, ToolResult

class ExampleTool(BaseTool):
    # 工具名称（必须唯一）
    name = "example_tool"

    # 工具描述（Agent 根据此判断何时使用）
    description = "示例工具，用于演示插件开发。当用户需要示例时使用。"

    @property
    def parameters_schema(self):
        """参数定义（JSON Schema 格式）"""
        return {
            "type": "object",
            "properties": {
                "param1": {
                    "type": "string",
                    "description": "第一个参数"
                },
                "param2": {
                    "type": "integer",
                    "description": "第二个参数（可选）",
                    "default": 10
                }
            },
            "required": ["param1"]
        }

    def execute(self, param1: str, param2: int = 10) -> ToolResult:
        """
        执行工具逻辑

        Args:
            param1: 必需参数
            param2: 可选参数

        Returns:
            ToolResult: 执行结果
        """
        try:
            # 实现你的逻辑
            result = f"处理 {param1}，参数2={param2}"

            return ToolResult(
                success=True,
                output=result
            )
        except Exception as e:
            return ToolResult(
                success=False,
                error=str(e)
            )
```

## 代码中使用

```python
from nano_agent.tools import PluginLoader, ToolRegistry

# 创建注册表和加载器
registry = ToolRegistry()
loader = PluginLoader(registry)

# 从文件加载
tools = loader.load_from_file("my_tools.py")
print(f"加载了 {len(tools)} 个工具")

# 从目录加载
tools = loader.load_from_directory(".nano_agent/plugins")

# 从模块加载
tools = loader.load_from_module("my_package.tools")

# 查看已加载的工具
for tool_name, source in loader.list_loaded_plugins().items():
    print(f"{tool_name} <- {source}")

# 卸载工具
loader.unload_tool("my_tool")
```

## 最佳实践

### 1. 文件命名

- 使用 `tool_*.py` 前缀，便于目录自动加载
- 一个文件可以定义多个工具类

### 2. 错误处理

始终返回 `ToolResult`，不要抛出异常：

```python
def execute(self, path: str) -> ToolResult:
    try:
        with open(path) as f:
            content = f.read()
        return ToolResult(success=True, output=content)
    except FileNotFoundError:
        return ToolResult(success=False, error=f"文件不存在: {path}")
    except PermissionError:
        return ToolResult(success=False, error=f"无权限: {path}")
```

### 3. 描述清晰

描述决定了 Agent 何时调用工具：

```python
# 好的描述
description = "获取指定城市的实时天气信息。当用户询问天气、气温、降雨等情况时使用。"

# 不好的描述
description = "天气工具"  # 太模糊
```

### 4. 参数验证

使用 JSON Schema 定义参数：

```python
parameters_schema = {
    "type": "object",
    "properties": {
        "city": {
            "type": "string",
            "description": "城市名称",
            "enum": ["北京", "上海", "广州"]  # 可选：限制取值
        },
        "days": {
            "type": "integer",
            "description": "预报天数",
            "minimum": 1,
            "maximum": 7
        }
    },
    "required": ["city"]
}
```

## 示例

查看 `examples/plugins/tool_weather.py` 了解完整示例。