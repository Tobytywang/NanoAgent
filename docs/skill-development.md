# 技能包开发指南

本文档介绍如何为 NanoAgent 开发自定义技能包（Skill）。

## 什么是技能包？

技能包是 NanoAgent 的扩展机制，允许你为 Agent 添加：

- **专属工具**：自定义的 Tool 实现
- **系统提示**：特定领域的指令和知识
- **知识库**：结构化的知识数据

## 快速开始

### 创建一个简单的 YAML 技能包

在 `.nano_agent/skills/` 目录下创建 `my_skill.yaml`：

```yaml
name: my_skill
description: My custom skill
system_prompt: |
  You are a specialized assistant for my domain.
  Follow these rules when responding:
  1. Always be concise
  2. Provide code examples when relevant
enabled: true
```

重启 Agent 后，这个技能包会自动加载。

### 创建 Python 技能包

对于需要自定义工具的场景，创建 Python 技能包：

```python
# my_skill.py
from nano_agent.skills.base import BaseSkill
from nano_agent.tools.base import BaseTool, ToolResult

class MyTool(BaseTool):
    """自定义工具"""

    name = "my_tool"
    description = "A custom tool for specific tasks"

    @property
    def parameters_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "input": {
                    "type": "string",
                    "description": "Input to process"
                }
            },
            "required": ["input"]
        }

    def execute(self, input: str) -> ToolResult:
        # 实现你的逻辑
        result = f"Processed: {input}"
        return ToolResult(success=True, output=result)


class Skill(BaseSkill):
    """自定义技能包"""

    name = "my_skill"
    description = "A custom skill with tools"

    @property
    def system_prompt(self) -> str:
        return "You are a specialized assistant with custom tools."

    @property
    def tools(self) -> list[BaseTool]:
        return [MyTool()]

    def setup(self, config: dict | None = None) -> None:
        """初始化钩子"""
        print(f"Setting up {self.name}")

    def teardown(self) -> None:
        """清理钩子"""
        print(f"Tearing down {self.name}")
```

## 技能包类型

### YAML 技能包

适用于简单配置场景，只包含系统提示和工具引用：

```yaml
name: coding
description: Code assistant skill
system_prompt: |
  You are a coding assistant.
  Help users write, review, and debug code.
tools:
  - code_review
  - test_runner
knowledge:
  - topic: python
    content: "Python best practices..."
enabled: true
```

### Python 技能包

适用于需要复杂逻辑的场景：

- 自定义工具实现
- 初始化/清理逻辑
- 动态配置

## API 参考

### BaseSkill

技能包抽象基类：

```python
class BaseSkill(ABC):
    name: str                    # 技能包名称（必需）
    description: str = ""        # 描述
    enabled: bool = True         # 是否启用

    @property
    def system_prompt(self) -> str | None:
        """系统提示（可选）"""
        return None

    @property
    def tools(self) -> list[BaseTool]:
        """提供的工具列表"""
        return []

    @property
    def knowledge(self) -> list[dict]:
        """知识库"""
        return []

    def setup(self, config: dict | None = None) -> None:
        """初始化钩子"""
        pass

    def teardown(self) -> None:
        """清理钩子"""
        pass
```

### SkillDefinition

从 YAML 加载的技能包定义：

```python
@dataclass
class SkillDefinition:
    name: str
    description: str = ""
    system_prompt: str | None = None
    tools: list[str] = field(default_factory=list)
    knowledge: list[dict] = field(default_factory=list)
    enabled: bool = True
    config: dict = field(default_factory=dict)
```

### SkillRegistry

技能包注册表：

```python
class SkillRegistry:
    def register(self, skill: BaseSkill) -> None:
        """注册技能包"""

    def unregister(self, name: str) -> bool:
        """注销技能包"""

    def get(self, name: str) -> BaseSkill | None:
        """获取技能包"""

    def get_active_skills(self) -> list[BaseSkill]:
        """获取所有启用的技能包"""

    def get_all_tools(self) -> list[BaseTool]:
        """获取所有工具"""

    def get_combined_system_prompt(self) -> str:
        """获取合并后的系统提示"""
```

### SkillLoader

技能包加载器：

```python
class SkillLoader:
    def load_from_yaml(self, yaml_path: str | Path) -> SkillDefinition | None:
        """从 YAML 文件加载"""

    def load_from_directory(self, directory: str | Path) -> list[SkillDefinition]:
        """从目录加载所有技能包"""

    def load_skill_class(self, module_path: str, class_name: str = "Skill") -> BaseSkill | None:
        """动态加载 Python 技能包类"""

    def reload_skill(self, name: str) -> bool:
        """热重载技能包"""

    def unload_skill(self, name: str) -> bool:
        """卸载技能包"""

    def list_loaded_skills(self) -> list[str]:
        """列出已加载的技能包"""
```

## 工具开发

### BaseTool

所有工具必须继承 `BaseTool`：

```python
from nano_agent.tools.base import BaseTool, ToolResult

class MyTool(BaseTool):
    name = "my_tool"
    description = "Tool description"

    @property
    def parameters_schema(self) -> dict:
        """JSON Schema 格式的参数定义"""
        return {
            "type": "object",
            "properties": {
                "param1": {"type": "string", "description": "参数1"},
                "param2": {"type": "integer", "description": "参数2"}
            },
            "required": ["param1"]
        }

    def execute(self, param1: str, param2: int = 0) -> ToolResult:
        """执行工具逻辑"""
        try:
            # 你的实现
            result = do_something(param1, param2)
            return ToolResult(success=True, output=result)
        except Exception as e:
            return ToolResult(success=False, error=str(e))
```

### ToolResult

工具执行结果：

```python
@dataclass
class ToolResult:
    success: bool          # 是否成功
    output: str = ""       # 输出内容
    error: str = ""        # 错误信息
```

## 热加载

在 Agent 运行时，可以使用 CLI 命令管理技能包：

```
skills                    # 列出已加载的技能包
skill reload <name>       # 重载指定技能包
skill unload <name>       # 卸载指定技能包
```

热加载流程：

1. 从注册表注销旧技能包
2. 重新从源文件加载
3. 注册新技能包
4. 更新 Agent 的工具和系统提示

## 配置

在 `.nano_agent/config.yaml` 中配置技能包：

```yaml
skills:
  enabled:
    - coding
    - translation
  directory: .nano_agent/skills
```

## 最佳实践

### 1. 单一职责

每个技能包应该专注于一个领域：

```python
# 好的做法
class CodeReviewSkill(BaseSkill):
    name = "code_review"
    # 只处理代码审查相关功能

# 避免的做法
class EverythingSkill(BaseSkill):
    name = "everything"
    # 混合多个不相关的功能
```

### 2. 清晰的系统提示

提供明确的指令：

```python
@property
def system_prompt(self) -> str:
    return """
You are a code review assistant.

Your responsibilities:
1. Review code for bugs and issues
2. Suggest improvements
3. Check for best practices

Output format:
- Use markdown for code blocks
- List issues by severity
"""
```

### 3. 错误处理

工具执行时正确处理错误：

```python
def execute(self, path: str) -> ToolResult:
    if not os.path.exists(path):
        return ToolResult(success=False, error=f"File not found: {path}")

    try:
        content = read_file(path)
        return ToolResult(success=True, output=content)
    except Exception as e:
        return ToolResult(success=False, error=str(e))
```

### 4. 使用 setup/teardown

进行初始化和清理：

```python
class DatabaseSkill(BaseSkill):
    def setup(self, config: dict | None = None) -> None:
        self.connection = connect_db(config.get("db_url"))

    def teardown(self) -> None:
        if self.connection:
            self.connection.close()
```

## 示例

查看 `examples/skills/` 目录获取完整示例：

- `coding.yaml` - YAML 技能包示例
- `translation.py` - Python 技能包示例
