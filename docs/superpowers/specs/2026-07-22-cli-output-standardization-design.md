# CLI 输出标准化与展示层重构

## 目标

将分散在 `main.py` 中的输出函数抽出为独立的 `displays.py`，统一所有 slash 命令的输出格式、语言和样式，并增强 `Console` 类的高阶格式化方法。

## 架构

```
main.py
  │  import { _show_*, _get_display_width, _pad_to_width }
  │         ↓
displays.py     ← 所有 _show_* 函数集中于此
  │
  │  import Console
  │         ↓
console.py      ← Console 类（新增 print_title / print_subtitle / print_end / print_kv）
```

### 文件职责

| 文件 | 职责 | 预估行数 |
|------|------|----------|
| `cli/console.py` | Console 底层格式化工具 + 新增高阶方法 | ~120 |
| `cli/displays.py` | 所有 `_show_*` 展示函数（NEW） | ~600 |
| `cli/main.py` | 命令处理 + 事件循环，保留 `_handle_*` | ~3100（-600） |

## Console 类增强

### 新增方法

```python
@classmethod
def print_title(cls, title: str) -> None:
    """标准标题块"""
    print()
    print("=" * 50)
    print(title)
    print("=" * 50)

@classmethod
def print_subtitle(cls, title: str) -> None:
    """标准小标题"""
    print(f"\n## {title}")

@classmethod
def print_end(cls) -> None:
    """标准结尾分隔线"""
    print("\n" + "=" * 50 + "\n")

@classmethod
def print_kv(cls, key: str, value: str, key_width: int = 12, indent: int = 0) -> None:
    """对齐 key-value 行

    Args:
        key: 键名（可包含 ":"，如 "工具定义:"）
        value: 值字符串
        key_width: 键区域显示宽度（含缩进）
        indent: 额外缩进空格数
    """
    prefix = " " * indent
    padding = key_width - _get_display_width(key) - indent
    print(f"{prefix}{key}{' ' * padding} {value}")

@classmethod
def print_progress_bar(cls, pct: float, width: int = 40) -> None:
    """标准进度条，用 █ 填充 + · 表示剩余

    例如：
      [████████████························] 45.0%
        · 剩余: 55.0%
    """
    filled = int(pct / 100 * width)
    bar = "█" * filled + "·" * (width - filled)
    print(f"  [{bar}] {pct:.1f}%")
```

### 保留当前格式的输出形式

以下形式保持不动（已有独立实现且使用范围有限）：
- **表格**（`_show_context_composition`、`_show_iteration_breakdown` 中的多列表格）
- **紧凑行**（`_show_run_stats` 中单行统计摘要）

### 覆盖范围验证

| 形式 | 覆盖方法 | 适用于 |
|------|----------|--------|
| 标题块 | `print_title()` | 所有 `_show_*` 的开头 |
| 小标题 | `print_subtitle()` | 各 section 分隔 |
| 结尾线 | `print_end()` | 所有 `_show_*` 结尾 |
| 对齐列表 | `print_kv()` | 帮助区（indent=0）、设置信息（indent=0）、缩进子项（indent=4）|
| 进度条 | `print_progress_bar()` | `/context` 预算占比 |

### 向后兼容

`print_header()` 保留作为 `print_title()` 的别名，老调用方不报错。

## displays.py

### 迁移的函数

| 函数 | 说明 |
|------|------|
| `_show_help()` | 全面重写，Console.print + 中文 + 统一风格 |
| `_show_run_stats()` | 统一 print → Console.print |
| `_show_monitoring_stats()` | 格式统一 |
| `_show_stats_status()` | 语言统一 + 格式统一 |
| `_show_context_composition()` | 语言统一（脚注 `[*]` → 中文） |
| `_show_context_budget()` | 进度条统一为 print_progress_bar |
| `_show_estimation_audit()` | 格式统一 + 进度条 |
| `_show_iteration_breakdown()` | 进度条统一 |
| `_show_memory_status()` | 格式统一 |
| `_show_session()` | 格式统一 |
| `_show_config()` | 委托 config_display.render_config，不动 |

### 辅助方法

`_get_display_width()`、`_pad_to_width()` — 从 main.py 移入。

### 导入关系

```python
# displays.py
from .console import Console
# _get_display_width, _pad_to_width 现在定义在 displays.py 中
```

## 显示标准

### 1. 标题块

```
==================================================
📊 上下文预算分析
==================================================
```

### 2. 小标题

```
## Token 组成
```

### 3. key-value 对齐列表

```
  工具定义:    -
  系统提示:    -
  总计:        0
```

### 4. 进度条

```
  [████████████████························] 45.0%
    · 剩余: 55.0%
```

### 5. 结尾分隔线

```
==================================================
```

### 6. 输出规范

- 全部使用 `Console.print(style=...)`，不使用裸 `print()`
- 友好提示使用 `style="info"`，成功用 `style="success"`，错误用 `style="error"`，警告用 `style="warning"`
- 语言统一为中文（所有用户可见输出）

## 命令输出统一清单

| 命令 | 当前输出 | 改为 |
|------|----------|------|
| `/tools` | `"Available tools: ..."` | `"可用工具: "` |
| `/sessions` (无) | `"No sessions found."` | `"暂无会话"` |
| `/sessions` (有) | `"Available sessions (N):"` | `"可用会话 (N):"` |
| `/sessions` (不支持) | `"Session listing not available..."` | `"当前记忆类型不支持会话列表"` |
| `/plans` | 检查外部函数输出 | 统一输出到 Console.print |
| `/history` (无) | `"暂无操作历史"` | 已有中文，仅加 style |
| `/history` (未启用) | `"Git 未启用或不在 Git 仓库中"` | 已有中文，仅加 style |
| `/clear` | `"Conversation history cleared"` | `"对话历史已清空"` |
| `/plan` (无参数) | `"用法: /plan <任务描述>"` | 已有中文，改 style |
| `/plan` (执行) | `list_plans()` 等外部输出 | 检查并统一 |
| `/usage` 脚注 | `"[*] 表示按字符长度比例估算"` + `"- 表示该值为 0"` | 已有中文，ok |
| `/context` 进度条 | `█▓▒░` 混合符号 | 统一用 `█` 填充 + `·` 剩余 |
| `/verbose` | 中文 | ok |
| `/effort` | 中文 | ok |
| `/stats` | 中英混杂 | 全部中文 |
| `/undo` | 中文 | ok |
| `/auto` | 中文 | ok |
| `/init` | 中文 | ok |
| `/memory` | 中文 | ok |
| `/config` | 中文（通过 config_display）| ok |
| `/skill` | 英文 mixed | 统一中文 |
| `/setname` | 中文 | ok |
| `/snapshot` | 英文 mixed | 统一中文 |

### 6. 缩进列表（print_kv 加 indent 参数）

```
  - Successful:   xxx
  - Failed:       xxx
```

### 7. 帮助区（print_subtitle + print_kv）

```
## 基本操作
  /exit, /quit     退出（保存摘要）
  /clear           清空对话
```

### 保留现有格式的形式

以下两种形式的显示格式已够用，保持不动：

**表格**（`/usage`、`/stats breakdown`）：
```
  ID    轮次   迭代   工具[*]  系统[*]  ...
  ---  -----  -----  -------  -------  ...
  1    1      1      -        -        ...
```

**紧凑行**（`_show_run_stats`）：
```
📊 本轮: 1234 tokens | 12.34s | LLM调用: 3 | 迭代: 2 | 工具: ✓read*2
```


## 不涉及范围

- `config_display.py` 配置渲染逻辑不动（已独立，格式良好）
- 命令处理逻辑 `_handle_*` 函数不动
- 事件循环结构不动
- 测试不动

## 实施顺序

1. 增强 Console 类（新增 5 个方法）
2. 创建 displays.py，迁移所有 `_show_*` + 辅助函数
3. 更新 main.py 的 import
4. 逐一修改各 `_show_*` 中的输出格式和语言
5. 检查所有 `_handle_*` 中的直接 Console.print 调用（语言统一 + style 统一）
6. 运行测试确保无回归
