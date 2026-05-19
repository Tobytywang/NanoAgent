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