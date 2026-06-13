# 资源约束与限制参考

> 本文档汇总 NanoAgent 中所有约束会话执行的资源限制，按作用方式分为**硬限制**（直接终止对话）和**软限制**（间接影响对话质量）。

---

## 硬限制（直接终止对话）

以下限制会在条件满足时直接终止 ReAct 循环或跳过操作，导致对话无法继续执行。

### 1. 迭代次数限制

| 项目 | 值 |
|------|------|
| 配置路径 | `agent.max_iterations` |
| 默认值 | `10` |
| 源码位置 | `nano_agent/config/schema.py` → `AgentConfig` |

ReAct 循环最多运行 10 轮 Think-Act-Observe。超过后返回超时消息并终止。

```yaml
# 配置示例
agent:
  max_iterations: 15  # 增大以支持更复杂任务
```

### 2. Token 总量限制

| 项目 | 值 |
|------|------|
| 配置路径 | 内部 `Budget` 对象 |
| 默认值 | `100000` |
| 源码位置 | `nano_agent/agent/budget.py` → `Budget` |

全会话累计 Token 消耗（prompt + completion）超过此值时终止循环。`BudgetChecker.can_continue()` 在每轮迭代开始时检查此限制。

### 3. 工具调用总次数限制

| 项目 | 值 |
|------|------|
| 配置路径 | 内部 `Budget` 对象 |
| 默认值 | `50` |
| 源码位置 | `nano_agent/agent/budget.py` → `Budget` |

全会话累计工具调用次数超过此值时终止循环。与 Token 总量限制一起由 `BudgetChecker` 在每轮检查。

> **注意**：`Budget` 的 `max_iterations`、`max_tokens`、`max_tool_calls` 三个维度构成 BudgetChecker 的检查条件，**任一维度超限即终止**。

### 4. Token 预算耗尽

| 项目 | 值 |
|------|------|
| 配置路径 | `smart_optimization.initial_budget` |
| 默认值 | `50000` |
| 源码位置 | `nano_agent/config/schema.py` → `SmartOptimizationConfig`；`nano_agent/agent/token_budget.py` → `TokenBudgetConfig` |

每轮扣减实际 LLM 消耗的 Token，预算归零时调用 `_force_summarize()` 强制总结并终止。与 BudgetChecker 不同，这是逐扣减制而非累计检查。

**复杂度预算 Profile（v0.7.16）**：

Token 预算按查询复杂度动态调整，小任务不浪费大预算：

| 复杂度 | 预算比例 | 实际预算（以 50000 为例） |
|--------|----------|--------------------------|
| SIMPLE | 15% | 7500 |
| MODERATE | 50% | 25000 |
| COMPLEX | 100% | 50000 |

| 配置项 | 默认值 | 说明 |
|--------|--------|------|
| `smart_optimization.complexity_budget_enabled` | `True` | 是否按复杂度调整预算 |
| `smart_optimization.complexity_budget_simple_ratio` | `0.15` | SIMPLE 预算比例 |
| `smart_optimization.complexity_budget_moderate_ratio` | `0.5` | MODERATE 预算比例 |
| `smart_optimization.complexity_budget_complex_ratio` | `1.0` | COMPLEX 预算比例 |

**预算收尾轮（v0.7.9）**：

预算即将耗尽时（剩余比例 ≤ `budget_wrapup_threshold`），触发收尾轮：注入收尾指令到对话，让 LLM 执行最后一轮总结。收尾轮可以不扣预算（`budget_wrapup_free_round`），相当于"低电量时弹出保存对话框"。

| 配置项 | 默认值 | 说明 |
|--------|--------|------|
| `smart_optimization.budget_wrapup_enabled` | `False` | 是否启用收尾轮 |
| `smart_optimization.budget_wrapup_threshold` | `0.1` | 触发阈值（剩余比例 ≤ 此值时触发） |
| `smart_optimization.budget_wrapup_free_round` | `True` | 收尾轮不扣预算 |
| `smart_optimization.budget_wrapup_max_tokens` | `2000` | 收尾轮 LLM 最大 Token 数 |

```yaml
smart_optimization:
  budget_wrapup_enabled: true      # 启用收尾轮
  budget_wrapup_threshold: 0.15    # 剩余 15% 时触发
  budget_wrapup_free_round: true   # 收尾轮不扣预算
```

**渐进式预算警告**：

| 配置项 | 默认值 | 说明 |
|--------|--------|------|
| `smart_optimization.budget_warning_thresholds` | `[0.5, 0.3, 0.2, 0.1]` | 剩余比例降至 50%/30%/20%/10% 时触发警告 |
| `smart_optimization.budget_warning_mode` | `"console"` | 警告输出方式：`silent`/`console`/`event` |
| `smart_optimization.budget_warning_interval` | `1` | 最小迭代间隔（防警告刷屏） |
| `smart_optimization.budget_force_summarize` | `True` | 预算耗尽时强制总结 |
| `smart_optimization.budget_llm_summary_enabled` | `True` | 使用 LLM 生成结构化摘要 |
| `smart_optimization.budget_llm_summary_max_tokens` | `500` | LLM 摘要最大 Token 数 |

**预算动态校准**：

| 配置项 | 默认值 | 说明 |
|--------|--------|------|
| `calibration_enabled` | `True` | 基于历史 Usage 校准预算预测 |
| `calibration_window` | `5` | 校准窗口（最近 5 次调用） |
| `min_calibration_samples` | `3` | 最少采样数（3 次后才启动校准） |

**估算审计** (v0.7.18)：

| 配置项 | 默认值 | 说明 |
|--------|--------|------|
| `estimation_audit_enabled` | `True` | 启用估算偏差审计 |
| `estimation_deviation_warning_threshold` | `0.50` | 偏差告警阈值（>50% 触发 WARNING） |

```yaml
smart_optimization:
  initial_budget: 80000        # 增大预算支持更长对话
  budget_warning_thresholds: [0.5, 0.3, 0.2, 0.1]
  budget_force_summarize: true
  budget_llm_summary_enabled: true
```

### 5. 置信度早停

| 项目 | 值 |
|------|------|
| 配置路径 | `smart_optimization.confidence_enabled` / `confidence_threshold` |
| 默认值 | `True` / `0.9` |
| 源码位置 | `nano_agent/agent/confidence.py` → `ConfidenceParser` |

LLM 被要求在响应末尾输出 `[CONFIDENCE: X.XX] [CAN_ANSWER: yes/no]`。当置信度 ≥ 0.9 且 `CAN_ANSWER=yes` 时，ReAct 循环提前终止，不再继续调用工具。

```yaml
smart_optimization:
  confidence_enabled: true
  confidence_threshold: 0.8   # 降低阈值更容易早停
```

### 6. 查询复杂度路由限制

| 项目 | 值 |
|------|------|
| 配置路径 | `smart_optimization.routing_enabled` / `routing_simple_direct` / `routing_moderate_single_tool` |
| 默认值 | `True` / `True` / `True` |
| 源码位置 | `nano_agent/agent/router.py` → `QueryRouter` |

根据查询复杂度限制工具调用次数：

| 复杂度 | 最大工具调用 | 处理方式 |
|--------|-------------|---------|
| 简单 (SIMPLE) | 0 | 直接回答，不进入 ReAct 循环 |
| 中等 (MODERATE) | 1 | 单次 LLM + 最多 1 次工具 |
| 复杂 (COMPLEX) | 不限 | 完整 ReAct 循环 |

```yaml
smart_optimization:
  routing_enabled: true
  routing_simple_direct: true      # 简单问题直接回答
  routing_moderate_single_tool: true  # 中等问题限 1 次工具
```

### 7. 重复调用阻断

| 项目 | 值 |
|------|------|
| 配置路径 | `smart_optimization.duplicate_threshold` / `duplicate_deep_equal` |
| 默认值 | `3` / `False` |
| 源码位置 | `nano_agent/agent/duplicate.py` → `DuplicateDetector` |

同一工具名+参数组合调用超过 `duplicate_threshold` 次后自动跳过，返回缓存结果或 `[skipped] duplicate call`。防止 LLM 陷入重复调用死循环。

`duplicate_deep_equal` 控制键生成方式：
- `False`（默认）：使用 `MD5[:8]` 哈希，与之前行为一致
- `True`：使用完整 JSON 参数比较，更精确但键更长

```yaml
smart_optimization:
  duplicate_threshold: 5     # 允许更多重复调用
  duplicate_deep_equal: true  # 使用精确参数比较
```

### 8. 各类超时

超时后请求中断，返回错误结果。不直接终止循环，但可能导致 Agent 因工具错误而无法继续。

| 类型 | 默认值 | 配置路径 | 源码位置 |
|------|--------|---------|---------|
| LLM API 调用 | `120s` | `llm.timeout` | `nano_agent/config/schema.py` → `LLMConfig` |
| Shell 命令执行 | `30s` | 不可配置 | `nano_agent/tools/builtin/shell.py` |
| Python 代码执行 | `30s` | 不可配置 | `nano_agent/tools/builtin/python_executor.py` |
| Web 搜索 | `15s` | 不可配置 | `nano_agent/tools/builtin/web_search.py` |
| Git 命令 | `5-10s` | 不可配置 | `nano_agent/agent/git_manager.py` |

```yaml
llm:
  timeout: 180  # 增大 LLM 超时（慢模型场景）
```

### 9. Stall Detection 停滞检测

| 项目 | 值 |
|------|------|
| 配置路径 | `smart_optimization.stall_detection_enabled` / `stall_patience` / `stall_similarity_threshold` |
| 默认值 | `True` / `3` / `0.7` |
| 源码位置 | `nano_agent/agent/stall_detector.py` → `StallDetector` |

当连续 N 次迭代产生相似结果（Jaccard 相似度 ≥ threshold）时，判定 Agent 停滞（原地打转）。停滞时注入转向提示让 LLM 换策略，而非直接终止循环。

**与重复调用阻断的区别**：DuplicateDetector 检测完全相同的重复调用；StallDetector 检测"不同工具但结果相似"的停滞模式。

| 配置项 | 默认值 | 说明 |
|--------|--------|------|
| `smart_optimization.stall_detection_enabled` | `True` | 是否启用停滞检测 |
| `smart_optimization.stall_patience` | `3` | 连续相似迭代次数阈值 |
| `smart_optimization.stall_similarity_threshold` | `0.7` | 签名相似度阈值（Jaccard） |
| `smart_optimization.stall_hint_injection` | `True` | 检测到停滞时注入转向提示 |

```yaml
smart_optimization:
  stall_detection_enabled: true
  stall_patience: 5            # 更耐心，允许更多相似迭代
  stall_similarity_threshold: 0.8  # 更严格的相似度判定
  stall_hint_injection: true
```

### 10. LLM 调用重试

**触发条件**: LLM API 返回 429（限流）、500/502/503/504（服务端错误）或网络故障（ConnectionError、Timeout）。

**行为**: 指数退避重试，延迟 = `min(base * 2^attempt + jitter, max_delay)`。默认最多重试 3 次。

**不可重试**: 400/401/403/404（客户端错误）、ValueError/TypeError（逻辑错误）立即抛出，不重试。

**事件**: 每次重试触发 `AgentEvent.LLM_RETRY` 事件，verbose 模式打印 `[Retry 1/3] ConnectionError, waiting 1.0s...`。

```yaml
retry:
  enabled: true
  max_retries: 3
  base_delay: 1.0
  max_delay: 60.0
  jitter: true
  retryable_status_codes: [429, 500, 502, 503, 504]
```

### 12. 速率限制

| 项目 | 值 |
|------|------|
| 配置路径 | `rate_limiter.*` |
| 默认值 | `enabled: True` / `requests_per_minute: 60` / `burst: 10` |
| 源码位置 | `nano_agent/config/schema.py` → `RateLimiterConfig` |

基于令牌桶算法，在 LLM API 调用前主动控制请求频率，防止触发 API 限流（429 错误）。与重试机制配合使用：速率限制是"预防"，重试是"治疗"。

**令牌桶算法**：
- 令牌以 `requests_per_minute / 60` 的速率填充到桶中
- 桶容量为 `burst`，满时新令牌被丢弃
- 每次请求消耗一个令牌
- 桶空时请求阻塞等待直到获取令牌

| 配置项 | 默认值 | 说明 |
|--------|--------|------|
| `rate_limiter.enabled` | `True` | 是否启用速率限制 |
| `rate_limiter.requests_per_minute` | `60` | 每分钟最大请求数（必须 > 0） |
| `rate_limiter.burst` | `10` | 令牌桶容量，允许突发请求数（必须 > 0） |

**约束验证**: `requests_per_minute <= 0` 或 `burst <= 0` 时，`RateLimiterConfig.__post_init__()` 抛出 `ValueError`。

```yaml
rate_limiter:
  enabled: true
  requests_per_minute: 60   # 每分钟 60 次请求
  burst: 10                 # 允许 10 次突发
```

### 13. 熔断器降级

| 项目 | 值 |
|------|------|
| 配置路径 | `smart_optimization.circuit_breaker.*` |
| 默认值 | `enabled: True` |
| 源码位置 | `nano_agent/agent/circuit_breaker.py` → `CircuitBreaker` |

检测异常 LLM 行为后，从 AUTO 模式降级到 SUPERVISED 模式，要求用户确认每个工具调用。不是限制总 token，而是检测异常行为后干预。

**三种触发条件**：

| 触发条件 | 检测位置 | 默认阈值 | 说明 |
|---------|---------|---------|------|
| LLM 响应过大 | `_think()` 后 | `max_response_tokens: 8000` | 单次 completion_tokens 超限 |
| 重复工具调用 | `_act()` 中 | `duplicate_trigger_count: 3` | 复用 DuplicateDetector 结果 |
| 停滞检测 | 迭代结束后 | `stall_trigger_count: 3` | 复用 StallDetector 结果 |

**降级行为**：

- AUTO → SUPERVISED：每个工具调用强制走 `ConfirmationManager` 确认流程
- 用户确认后可选自动恢复 AUTO（`auto_reset_on_user_confirm: True`）
- `/auto` CLI 命令手动恢复 AUTO 模式

| 配置项 | 默认值 | 说明 |
|--------|--------|------|
| `smart_optimization.circuit_breaker.enabled` | `True` | 是否启用熔断器 |
| `smart_optimization.circuit_breaker.max_response_tokens` | `8000` | LLM 单次响应上限 |
| `smart_optimization.circuit_breaker.duplicate_trigger_count` | `3` | 重复调用触发次数 |
| `smart_optimization.circuit_breaker.stall_trigger_count` | `3` | 停滞触发次数 |
| `smart_optimization.circuit_breaker.auto_reset_on_user_confirm` | `True` | 用户确认后自动恢复 AUTO |

```yaml
smart_optimization:
  circuit_breaker:
    enabled: true
    max_response_tokens: 8000
    duplicate_trigger_count: 3
    stall_trigger_count: 3
    auto_reset_on_user_confirm: true
```

### 14. 输入净化

| 项目 | 值 |
|------|------|
| 配置路径 | `sanitizer.*` |
| 默认值 | `enabled: True` / `max_input_length: 10000` / `length_action: "truncate"` |
| 源码位置 | `nano_agent/config/schema.py` → `SanitizerConfig`；`nano_agent/agent/sanitizer.py` → `InputSanitizer` |

在编排层（orchestrator）边界对用户输入执行净化检查，是 ReAct 循环前的**硬门控**。输入被拒绝时返回 `TerminationReason.INPUT_REJECTED`，不进入 ReAct 循环。

**处理顺序**（顺序不可调换，格式检查先于注入检查防止编码绕过）：

1. **格式检查**：null 字节 → 直接拒绝；控制字符 → 剥离（保留换行/制表符）
2. **PII 脱敏**（可选）：检测 phone/id_card/email/api_key → 遮蔽后替换原始文本
3. **注入检查**：正则匹配 injection_patterns + custom_patterns → 匹配则直接拒绝
4. **长度检查**：超过 `max_input_length` → 按 `length_action` 截断或拒绝

**注入检测**：默认 18 条正则覆盖常见 prompt injection 模式（ignore previous instructions、system prompt override、role manipulation 等）。`custom_patterns` 允许用户添加领域特定的注入模式。

| 配置项 | 默认值 | 说明 |
|--------|--------|------|
| `sanitizer.enabled` | `True` | 是否启用输入净化 |
| `sanitizer.injection_patterns` | 18 条默认正则 | 注入检测正则列表 |
| `sanitizer.custom_patterns` | `[]` | 用户自定义注入检测正则 |
| `sanitizer.max_input_length` | `10000` | 输入最大字符长度 |
| `sanitizer.length_action` | `"truncate"` | 超长处理方式：`truncate` 截断 / `reject` 拒绝 |
| `sanitizer.reject_null_bytes` | `True` | 拒绝含 null 字节的输入 |
| `sanitizer.reject_control_chars` | `True` | 剥离控制字符 |
| `sanitizer.pii_enabled` | `False` | 启用 PII 脱敏（默认关闭） |
| `sanitizer.pii_mask_mode` | `"partial"` | 遮蔽模式：`"partial"` 保留首尾 / `"full"` 全遮蔽 |
| `sanitizer.pii_mask_char` | `"*"` | 遮蔽字符 |
| `sanitizer.pii_types` | `["phone", "id_card", "email", "api_key"]` | 启用的 PII 检测类型 |

```yaml
sanitizer:
  enabled: true
  max_input_length: 10000
  length_action: truncate       # truncate / reject
  reject_null_bytes: true
  reject_control_chars: true
  custom_patterns: []           # 添加自定义注入检测正则
  pii_enabled: true             # 启用 PII 脱敏
  pii_mask_mode: partial        # partial / full
  pii_mask_char: "*"            # 遮蔽字符
  pii_types:                    # 启用的 PII 类型
    - phone
    - id_card
    - email
    - api_key
```

### 8b. 输出护栏 (Output Guard)

| 项目 | 值 |
|------|------|
| 配置路径 | `output_guard.*` |
| 源码位置 | `nano_agent/config/schema.py` → `OutputGuardConfig`；`nano_agent/agent/output_guard.py` → `OutputGuard` |

输出护栏在编排层（orchestrator）边界扫描 Agent 响应中的敏感信息，是 ReAct 循环后的硬门控。

| 配置项 | 默认值 | 说明 |
|--------|--------|------|
| `output_guard.enabled` | `True` | 是否启用输出护栏 |
| `output_guard.action` | `"mask"` | 拦截动作：`mask` 遮蔽 / `block` 拦截 / `warn` 警告 |
| `output_guard.mask_mode` | `"partial"` | 遮蔽模式：`"partial"` 保留首尾 / `"full"` 全遮蔽 |
| `output_guard.mask_char` | `"*"` | 遮蔽字符 |
| `output_guard.sensitive_types` | 7 种默认类型 | 启用的敏感检测类型 |
| `output_guard.block_severity` | `["private_key"]` | 强制触发 block 的类型 |
| `output_guard.custom_patterns` | `[]` | 用户自定义检测模式 |

```yaml
output_guard:
  enabled: true
  action: mask                # mask / block / warn
  mask_mode: partial          # partial / full
  mask_char: "*"              # 遮蔽字符
  sensitive_types:            # 启用的敏感类型
    - api_key
    - password
    - private_key
    - connection_string
    - phone
    - id_card
    - email
  block_severity:             # 强制拦截的类型
    - private_key
  custom_patterns: []         # 添加自定义检测模式
```

### 8c. 有害内容过滤 (Harmful Content Filter)

| 项目 | 值 |
|------|------|
| 配置路径 | `harmful_content_filter.*` |
| 默认值 | `enabled: False` / `default_action: "block"` |
| 源码位置 | `nano_agent/config/schema.py` → `HarmfulContentFilterConfig`；`nano_agent/agent/harmful_filter.py` → `HarmfulContentFilter` |

有害内容过滤器在编排层（orchestrator）边界扫描 Agent 响应中的有害/危险内容，是输出护栏之后的第二道防线。OutputGuard 防止信息*泄露*，HarmfulContentFilter 防止*有害内容*触达用户。默认关闭（opt-in），用户需显式启用并配置检测类别。

**四种检测类别**:

| 类别 | 严重度 | 说明 |
|------|--------|------|
| `violence` | high | 暴力内容（制造武器/爆炸物指示、杀人方法、暴力犯罪教唆） |
| `hate` | high | 仇恨言论（仇恨言论+攻击意图、种族歧视+暴力、种族清洗） |
| `dangerous` | high | 危险内容（自杀/自残方法、毒品合成、黑客攻击/入侵教程） |
| `illegal` | medium | 违法内容（洗钱方法、逃税方法、伪造货币/证件、身份盗窃） |

**三种处理动作**:

| 动作 | 说明 |
|------|------|
| `block` | 拦截整个响应，返回空文本（block 优先于 warn/replace） |
| `warn` | 允许响应但添加 `[Content Warning: ...]` 前缀 |
| `replace` | 将有害片段替换为 `replacement_text`，保留非有害部分 |

| 配置项 | 默认值 | 说明 |
|--------|--------|------|
| `harmful_content_filter.enabled` | `False` | 是否启用有害内容过滤 |
| `harmful_content_filter.categories` | `["violence", "hate", "dangerous", "illegal"]` | 启用的检测类别 |
| `harmful_content_filter.default_action` | `"block"` | 默认处理动作：`"block"` / `"warn"` / `"replace"` |
| `harmful_content_filter.category_actions` | `{}` | 按类别覆盖动作（如 `{"illegal": "warn"}`） |
| `harmful_content_filter.replacement_text` | `"[Content removed for safety]"` | replace 动作的替换文本 |
| `harmful_content_filter.custom_patterns` | `[]` | 用户自定义有害内容模式 |

**HarmfulContentMiddleware**: priority=99，在工具执行边界（after phase）扫描工具输出，仅执行替换不拦截。低于 SensitiveOutputMiddleware（priority=100），确保敏感信息先被处理。

**事件**: 拦截时触发 `AgentEvent.HARMFUL_CONTENT_DETECTED`（action="blocked"）和 `AgentEvent.OUTPUT_BLOCKED`（filter_type="harmful_content"），终止原因为 `TerminationReason.HARMFUL_CONTENT_BLOCKED`。

```yaml
harmful_content_filter:
  enabled: true
  categories:                      # 启用的检测类别
    - violence
    - hate
    - dangerous
    - illegal
  default_action: block            # 默认动作：block / warn / replace
  category_actions:                # 按类别覆盖动作
    illegal: warn                  # illegal 仅警告
  replacement_text: "[Content removed for safety]"
  custom_patterns: []              # 自定义有害内容模式
```

### 8d. 结果正确性验证 (Result Validator)

| 项目 | 值 |
|------|------|
| 配置路径 | `result_validator.*` |
| 默认值 | `enabled: False` / `on_fail: "annotate"` |
| 源码位置 | `nano_agent/config/schema.py` → `ResultValidatorConfig`；`nano_agent/agent/result_validator.py` → `ResultValidator` |

作为第三道输出防线，在 OutputGuard 和 HarmfulContentFilter 之后验证结果正确性。验证 Agent 输出中的声明是否与实际结果一致（如声称创建了文件但文件不存在）。默认关闭（opt-in），用户需显式启用。

| 配置项 | 默认值 | 说明 |
|--------|--------|------|
| `result_validator.enabled` | `False` | 是否启用结果正确性验证 |
| `result_validator.checks` | `["file_exists", "code_syntax", "command_success"]` | 启用的验证检查类型 |
| `result_validator.on_fail` | `"annotate"` | 检查失败时的动作：`"block"` 拦截（仅 high-severity）/ `"warn"` 警告 / `"annotate"` 添加验证标注 |
| `result_validator.on_pass` | `"silent"` | 所有检查通过时的动作：`"silent"` 无输出 / `"annotate"` 添加通过标注 |
| `result_validator.custom_validators` | `[]` | 自定义验证器函数列表 |
| `result_validator` | — | 结果正确性验证器整体配置 |

**事件**: 拦截时触发 `AgentEvent.VALIDATION_FAILED`（action="blocked"）和 `AgentEvent.OUTPUT_BLOCKED`（filter_type="result_validator"），终止原因为 `TerminationReason.VALIDATION_FAILED`。

```yaml
result_validator:
  enabled: true                       # 启用结果正确性验证
  checks:                             # 启用的验证检查类型
    - file_exists                     # 验证声称创建的文件是否存在
    - code_syntax                     # 验证声称正确的代码语法
    - command_success                 # 验证声称成功的命令结果
  on_fail: annotate                   # 失败时动作：block / warn / annotate
  on_pass: silent                     # 通过时动作：silent / annotate
  custom_validators: []               # 自定义验证器函数列表
```

---

## 软限制（间接影响对话质量）

以下限制不会直接终止对话，但会影响上下文内容、输出长度或信息完整性。

### 9. 上下文压力三层阈值

| 项目 | 值 |
|------|------|
| 配置路径 | `context.*` |
| 源码位置 | `nano_agent/config/schema.py` → `ContextConfig`；`nano_agent/agent/context.py` → `ContextManager` |

当对话消息 Token 占模型上下文窗口的比例超过阈值时，逐级触发压缩：

| 阈值 | 触发行为 | 效果 |
|------|---------|------|
| `pressure_threshold_low` = `0.70` (70%) | 轻清理 (`_try_light_cleanup`) | 移除过期临时消息 |
| `pressure_threshold_mid` = `0.85` (85%) | 摘要标记 (`_try_summary_mark`) | 标记旧消息为可删除，保留关键消息 |
| `pressure_threshold_high` = `0.95` (95%) | 模型压缩 (`_try_model_compress`) | 生成九段式摘要替换旧消息 |

| 配置项 | 默认值 | 说明 |
|--------|--------|------|
| `context.max_context_tokens` | `None`（自动检测） | 模型上下文窗口大小 |
| `context.max_compress_failures` | `3` | 连续压缩失败熔断阈值 |
| `context.summary_max_tokens` | `4000` | 九段式摘要最大 Token 数 |
| `context.temp_message_age` | `5` | 临时消息过期轮数 |

```yaml
context:
  pressure_threshold_low: 0.70
  pressure_threshold_mid: 0.85
  pressure_threshold_high: 0.95
  max_compress_failures: 3
  summary_max_tokens: 4000
```

### 10. 压缩熔断

| 项目 | 值 |
|------|------|
| 配置路径 | `context.max_compress_failures` |
| 默认值 | `3` |

连续模型压缩失败 3 次后，`ContextManager` 停止所有后续压缩尝试。此后上下文将持续增长直到上下文窗口溢出（由模型 API 自动截断）。

### 11. 消息数量上限

| 项目 | 值 |
|------|------|
| 配置路径 | `memory.max_messages` |
| 默认值 | `50` |
| 源码位置 | `nano_agent/memory/short_term.py` → `_trim_if_needed()` |

当内存中的消息数超过 `max_messages` 时，裁剪旧消息（保留系统消息 + 最近 49 条）。被裁剪的消息永久丢失，Agent 无法回溯。

```yaml
memory:
  max_messages: 80  # 增大以保留更多对话历史
```

### 12. 历史消息压缩

| 项目 | 值 |
|------|------|
| 配置路径 | `compressor.*` |
| 源码位置 | `nano_agent/config/schema.py` → `CompressorConfig`；`nano_agent/agent/compressor.py` |

在 `_think()` 前，如果 `prompt_tokens` 超过阈值，旧消息被压缩为 `[历史摘要]`，仅保留最近 N 轮原文。

| 配置项 | 默认值 | 说明 |
|--------|--------|------|
| `compressor.enabled` | `True` | 是否启用压缩 |
| `compressor.threshold_tokens` | `2000` | 触发压缩的 prompt_tokens 阈值 |
| `compressor.keep_recent` | `3` | 保留最近 3 轮原文 |
| `compressor.summary_max_tokens` | `500` | 摘要最大 Token 数 |

```yaml
compressor:
  enabled: true
  threshold_tokens: 1500
  keep_recent: 3
  summary_max_tokens: 300
```

### 13. 工具输出截断

| 项目 | 值 |
|------|------|
| 配置路径 | `output_style.tool_output_max_tokens` |
| 默认值 | `500`（约 2000 字符） |
| 源码位置 | `nano_agent/config/schema.py` → `OutputStyleConfig` |

在 `_observe()` 中，工具输出超过 `max_tokens * 4` 字符时截断，附加截断标记。截断后的内容进入上下文，影响 LLM 的信息完整性。

```yaml
output_style:
  tool_output_max_tokens: 800  # 增大以保留更多工具输出
```

### 14. 提示词 Token 预算

| 项目 | 值 |
|------|------|
| 配置路径 | `prompt.token_budget` |
| 默认值 | `2000` |
| 源码位置 | `nano_agent/config/schema.py` → `PromptConfig`；`nano_agent/agent/prompt_modules.py` → `STYLE_PRESETS` |

系统提示词的 Token 目标上限，决定哪些模块被包含。不同风格预设使用不同预算：

| 风格 | token_budget | 包含模块数 | 系统提示词 Token |
|------|-------------|-----------|----------------|
| `concise` | `200` | ~4 个核心模块 | ~300 |
| `standard` | `1000` | ~12 个模块 | ~800 |
| `detailed` | `2000` | ~17 个全部模块 | ~1500 |

```yaml
prompt:
  style: concise       # 使用简洁预设
  token_budget: 200    # 简洁模式预算
```

### 15. LLM 响应上限

| 项目 | 值 |
|------|------|
| 配置路径 | 不可配置 |
| 默认值 | `4096` |
| 源码位置 | `nano_agent/llm/anthropic.py` → `AnthropicLLM` |

AnthropicLLM 在每次 API 调用中设置 `max_tokens: 4096`，限制 LLM 单次响应的 completion Token 数。其他 LLM 提供者（Ollama、OpenAI Compatible）使用模型默认值。

### 16. 缓存限制

| 项目 | 值 |
|------|------|
| 配置路径 | `cache.*` |
| 源码位置 | `nano_agent/config/schema.py` → `CacheConfig`；`nano_agent/agent/cache.py` → `ToolResultCache` |

| 配置项 | 默认值 | 说明 |
|--------|--------|------|
| `cache.enabled` | `True` | 是否启用工具结果缓存 |
| `cache.ttl_seconds` | `300` (5 分钟) | 缓存过期时间 |
| `cache.max_cache_size` | `100` | 最大缓存条目数（LRU 淘汰） |
| `cache.persist` | `False` | 是否持久化到磁盘 |
| `cache.mtime_invalidation` | `True` | 文件修改后缓存自动失效 |

缓存仅对只读工具生效（`file_read`、`file_search`、`shell_execute`），写操作不缓存。缓存过期后需要重新调用工具，增加 Token 消耗。

```yaml
cache:
  enabled: true
  ttl_seconds: 600   # 增大 TTL 减少重复调用
  max_cache_size: 200
  persist: true       # 开启跨会话持久化
  mtime_invalidation: true
```

### 17. 工具结果卸载限制

| 项目 | 值 |
|------|------|
| 配置路径 | `offload.*` |
| 源码位置 | `nano_agent/config/schema.py` → `ToolOffloadConfig`；`nano_agent/agent/tool_offload.py` → `ToolOffloadManager` |

| 配置项 | 默认值 | 说明 |
|--------|--------|------|
| `offload.enabled` | `True` | 是否启用卸载 |
| `offload.size_threshold_tokens` | `1000` | 超过此 token 数触发卸载 |
| `offload.summary_max_tokens` | `200` | 摘要最大 token 数 |
| `offload.auto_cleanup` | `True` | 会话结束时自动清理临时文件 |

仅 `can_offload=True` 的工具触发卸载（file_read、file_search、shell_execute、python_execute、web_search）。卸载后 LLM 仅看到摘要，需通过 `file_read(path)` 按需加载完整结果。

```yaml
offload:
  enabled: true
  size_threshold_tokens: 1000
  summary_max_tokens: 200
  auto_cleanup: true
```

### 18. 语义压缩

| 项目 | 值 |
|------|------|
| 配置路径 | `semantic_compressor.*` |
| 源码位置 | `nano_agent/config/schema.py` → `SemanticCompressorConfig`；`nano_agent/agent/semantic_compressor.py` → `SemanticCompressor` |

通过 embedding 向量计算余弦相似度，合并长对话中语义重复的历史消息。仅同 role 消息可合并，system 消息不参与。作为第二遍压缩，在 `MessageCompressor` 之后运行。

| 配置项 | 默认值 | 说明 |
|--------|--------|------|
| `semantic_compressor.enabled` | `False` | 默认关闭，需 embedding 服务 |
| `semantic_compressor.similarity_threshold` | `0.85` | 余弦相似度阈值 |
| `semantic_compressor.min_messages_to_compress` | `8` | 最少消息数触发 |
| `semantic_compressor.provider` | `"ollama"` | Embedding 提供者 |
| `semantic_compressor.embedding_model` | `"nomic-embed-text"` | Embedding 模型 |
| `semantic_compressor.cache_embeddings` | `True` | 缓存 embedding 向量 |
| `semantic_compressor.merge_tag` | `"[merged {n} similar]"` | 合并标签模板 |

Embedding 服务不可用时优雅降级，静默跳过不报错。

```yaml
semantic_compressor:
  enabled: true
  similarity_threshold: 0.85
  min_messages_to_compress: 8
  provider: ollama
  embedding_model: nomic-embed-text
```

### 19. 会话清理阈值

| 项目 | 值 |
|------|------|
| 配置路径 | `memory.clean_threshold` |
| 默认值 | `3` |

少于 3 条消息的会话视为"低价值"，可在 `--clean-sessions` 时自动删除。不影响正在进行的对话。

---

## 约束交互关系

多个限制在 ReAct 循环中按以下顺序检查：

```
用户输入
  │
  ├─ 〇 输入净化（sanitizer 硬门控）
  │   ├─ 格式检查：null 字节 → 拒绝，控制字符 → 剥离
  │   ├─ PII 脱敏：phone/id_card/email/api_key → 遮蔽替换
  │   ├─ 注入检查：正则匹配 → 拒绝（TerminationReason.INPUT_REJECTED）
  │   ├─ 长度检查：超长 → 截断或拒绝
  │
  ├─ ① 查询复杂度路由 ─→ 简单问题直接返回（不进循环）
  │
  ├─ 进入 ReAct 循环
  │   │
  │   ├─ ② BudgetChecker（iterations / tokens / tool_calls 任一超限 → 终止）
  │   │
  │   ├─ ③ TokenBudget（预算耗尽 → 强制总结终止）
  │   │   ├─ 渐进式警告（50% → 30% → 20% → 10%）
  │   │   ├─ 收尾轮（剩余 ≤ wrapup_threshold → 注入收尾指令 → 最后一轮 LLM → 终止）
  │   │
  │   ├─ ④ 上下文压力检测
  │   │   ├─ 70% → 轻清理
  │   │   ├─ 85% → 摘要标记
  │   │   ├─ 95% → 模型压缩（失败 3 次 → 熔断）
  │   │
  │   ├─ ⑤ 历史消息压缩（prompt_tokens > threshold → 压缩旧消息）
  │   │
  │   ├─ ⑥ _think() → LLM 调用
  │   │   ├─ 系统提示词受 token_budget 限制
  │   │   ├─ 速率限制（令牌桶 acquire → 桶空则等待）
  │   │   ├─ 指数退避重试（429/500/网络错误 → 自动重试）
  │   │   ├─ 工具输出受 tool_output_max_tokens 截断
  │   │
  │   ├─ ⑦ 置信度早停（confidence ≥ 0.9 且 can_answer → 终止）
  │   │
  │   ├─ ⑧ _act() → 工具调用
  │   │   ├─ 重复调用检测（>3 次 → 跳过）
  │   │   ├─ 查询路由工具数限制（中等=1次，简单=0次）
  │   │   ├─ 工具缓存命中 → 跳过执行
  │   │   ├─ 确认机制（危险工具需用户确认）
  │   │
  │   ├─ ⑨ _observe() → 工具输出截断后写入内存
  │   │   ├─ 消息数 > max_messages → 裁剪旧消息
  │   │
  │   ├─ ⑩ Stall Detection → 连续相似迭代 → 注入转向提示
│   │   ├─ 熔断器检测 → 达到 stall_trigger_count → 降级到 SUPERVISED
│   │
│   ├─ ⑪ 熔断器 → SUPERVISED 模式 → 每个工具调用需用户确认
│   │   ├─ 触发条件：LLM 响应过大 / 重复调用 / 停滞
│   │   ├─ `/auto` 命令恢复 AUTO 模式
│   └─ 回到循环顶部 ↺
  │
  └─ 循环结束 → 返回 ExecutionResult
      │
      ├─ OutputGuard.guard() → 敏感信息遮蔽/拦截
      │
      ├─ HarmfulContentFilter.filter() → 有害内容过滤/拦截
      │
      └─ ResultValidator.validate() → 结果正确性验证/拦截
```

**关键交互**：
- BudgetChecker 和 TokenBudget 是**两个独立的终止机制**：BudgetChecker 检查累计值是否超限，TokenBudget 检查扣减后是否归零
- 上下文压缩和消息压缩是**两个独立的压缩机制**：上下文压缩基于窗口占比，消息压缩基于 prompt_tokens 阈值
- 置信度早停和查询路由是**两个独立的提前终止机制**：置信度在循环内部触发，路由在循环入口触发
- 预算收尾轮是**TokenBudget 的子机制**：在 `should_summarize()` 之前检查，收尾轮执行后直接终止，不会回到主循环
- 重复检测阈值现在可通过 `smart_optimization.duplicate_threshold` 配置
- Stall Detection 是**第三个提前干预机制**：与置信度早停（循环内部）和查询路由（循环入口）不同，Stall Detection 在循环末尾检测无进展并注入转向提示，不直接终止循环
- 速率限制和重试是**LLM 调用的两层防护**：速率限制是"预防"（主动控制调用频率），重试是"治疗"（被动恢复失败调用）。调用链为 `rate_limiter.acquire() → with_retry(_chat_impl)`
- 输入净化是**ReAct 循环前的硬门控**：在 orchestrator 边界执行，拒绝的输入不进入循环。处理顺序（format → PII → injection → length）不可调换，格式检查先于注入检查防止通过编码绕过，PII 脱敏在注入检查前执行确保遮蔽后的文本参与注入检测
- ResultValidator 是**第四道输出防线**：在 OutputGuard（防信息泄露）、HarmfulContentFilter（防有害内容）之后验证结果正确性。block 动作仅对 high-severity 失败生效，medium/low 失败不会触发拦截

---

## 配置速查表

| YAML 配置路径 | 默认值 | 说明 | 类别 |
|---------------|--------|------|------|
| `agent.max_iterations` | `10` | 最大迭代轮数 | 硬限制 |
| `smart_optimization.initial_budget` | `50000` | Token 预算初始值 | 硬限制 |
| `smart_optimization.budget_force_summarize` | `True` | 预算耗尽强制总结 | 硬限制 |
| `smart_optimization.confidence_enabled` | `True` | 置信度早停开关 | 硬限制 |
| `smart_optimization.confidence_threshold` | `0.9` | 置信度阈值 | 硬限制 |
| `smart_optimization.routing_enabled` | `True` | 查询路由开关 | 硬限制 |
| `smart_optimization.routing_simple_direct` | `True` | 简单问题直接回答 | 硬限制 |
| `smart_optimization.routing_moderate_single_tool` | `True` | 中等问题限 1 次工具 | 硬限制 |
| `llm.timeout` | `120` | LLM API 超时(秒) | 硬限制 |
| `context.pressure_threshold_low` | `0.70` | 上下文 70% 轻清理 | 软限制 |
| `context.pressure_threshold_mid` | `0.85` | 上下文 85% 摘要标记 | 软限制 |
| `context.pressure_threshold_high` | `0.95` | 上下文 95% 模型压缩 | 软限制 |
| `context.max_compress_failures` | `3` | 压缩熔断阈值 | 软限制 |
| `context.summary_max_tokens` | `4000` | 摘要最大 Token | 软限制 |
| `context.temp_message_age` | `5` | 临时消息过期轮数 | 软限制 |
| `memory.max_messages` | `50` | 内存消息数上限 | 软限制 |
| `memory.clean_threshold` | `3` | 会话清理阈值 | 软限制 |
| `compressor.enabled` | `True` | 消息压缩开关 | 软限制 |
| `compressor.threshold_tokens` | `2000` | 压缩触发阈值 | 软限制 |
| `compressor.keep_recent` | `3` | 保留最近轮数 | 软限制 |
| `compressor.summary_max_tokens` | `500` | 摘要最大 Token | 软限制 |
| `output_style.tool_output_max_tokens` | `500` | 工具输出截断 Token | 软限制 |
| `prompt.token_budget` | `2000` | 提示词 Token 预算 | 软限制 |
| `prompt.style` | `"standard"` | 提示词风格预设 | 软限制 |
| `cache.enabled` | `True` | 工具缓存开关 | 软限制 |
| `cache.ttl_seconds` | `300` | 缓存过期时间(秒) | 软限制 |
| `cache.max_cache_size` | `100` | 最大缓存条目数 | 软限制 |
| `smart_optimization.budget_warning_thresholds` | `[0.5, 0.3, 0.2, 0.1]` | 预算警告阈值 | 软限制 |
| `smart_optimization.budget_warning_mode` | `"console"` | 警告输出方式 | 软限制 |
| `smart_optimization.budget_warning_interval` | `1` | 警告最小间隔 | 软限制 |
| `smart_optimization.budget_llm_summary_enabled` | `True` | LLM 摘要生成开关 | 软限制 |
| `smart_optimization.budget_llm_summary_max_tokens` | `500` | LLM 摘要最大 Token | 软限制 |
| `smart_optimization.duplicate_threshold` | `3` | 重复调用阻断阈值 | 硬限制 |
| `smart_optimization.duplicate_deep_equal` | `False` | 重复检测精确模式 | 硬限制 |
| `smart_optimization.budget_wrapup_enabled` | `False` | 预算收尾轮开关 | 硬限制 |
| `smart_optimization.budget_wrapup_threshold` | `0.1` | 收尾轮触发阈值 | 硬限制 |
| `smart_optimization.budget_wrapup_free_round` | `True` | 收尾轮不扣预算 | 硬限制 |
| `smart_optimization.budget_wrapup_max_tokens` | `2000` | 收尾轮 LLM 最大 Token | 硬限制 |
| `smart_optimization.complexity_budget_enabled` | `True` | 按复杂度调整预算 | 硬限制 |
| `smart_optimization.complexity_budget_simple_ratio` | `0.15` | SIMPLE 预算比例 | 硬限制 |
| `smart_optimization.complexity_budget_moderate_ratio` | `0.5` | MODERATE 预算比例 | 硬限制 |
| `smart_optimization.complexity_budget_complex_ratio` | `1.0` | COMPLEX 预算比例 | 硬限制 |
| `smart_optimization.stall_detection_enabled` | `True` | Stall Detection 开关 | 硬限制 |
| `smart_optimization.stall_patience` | `3` | 连续相似迭代阈值 | 硬限制 |
| `smart_optimization.stall_similarity_threshold` | `0.7` | 签名相似度阈值 | 硬限制 |
| `smart_optimization.stall_hint_injection` | `True` | 停滞时注入转向提示 | 硬限制 |
| `retry.enabled` | `True` | LLM 调用重试开关 | 硬限制 |
| `retry.max_retries` | `3` | 最大重试次数 | 硬限制 |
| `retry.base_delay` | `1.0` | 基础退避延迟(秒) | 硬限制 |
| `retry.max_delay` | `60.0` | 最大退避延迟(秒) | 硬限制 |
| `retry.jitter` | `True` | 随机抖动 | 硬限制 |
| `retry.retryable_status_codes` | `[429,500,502,503,504]` | 可重试 HTTP 状态码 | 硬限制 |
| `rate_limiter.enabled` | `True` | 速率限制开关 | 硬限制 |
| `rate_limiter.requests_per_minute` | `60` | 每分钟最大请求数 | 硬限制 |
| `rate_limiter.burst` | `10` | 令牌桶容量（突发请求数） | 硬限制 |
| `smart_optimization.circuit_breaker.enabled` | `True` | 熔断器开关 | 硬限制 |
| `smart_optimization.circuit_breaker.max_response_tokens` | `8000` | LLM 单次响应上限 | 硬限制 |
| `smart_optimization.circuit_breaker.duplicate_trigger_count` | `3` | 重复调用触发次数 | 硬限制 |
| `smart_optimization.circuit_breaker.stall_trigger_count` | `3` | 停滞触发次数 | 硬限制 |
| `smart_optimization.circuit_breaker.auto_reset_on_user_confirm` | `True` | 确认后恢复 AUTO | 硬限制 |
| `sanitizer.enabled` | `True` | 输入净化开关 | 硬限制 |
| `sanitizer.max_input_length` | `10000` | 输入最大字符长度 | 硬限制 |
| `sanitizer.length_action` | `"truncate"` | 超长处理方式 | 硬限制 |
| `sanitizer.reject_null_bytes` | `True` | 拒绝 null 字节 | 硬限制 |
| `sanitizer.reject_control_chars` | `True` | 剥离控制字符 | 硬限制 |
| `sanitizer.pii_enabled` | `False` | 启用 PII 脱敏 | 硬限制 |
| `sanitizer.pii_mask_mode` | `"partial"` | 遮蔽模式 | 硬限制 |
| `sanitizer.pii_mask_char` | `"*"` | 遮蔽字符 | 硬限制 |
| `sanitizer.pii_types` | `["phone","id_card","email","api_key"]` | PII 检测类型 | 硬限制 |
| `output_guard.enabled` | `True` | 输出护栏开关 | 硬限制 |
| `output_guard.action` | `"mask"` | 拦截动作 | 硬限制 |
| `output_guard.mask_mode` | `"partial"` | 遮蔽模式 | 硬限制 |
| `output_guard.mask_char` | `"*"` | 遮蔽字符 | 硬限制 |
| `output_guard.sensitive_types` | 7 种默认类型 | 敏感检测类型 | 硬限制 |
| `output_guard.block_severity` | `["private_key"]` | 强制拦截类型 | 硬限制 |
| `harmful_content_filter.enabled` | `False` | 有害内容过滤开关 | 硬限制 |
| `harmful_content_filter.categories` | `["violence","hate","dangerous","illegal"]` | 启用的检测类别 | 硬限制 |
| `harmful_content_filter.default_action` | `"block"` | 默认处理动作 | 硬限制 |
| `harmful_content_filter.category_actions` | `{}` | 按类别覆盖动作 | 硬限制 |
| `harmful_content_filter.replacement_text` | `"[Content removed for safety]"` | 替换文本 | 硬限制 |
| `harmful_content_filter.custom_patterns` | `[]` | 自定义有害内容模式 | 硬限制 |
| `result_validator.enabled` | `False` | 结果正确性验证开关 | 硬限制 |
| `result_validator.checks` | `["file_exists","code_syntax","command_success"]` | 启用的验证检查类型 | 硬限制 |
| `result_validator.on_fail` | `"annotate"` | 检查失败时的动作 | 硬限制 |
| `result_validator.on_pass` | `"silent"` | 检查通过时的动作 | 硬限制 |
| `result_validator.custom_validators` | `[]` | 自定义验证器函数列表 | 硬限制 |
| `semantic_compressor.enabled` | `False` | 语义压缩开关 | 软限制 |
| `semantic_compressor.similarity_threshold` | `0.85` | 相似度阈值 | 软限制 |
| `semantic_compressor.min_messages_to_compress` | `8` | 最少消息数触发 | 软限制 |
| `tool_merge.enabled` | `True` | 工具合并开关 | 软限制 |
| `tool_merge.max_batch_size` | `3` | 合批最大数量 | 软限制 |

---

## 不可配置的内部限制

以下限制为代码内部参数，暂不支持 YAML 配置：

| 参数 | 默认值 | 源码位置 | 说明 |
|------|--------|---------|------|
| `Budget.max_tokens` | `100000` | `nano_agent/agent/budget.py` | 全会话 Token 总量上限 |
| `Budget.max_tool_calls` | `50` | `nano_agent/agent/budget.py` | 全会话工具调用上限 |
| `_duplicate_threshold` | `3` | `nano_agent/agent/duplicate.py` → `DuplicateDetector` | 重复调用阻断阈值（已可配置：`smart_optimization.duplicate_threshold`） |
| AnthropicLLM `max_tokens` | `4096` | `nano_agent/llm/anthropic.py` | Anthropic 单次响应上限 |
| Shell timeout | `30s` | `nano_agent/tools/builtin/shell.py` | Shell 命令超时 |
| Python timeout | `30s` | `nano_agent/tools/builtin/python_executor.py` | Python 执行超时 |
| Web search timeout | `15s` | `nano_agent/tools/builtin/web_search.py` | Web 搜索超时 |
| Git status timeout | `5s` | `nano_agent/agent/git_manager.py` | Git 状态命令超时 |
| Git commit timeout | `10s` | `nano_agent/agent/git_manager.py` | Git 提交命令超时 |