# BUGLIST

> 记录项目中发现的 BUG 及其修复方案，用于复盘和学习。

---

## BUG-001: PersistentMemory 缺失 stable_system_prompt 方法

**发现日期**: 2026-05-19

**严重程度**: 中等（导致程序启动失败）

**影响范围**: 使用 `memory.type: "persistent"` 配置的用户无法启动 nano-agent

### 问题描述

当用户配置使用 `PersistentMemory` 作为工作内存时，程序启动时报错：

```
AttributeError: 'PersistentMemory' object has no attribute 'set_stable_system_prompt'.
Did you mean: 'get_stable_system_prompt'?
```

### 根因分析

在实现 v0.7.7 Prefix Caching 功能时，添加了 `set_stable_system_prompt()` 和 `get_stable_system_prompt()` 方法：

1. ✅ 添加到了 `ShortTermMemory`
2. ✅ 添加到了 `HybridMemory`（委托给 `working_memory`）
3. ❌ **遗漏了 `PersistentMemory`**

`HybridMemory.set_stable_system_prompt()` 会调用 `self.working_memory.set_stable_system_prompt()`，当 `working_memory` 是 `PersistentMemory` 时就会报错。

### 为什么测试没发现

1. `test_prefix_caching.py` 只测试了 `ShortTermMemory` 和 `HybridMemory`（使用 `ShortTermMemory` 作为 working memory）
2. **没有测试 `HybridMemory` 使用 `PersistentMemory` 作为 working memory 的场景**
3. `test_hybrid_memory.py` 中有 `PersistentMemory` 作为 working memory 的测试，但没有测试 `set_stable_system_prompt`

### 修复方案

在 `nano_agent/memory/persistent.py` 中添加：

```python
# 1. 添加属性
stable_system_prompt: str = ""  # 稳定部分（用于 prefix caching）

# 2. 添加方法
def set_stable_system_prompt(self, prompt: str) -> None:
    """设置稳定部分 system prompt（用于 prefix caching）。"""
    self.stable_system_prompt = prompt

def get_stable_system_prompt(self) -> str:
    """获取稳定部分 system prompt（用于 prefix caching）。"""
    return self.stable_system_prompt or self.system_prompt
```

### 补充的测试用例

1. **`test_persistent_memory.py`** - 添加 3 个测试：
   - `test_set_stable_system_prompt`
   - `test_get_stable_system_prompt`
   - `test_stable_system_prompt_persists_across_sessions`

2. **`test_prefix_caching.py`** - 添加 1 个测试：
   - `test_hybrid_memory_with_persistent_memory_stable_system_prompt`（测试触发 bug 的具体场景）

3. **`test_memory_interface.py`** - 新建接口一致性测试文件：
   - 确保所有 `BaseMemory` 子类都实现核心方法
   - 防止类似遗漏再次发生

### 经验教训

1. **接口一致性测试很重要**：当给基类或接口添加新方法时，应确保所有实现类都添加了该方法
2. **测试要覆盖所有组合场景**：`HybridMemory` 可以使用不同的 working memory 类型，测试应覆盖所有组合
3. **考虑在 `BaseMemory` 中定义抽象方法**：让缺少实现的类在实例化时就报错，而不是运行时才发现

### 相关提交

- Commit `84124d8`: 添加 `set_stable_system_prompt` 到 `ShortTermMemory` 和 `HybridMemory`（遗漏 `PersistentMemory`）
- Commit `9447bc2`: 添加 `test_prefix_caching.py`（只测试了 `ShortTermMemory`）

---

## BUG-002: file_search 工具不支持管道分隔的多模式搜索

**发现日期**: 2026-05-19

**严重程度**: 中等（导致搜索结果为空）

**影响范围**: 使用 `file_search` 搜索多个模式时，合并后的搜索无法找到文件

### 问题描述

用户在 TYNote 项目中运行 `nano-agent`，请求"请帮我查看当前项目的plan"。Agent 调用 `file_search` 搜索 `*plan*|*.md|*.txt`，但返回"No files matching found"，而实际上 `.nano_agent/plans/frontmatter-optimization-plan.md` 文件存在。

### 根因分析

`tool_merger.py` 将多个 `file_search` 调用合并为一个，使用 `|` 分隔多个模式：

```python
# tool_merger.py 第 143 行
return "|".join(patterns)  # 生成 "*plan*|*.md|*.txt"
```

但 `file_search` 工具使用 Python 的 `rglob()`，**不支持 `|` 作为模式分隔符**：

```python
# file_ops.py 原代码
matches = base_path.rglob(pattern)  # "*plan*|*.md|*.txt" 无法匹配
```

### 为什么测试没发现

1. `test_tool_merger.py` 测试了合并逻辑，但没有测试合并后的模式是否能被 `file_search` 正确执行
2. 测试用例 `test_complex_pattern_not_simple_extension` 期望使用管道分隔符，但这是错误的设计
3. 缺少端到端测试验证合并后的工具调用能正确工作

### 修复方案

修改 `file_search` 工具，支持 `|` 分隔的多模式搜索：

```python
# nano_agent/tools/builtin/file_ops.py

def execute(self, directory: str, pattern: str, recursive: bool = True) -> ToolResult:
    # Support pipe separator for multiple patterns
    patterns = pattern.split("|") if "|" in pattern else [pattern]

    # Collect matches from all patterns
    all_matches = set()
    for p in patterns:
        p = p.strip()
        if p:
            matches = base_path.rglob(p) if recursive else base_path.glob(p)
            all_matches.update(matches)

    # Sort and return results
    sorted_matches = sorted(all_matches, key=lambda m: str(m))
    ...
```

### 补充的测试用例

**`test_tools.py`** - 添加 2 个测试：
- `test_search_with_pipe_separator`: 测试管道分隔符能正确搜索多个模式
- `test_search_with_pipe_separator_no_matches`: 测试无匹配时的正确行为

**`test_e2e.py`** - 添加 2 个端到端测试（防止回归）：
- `test_file_search_with_merged_patterns`: 验证 `file_search` 支持管道分隔符
- `test_tool_merger_produces_valid_file_search_pattern`: 验证 `ToolCallMerger` 产生的模式能被 `file_search` 正确执行

### 经验教训

1. **工具合并要与工具实现协调**：当 `tool_merger` 产生新的调用格式时，对应的工具必须支持该格式
2. **端到端测试很重要**：单元测试只验证了各模块独立工作，没有验证模块间的协作
3. **测试用例的预期要正确**：`test_complex_pattern_not_simple_extension` 的注释说"should use pipe separator"，但这是基于错误假设

### 相关提交

- Tool merger 逻辑在 `nano_agent/agent/tool_merger.py`
- File search 工具在 `nano_agent/tools/builtin/file_ops.py`

---

## BUG-003: Token 预算默认值过小导致提前终止

**发现日期**: 2026-05-19

**严重程度**: 高（导致 Agent 无法完成正常任务）

**影响范围**: 所有使用默认配置的用户，当对话历史较长时会提前终止

### 问题描述

用户在 TYNote 项目中测试"请帮我查看项目的plan"，Agent 执行了 1 轮迭代后就返回了 "Based on the information gathered..." 的摘要，没有继续读取 plan 文件内容。

### 根因分析

`SmartOptimizationConfig.initial_budget` 默认值为 **2000 tokens**，这个值太小了：

1. 第 1 轮迭代的 `prompt_tokens` 是 2033（包含历史对话）
2. 第 1 轮迭代执行后，预算被消耗：`remaining = 2000 - 2033 = -33`
3. 第 2 轮迭代开始时，`token_budget.should_summarize()` 返回 True
4. 触发 `_force_summarize()`，提前终止执行

### 为什么测试没发现

1. 单元测试没有模拟多轮对话的场景
2. 端到端测试使用的是 mock LLM，返回的 token 数量很小
3. 没有测试验证在正常对话历史下预算是否足够

### 修复方案

将 `initial_budget` 默认值从 2000 调整为 20000：

```python
# nano_agent/config/schema.py
class SmartOptimizationConfig:
    # === Token Budget Management ===
    budget_enabled: bool = True
    initial_budget: int = 20000  # Increased from 2000
    budget_warning_threshold: float = 0.2
    budget_force_summarize: bool = True
```

### 补充的测试用例

**需要添加**：测试验证预算设置在正常对话场景下不会提前终止

### 经验教训

1. **默认值要考虑实际使用场景**：2000 tokens 对于单次 LLM 调用都不够，更不用说多轮对话
2. **预算检查逻辑要合理**：应该在 LLM 调用前检查预算是否足够，而不是在调用后
3. **端到端测试要模拟真实场景**：包括对话历史、token 数量等

### 相关文件

- `nano_agent/config/schema.py` - SmartOptimizationConfig 定义
- `nano_agent/agent/react.py` - 预算检查逻辑
- `nano_agent/agent/token_budget.py` - TokenBudget 实现

---

## BUG-004: ConfidenceParser 将换行符合并为空格

**发现日期**: 2026-05-19

**严重程度**: 中等（导致输出格式混乱）

**影响范围**: 所有使用 confidence marker 的 LLM 响应，多行内容会被合并为单行

### 问题描述

用户在 TYNote 项目测试时，Agent 的 `[Think]` 部分显示正常换行，但最终输出 `>` 部分所有内容被合并到一行。

### 根因分析

`ConfidenceParser.parse()` 方法在清理 confidence markers 后，使用正则表达式清理多余空白：

```python
# 原代码 (第 81-84 行)
cleaned = self.CONFIDENCE_PATTERN.sub("", response)
cleaned = self.CAN_ANSWER_PATTERN.sub("", cleaned)
cleaned = re.sub(r"\s+", " ", cleaned).strip()  # 问题所在！
```

`re.sub(r"\s+", " ", cleaned)` 会将**所有空白字符**（包括换行符 `\n`）替换为单个空格，导致多行内容变成单行。

### 为什么测试没发现

1. `test_smart_optimization.py` 中的测试用例都是单行响应
2. 没有测试验证多行 markdown 格式（标题、列表等）是否被保留
3. 测试关注 confidence 值解析正确性，忽略了格式保留

### 修复方案

修改 `nano_agent/agent/confidence.py`，逐行处理空白，保留换行符：

```python
# 修复后的代码
cleaned = self.CONFIDENCE_PATTERN.sub("", response)
cleaned = self.CAN_ANSWER_PATTERN.sub("", cleaned)
# Clean up extra whitespace but preserve newlines
# Only collapse multiple spaces on the same line
lines = cleaned.split("\n")
cleaned_lines = [re.sub(r"[ \t]+", " ", line).strip() for line in lines]
cleaned = "\n".join(cleaned_lines).strip()
```

### 补充的测试用例

**`test_smart_optimization.py`** - 添加 1 个测试：
- `test_preserves_newlines`: 测试多行 markdown 内容（标题、列表）的换行符被正确保留

### 经验教训

1. **正则表达式要精确**：`\s+` 匹配所有空白包括换行，应使用 `[ \t]+` 只匹配空格和制表符
2. **测试要覆盖格式保留**：不仅测试数据正确性，还要测试格式完整性
3. **用户可见的输出要特别关注**：格式问题直接影响用户体验

### 相关文件

- `nano_agent/agent/confidence.py` - ConfidenceParser 实现
- `tests/test_smart_optimization.py` - 相关测试

---

## BUG-005: TokenBudgetConfig 默认值未同步更新

**发现日期**: 2026-05-20

**严重程度**: 高（导致 Agent 无法完成正常任务）

**影响范围**: 所有使用默认 `TokenBudgetConfig` 的用户，Agent 会提前终止并返回工具摘要而非回答

### 问题描述

用户在 TYNote 项目测试"请帮我查看当前项目的plan"，Agent 执行了 4 轮迭代后返回 "Based on the information gathered..." 的工具摘要，没有给出实际回答。

### 根因分析

在修复 BUG-003 时，只更新了 `SmartOptimizationConfig.initial_budget` 从 2000 到 20000，但遗漏了 `TokenBudgetConfig.initial_budget` 的默认值：

```python
# nano_agent/config/schema.py (已修复)
class SmartOptimizationConfig:
    initial_budget: int = 20000  # ✅ 已更新

# nano_agent/agent/token_budget.py (遗漏)
@dataclass
class TokenBudgetConfig:
    initial_budget: int = 2000   # ❌ 未更新！
```

虽然 `ReActAgent.__init__` 正确传递了配置值，但如果直接使用 `TokenBudget()` 无参数构造，仍会使用 2000 的默认值。

### 为什么测试没发现

1. 测试用例 `test_default_values` 只测试了 `SmartOptimizationConfig.initial_budget`
2. 测试用例 `test_initial_state` 期望值是 2000，测试通过但期望错误
3. 没有端到端测试验证多轮对话场景下预算是否足够

### 修复方案

同步更新 `TokenBudgetConfig.initial_budget` 默认值：

```python
# nano_agent/agent/token_budget.py
@dataclass
class TokenBudgetConfig:
    initial_budget: int = 20000  # Updated from 2000
```

### 补充的测试用例

**`test_smart_optimization.py`** - 更新测试期望：
- `test_initial_state`: 期望 `remaining == 20000`

### 经验教训

1. **配置默认值要同步**：当修改一处配置默认值时，要检查所有相关类的默认值
2. **测试期望值要正确**：测试通过不代表正确，要验证期望值是否合理
3. **配置传递链路要完整测试**：不仅要测试配置类，还要测试实际使用场景

### 相关文件

- `nano_agent/config/schema.py` - SmartOptimizationConfig 定义
- `nano_agent/agent/token_budget.py` - TokenBudgetConfig 定义（遗漏点）
- `nano_agent/agent/react.py` - 配置传递逻辑

---

## BUGLIST 格式说明

每个 BUG 记录应包含：

- **发现日期**: YYYY-MM-DD
- **严重程度**: 高/中/低
- **影响范围**: 受影响的用户或功能
- **问题描述**: 错误现象和报错信息
- **根因分析**: 为什么会发生
- **为什么测试没发现**: 测试覆盖不足的原因
- **修复方案**: 具体的代码修改
- **补充的测试用例**: 防止再次发生的测试
- **经验教训**: 可改进的开发流程
- **相关提交**: 相关的 git commit