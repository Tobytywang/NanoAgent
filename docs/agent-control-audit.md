# Agent 管控体系审计

> **理论框架**: 四层 16 控制点 — 从输入到运行兜底的完备 Agent 管控体系

## 理论框架概述

### LLM 本质定义

LLM 是在海量文本上通过统计学习构建的高维概率生成模型，将输入文本映射至高维语义空间，依托训练习得的全域语言分布做概率化模式重组与采样，逐 token 解码生成自然语言。

**工程简化**: 高维空间模式匹配引擎 `Y = f(X)`（模型权重固定，仅可通过外围管控优化输出）。

### 四层管控体系

```
┌─────────────────────────────────────────────────────────────┐
│                    第一层：Input 输入端                       │
│  Anchor 锚定 → Memory 记忆 → Prune 剪枝 → Sanitize 净化      │
├─────────────────────────────────────────────────────────────┤
│                   第二层：Latent 隐计算                       │
│  Route 路由 → Atomize 原子化 → Orchestrate 编排 → Monitor 监控│
├─────────────────────────────────────────────────────────────┤
│                    第三层：Output 输出端                      │
│  Format 格式化 → Guard 护栏 → Validate 校验 → Feedback 反馈  │
├─────────────────────────────────────────────────────────────┤
│                   第四层：Runtime 运行兜底                    │
│  ToolGuard 工具防护 → Stability 稳控 → MemoryGC 记忆迭代     │
│                    → Rollback&Audit 回溯兜底                 │
└─────────────────────────────────────────────────────────────┘
```

---

## NanoAgent 实现审计

### 审计结果矩阵

| 层级 | 控制点 | 状态 | 核心实现文件 |
|------|--------|------|--------------|
| **Input** | 1. Anchor 锚定 | ✅ 完整 | `prompt_builder.py`, `prompt_modules.py` |
| | 2. Memory 记忆 | ✅ 完整 | `memory/{base,short_term,long_term,hybrid}.py` |
| | 3. Prune 剪枝 | ✅ 完整 | `context.py`, `compressor.py`, `semantic_compressor.py` |
| | 4. Sanitize 净化 | ✅ 完整 | `sanitizer.py`, `output_guard.py`, `harmful_filter.py` |
| **Latent** | 5. Route 路由 | ✅ 完整 | `router.py`, `intent_detector.py` |
| | 6. Atomize 原子化 | ✅ 完整 | `orchestrator.py`, `plan_tools.py` |
| | 7. Orchestrate 编排 | ✅ 完整 | `orchestrator.py`, `subsystems.py` |
| | 8. Monitor 监控 | ✅ 完整 | `stall_detector.py`, `confidence.py`, `prejudgment.py` |
| **Output** | 9. Format 格式化 | ✅ 完整 | `standard_output.py`, `result_summarizer.py` |
| | 10. Guard 护栏 | ✅ 完整 | `output_guard.py`, `harmful_filter.py`, `middleware.py` |
| | 11. Validate 校验 | ✅ 完整 | `result_validator.py` |
| | 12. Feedback 反馈 | ✅ 完整 | `feedback_loop.py` |
| **Runtime** | 13. ToolGuard 工具防护 | ✅ 完整 | `resource_limiter.py`, `middleware.py` |
| | 14. Stability 稳控 | ✅ 完整 | `rate_limiter.py`, `circuit_breaker.py`, `retry.py`, `token_budget.py` |
| | 15. MemoryGC 记忆迭代 | ✅ 完整 | `gc.py`, `long_term.py` |
| | 16. Rollback&Audit 回溯兜底 | ✅ 完整 | `snapshot.py`, `consecutive_failure_detector.py` |

**统计**: 16/16 完整

---

## 各控制点详细审计

### 第一层：Input 输入端

#### 1. Anchor 锚定 ✅ 完整

**定义**: 角色、规则、范式预埋，锁定输出基准

**实现**:
- `PromptBuilder` 按固定顺序组装 system prompt：角色定义 → 能力说明 → 工具列表 → 记忆注入 → 当前任务
- `prompt_modules.py` 将 prompt 拆为可插拔 module（identity / capability / constraint / style）
- 每轮对话前 `PromptBuilder.build()` 重新渲染，确保锚定不被上下文覆盖

**关键文件**: `nano_agent/agent/prompt_builder.py`, `nano_agent/agent/prompts.py`, `nano_agent/agent/prompt_modules.py`

---

#### 2. Memory 记忆 ✅ 完整

**定义**: 长短时记忆、业务知识库注入补全信息

**实现**:
- `MemoryBase` 定义 `store()` / `recall()` / `delete()` 抽象接口
- `ShortTermMemory` 基于 token 预算的滑动窗口 + 时间戳排序
- `LongTermMemory` 基于 embedding 相似度检索 + 持久化存储
- `HybridMemory` 同时查询短时/长时，按相关度合并去重；按重要性阈值自动分流
- `memory_tools.py` 暴露工具给 agent 调用，形成记忆闭环

**关键文件**: `nano_agent/memory/{base,short_term,long_term,hybrid}.py`, `nano_agent/tools/builtin/memory_tools.py`

---

#### 3. Prune 剪枝 ✅ 完整

**定义**: 上下文裁剪，解决窗口与 Token 超限问题

**实现**:
- `ContextManager.manage()` 每轮计算 token 占用，超出预算触发压缩管线
- 压缩管线：`Compressor`（规则层）→ `SemanticCompressor`（语义层）
- `Compressor`: 移除冗余空白、折叠重复对话、截断超长工具输出、移除低优先级历史
- `SemanticCompressor`: 对保留轮次做 LLM 摘要压缩
- `TokenBudget` 将上下文窗口分配为 system_prompt / memory / history / working_output 四段

**关键文件**: `nano_agent/agent/context.py`, `nano_agent/agent/compressor.py`, `nano_agent/agent/semantic_compressor.py`, `nano_agent/agent/token_budget.py`

---

#### 4. Sanitize 净化 ✅ 完整

**定义**: 输入清洗、脱敏、防恶意注入

**实现**:
- `InputSanitizer` 三阶段处理管线：长度校验 → PII 脱敏 → 注入检测
- `_check_length()`: 超长输入截断或拒绝，单行长度限制
- `_check_format()`: 拒绝空字节，剥离控制字符
- `_check_injection()`: 硬性拦截 "ignore previous" / jailbreak 模板等特征模式（中英文）
- `PIIDesensitizer`: 手机号/身份证/邮箱/API key 等敏感信息自动脱敏（可选，默认关闭）
- 注入匹配始终拒绝（硬门控），PII 和长度可配置动作

**关键文件**: `nano_agent/agent/sanitizer.py`

---

### 第二层：Latent 隐计算

#### 5. Route 路由 ✅ 完整

**定义**: 意图分类，任务分流分发

**实现**:
- `IntentDetector.detect()` 返回 `IntentResult`（intent_type, confidence, suggested_tools）
- 意图类型：conversational / tool_call / planning / clarification / dangerous
- `Router.route()` 根据意图选择执行路径
- 低 confidence 自动降级到 clarification

**关键文件**: `nano_agent/agent/router.py`, `nano_agent/agent/intent_detector.py`

---

#### 6. Atomize 原子化 ✅ 完整

**定义**: 复杂任务拆解为最小可执行单元

**实现**:
- `Orchestrator.decompose()` 将任务拆解为 `List[SubTask]`
- 每个 `SubTask` 包含：description, dependencies, required_tools, estimated_complexity
- `Orchestrator.execute_plan()` 按拓扑序执行，支持并行无依赖子任务
- `plan_tools.py` 暴露 `create_plan` / `update_plan` 工具
- `AutoPlanTool` 在复杂度超阈值时自动触发拆解

**关键文件**: `nano_agent/agent/orchestrator.py`, `nano_agent/tools/builtin/plan_tools.py`, `nano_agent/tools/builtin/auto_plan.py`

---

#### 7. Orchestrate 编排 ✅ 完整

**定义**: 多步骤、多工具时序与状态管理

**实现**:
- `Orchestrator` 管理 plan 生命周期：decompose → schedule → execute → verify → complete
- `Subsystems` 统一注入各子系统（memory, router, confirmation 等）
- 失败子任务可重试，重试失败后标记 blocked 并调整依赖
- 支持跨步骤上下文传递

**关键文件**: `nano_agent/agent/orchestrator.py`, `nano_agent/agent/subsystems.py`

---

#### 8. Monitor 监控 ✅ 完整

**定义**: 推理过程纠偏、异常分支拦截

**实现**:
- `StallDetector` 检测三种卡死模式：重复循环、空转、死胡同
- `ConfidenceTracker` 追踪每步置信度，连续下降触发 early stop
- `Prejudgment` 预估任务可行性和风险，低可行性提前阻断
- 协同：prejudgment 预判 → 执行中 confidence 追踪 → stall_detector 兜底

**关键文件**: `nano_agent/agent/stall_detector.py`, `nano_agent/agent/confidence.py`, `nano_agent/agent/prejudgment.py`

---

### 第三层：Output 输出端

#### 9. Format 格式化 ✅ 完整

**定义**: 强制结构化输出，适配机器解析

**实现**:
- `StandardOutput` 统一工具返回值为 `{status, data, message, metadata}`
- `OutputSimplifier` 对冗长输出做摘要简化
- `ResultSummarizer` 生成最终结构化摘要
- `StyleModule` 约束输出格式（Markdown / JSON）

**关键文件**: `nano_agent/tools/standard_output.py`, `nano_agent/agent/output_simplifier.py`, `nano_agent/agent/result_summarizer.py`

---

#### 10. Guard 护栏 ✅ 完整

**定义**: 安全与业务规则拦截，禁止高危执行

**实现**:
- `ToolMiddleware` 提供 before/after hook 框架
- `ConfirmationManager` 对 `requires_confirmation=True` 的工具强制确认
- `shell.py` 对危险命令做黑名单过滤
- `OutputGuard` 输出敏感信息拦截：检测 password / private_key / connection_string + PII 类型，三种动作（mask/block/warn）
- `HarmfulContentFilter` 有害内容过滤：violence / hate / dangerous / illegal 四类，中英文模式，可选（默认关闭）
- `SensitiveOutputMiddleware` + `HarmfulContentMiddleware` 中间件级集成

**关键文件**: `nano_agent/agent/output_guard.py`, `nano_agent/agent/harmful_filter.py`, `nano_agent/tools/middleware.py`

---

#### 11. Validate 校验 ✅ 完整

**定义**: 格式、内容合理性校验与自动修复

**实现**:
- `StandardOutput` 自带格式校验
- `ConfidenceTracker` 评估结果置信度
- `EstimationAudit` 记录预估偏差
- `ResultValidator` 结果正确性验证：file_exists（文件路径存在性）/ code_syntax（Python/JSON/YAML 语法）/ command_success（命令声称成功但退出码非零矛盾检测）
- Schema-based 校验：`validate_tool_output()` 对 `StandardToolOutput` 按格式 schema 校验
- 自定义验证器支持（`custom_validators` 列表）
- 可选功能，默认关闭

**关键文件**: `nano_agent/agent/result_validator.py`

---

#### 12. Feedback 反馈 ✅ 完整

**定义**: 执行结果闭环，迭代优化后续推理

**实现**:
- `StallDetector` 检测卡死后触发预设恢复策略
- `EstimationAudit` 记录预估偏差
- `tracker.py` 记录完整执行轨迹
- `FeedbackLoop` 偏差信号回流：`check_deviation()` 追踪偏差警告次数，注入纠正提示到 LLM 上下文，可配置冷却期
- 自纠正循环：`should_retry()` 检查 ResultValidator 阻塞结果 + 剩余纠正次数，`build_correction_feedback()` 构造结构化反馈，`record_correction_attempt()` 追踪尝试次数
- 两种偏差提示模板（高估/低估）轮换避免重复

**关键文件**: `nano_agent/agent/feedback_loop.py`

---

### 第四层：Runtime 运行兜底

#### 13. ToolGuard 工具防护 ✅ 完整

**定义**: 接口容错、参数合法性、调用异常治理

**实现**:
- `ToolBase` 定义工具元信息（name, description, requires_confirmation, dangerous）
- `ToolMiddleware` 提供 before/after hook
- `shell.py` 对 shell 工具做危险命令黑名单
- `ToolTimeoutWrapper` 工具执行超时：`signal.setitimer` (Unix/macOS) / `ThreadPoolExecutor` (fallback)，支持单工具超时覆盖
- `ToolRateLimiter` 工具调用频率限制：per-tool + global 双层令牌桶，非阻塞式返回
- `SensitiveOutputMiddleware` + `HarmfulContentMiddleware` 中间件级安全扫描

**未实现**:
- ❌ 工具沙箱隔离（进程级隔离，实现成本高，可选）

**关键文件**: `nano_agent/tools/resource_limiter.py`, `nano_agent/tools/middleware.py`

---

#### 14. Stability 稳控 ✅ 完整

**定义**: 限流、熔断、降级、资源配额管控

**实现**:
- `TokenBucketRateLimiter` LLM API 调用频率限制：令牌桶算法，可配置 requests_per_minute + burst，阻塞式等待
- `CircuitBreaker` 熔断器：三种触发条件（超大响应/重复工具调用/卡死检测），触发后从 AUTO 降级到 SUPERVISED 模式，`reset()` 恢复
- `with_retry()` 指数退避重试：处理 429/500/502/503/504 + Anthropic SDK 异常 + 网络错误，支持 jitter
- `TokenBudget` Token 消耗硬上限：`is_exhausted()` / `should_summarize()` 多级预警（50%/30%/20%/10%），耗尽触发强制摘要

**关键文件**: `nano_agent/llm/rate_limiter.py`, `nano_agent/agent/circuit_breaker.py`, `nano_agent/llm/retry.py`, `nano_agent/agent/token_budget.py`

---

#### 15. MemoryGC 记忆迭代 ✅ 完整

**定义**: 过期知识淘汰、知识库动态更新，对抗知识漂移

**实现**:
- `ShortTermMemory` 基于 token 预算的 FIFO 淘汰
- `HybridMemory.store()` 按重要性分流
- `ContextManager` 剪枝时淘汰低相关性记忆
- `compute_decay_weight()` 指数衰减：`importance * e^(-lambda * age_days)`，可配置半衰期
- `MemoryGC` Phase 1 衰减清理：低于 `gc_threshold` 的条目被回收
- `LongTermMemory.add()` 记忆去重/合并：关键词 Jaccard 相似度 > 0.7 触发合并，更新 mention_count / last_mentioned_at / keywords 取并集 / importance 取最大
- `MemoryGC` Phase 2 长时记忆淘汰：超 `eviction_max_entries` 时淘汰最低 effective_weight 条目，保护类别 + 提及计数保护

**关键文件**: `nano_agent/memory/gc.py`, `nano_agent/memory/long_term.py`

---

#### 16. Rollback & Audit 回溯兜底 ✅ 完整

**定义**: 高危操作回滚、全链路审计溯源

**实现**:
- `UndoManager` 提供操作级撤销，支持 `undo()` 和 `undo_all()`
- `GitManager` 对文件操作提供 Git 级别回滚
- `tracker.py` 记录完整执行轨迹
- `metrics.py` 采集执行指标
- `SnapshotManager` 全局状态快照：捕获 12 个子系统状态并序列化为 JSON，支持 save / restore / list / delete，可配置自动存档
- `AuditLogEntry` 审计-回滚关联：`rollback_from_audit()` 从审计日志直接触发回滚，每次操作记录 audit_id + snapshot_id + trigger + outcome
- `ConsecutiveFailureDetector` 条件触发自动回滚：连续工具失败 N 次自动回滚到最近检查点，记录审计日志

**关键文件**: `nano_agent/agent/snapshot.py`, `nano_agent/agent/consecutive_failure_detector.py`

---

## 全部 16 控制点实现细节

> 每个功能子项标注实现版本；未实现的标注计划版本（对照 ROADMAP），暂无规划的留空

---

### 第一层：Input 输入端

#### 1. Anchor 锚定

| # | 功能子项 | 版本 |
|---|---------|------|
| 1.1 | **模块化 Prompt 系统 (PromptBuilder)** | |
| 1.1.1 | 17 个可组合 PromptModule | v0.7.6 |
| 1.1.2 | 风格预设 (concise/standard/detailed) | v0.7.6 |
| 1.1.3 | 稳定前缀/动态后段分离 | v0.7.7 |
| 1.1.4 | 按 context 长度自动降级 (detailed→standard) | v0.7.8 |
| 1.1.5 | 模块依赖声明与排序 | v0.7.6 |
| 1.2 | **动态模块激活** | |
| 1.2.1 | 意图关键词检测 → 按需加载模块 | v0.7.8 |
| 1.2.2 | 非关键模块条件跳过 | v0.7.8 |
| 1.3 | **Prompt 缓存优化** | |
| 1.3.1 | SHA256 缓存键生成 | v0.7.7 |
| 1.3.2 | 稳定前缀缓存命中 | v0.7.7 |
| 1.4 | **Excel 配置管理** | |
| 1.4.1 | 测试用例 Excel 加载 | v0.7.6 |
| 1.4.2 | 自动配置注入 | v0.7.6 |

---

#### 2. Memory 记忆

| # | 功能子项 | 版本 |
|---|---------|------|
| 2.1 | **抽象接口定义 (BaseMemory)** | |
| 2.1.1 | store() / recall() / delete() / clear() | v0.1.0 |
| 2.1.2 | get_relevant() 相关性检索 | v0.2.0 |
| 2.1.3 | stable_system_prompt() 稳定提示词接口 | v0.7.7 |
| 2.2 | **短时记忆 (ShortTermMemory)** | |
| 2.2.1 | 基于 token 预算的滑动窗口 | v0.1.0 |
| 2.2.2 | 时间戳排序 | v0.1.0 |
| 2.2.3 | FIFO 淘汰策略 | v0.1.0 |
| 2.3 | **长时记忆 (LongTermMemory)** | |
| 2.3.1 | Embedding 相似度检索 | v0.2.0 |
| 2.3.2 | 持久化存储 (SQLite/File) | v0.2.0 |
| 2.3.3 | 重要性评分 | v0.2.0 |
| 2.3.4 | stable_system_prompt() 实现 | v0.7.7 |
| 2.4 | **混合记忆 (HybridMemory)** | |
| 2.4.1 | 同时查询短时/长时，按相关度合并去重 | v0.5.0 |
| 2.4.2 | 按重要性阈值自动分流 | v0.5.0 |
| 2.4.3 | stable_system_prompt() 实现 | v0.7.7 |
| 2.5 | **记忆工具 (memory_tools.py)** | |
| 2.5.1 | memorize / recall / list_memories / forget | v0.7.0 |
| 2.5.2 | undo 撤销机制 | v0.5.1 |

---

#### 3. Prune 剪枝

| # | 功能子项 | 版本 |
|---|---------|------|
| 3.1 | **上下文管理 (ContextManager)** | |
| 3.1.1 | 每轮 token 占用计算 | v0.6.1 |
| 3.1.2 | 超预算触发压缩管线 | v0.6.1 |
| 3.1.3 | 四段预算分配 (system/memory/history/working) | v0.7.5 |
| 3.1.4 | 预算感知的模块激活/降级 | v0.7.8 |
| 3.2 | **规则层压缩 (Compressor)** | |
| 3.2.1 | 移除冗余空白 | v0.7.3 |
| 3.2.2 | 折叠重复对话 | v0.7.3 |
| 3.2.3 | 截断超长工具输出 | v0.7.3 |
| 3.2.4 | 移除低优先级历史 | v0.7.3 |
| 3.3 | **语义层压缩 (SemanticCompressor)** | |
| 3.3.1 | 九段摘要策略 | v0.6.1 |
| 3.3.2 | LLM 摘要压缩保留轮次 | v0.6.1 |
| 3.3.3 | Embedding 相似度合并历史消息 | v0.7.19 |
| 3.4 | **Token 工具集** | |
| 3.4.1 | Token 估算 (token_utils.py) | v0.6.1 |
| 3.4.2 | base_ratio 首轮偏差修正 | v0.7.18 |
| 3.4.3 | 跨轮 Prompt 缓存命中率追踪 | v0.7.7 |

---

#### 4. Sanitize 净化

| # | 功能子项 | 版本 |
|---|---------|------|
| 4.1 | **Prompt 级软防护** | |
| 4.1.1 | ConstraintModule 安全指令注入 | v0.7.6 |
| 4.1.2 | 确认拦截 (ConfirmationManager) | v0.6.4 |
| 4.2 | **输入清洗层** | |
| 4.2.1 | Prompt injection 特征过滤 | v0.8.3 |
| 4.2.2 | 输入长度/格式校验 | v0.8.3 |
| 4.2.3 | PII 脱敏 | v0.8.4 (可选) |
| 4.3 | **输入净化策略** | |
| 4.3.1 | 超长输入截断 | (并入 v0.8.3) |

---

### 第二层：Latent 隐计算

#### 5. Route 路由

| # | 功能子项 | 版本 |
|---|---------|------|
| 5.1 | **查询复杂度分类** | |
| 5.1.1 | simple / moderate / complex 三级分类 | v0.7.5 |
| 5.1.2 | 复杂度 → Prompt 风格联动 (simple→concise) | v0.7.16 |
| 5.2 | **意图检测 (IntentDetector)** | |
| 5.2.1 | 关键词模式匹配 | v0.7.8 |
| 5.2.2 | 意图类型 (conversational/tool_call/...) | v0.7.8 |
| 5.2.3 | 低 confidence 自动降级到 clarification | v0.7.8 |
| 5.2.4 | 意图 → 动态模块激活 | v0.7.8 |
| 5.3 | **预判机制 (Prejudgment)** | |
| 5.3.1 | 任务可行性预估 | v0.7.14 |
| 5.3.2 | 低可行性提前阻断 | v0.7.14 |
| 5.4 | **执行路径选择** | |
| 5.4.1 | Router.route() 根据意图选择路径 | v0.7.5 |

---

#### 6. Atomize 原子化

| # | 功能子项 | 版本 |
|---|---------|------|
| 6.1 | **任务拆解 (Orchestrator)** | |
| 6.1.1 | decompose() 拆解为 List[SubTask] | v0.6.0 |
| 6.1.2 | SubTask 定义 (description/dependencies/...) | v0.6.0 |
| 6.1.3 | 拓扑序执行 + 无依赖子任务并行 | v0.6.0 |
| 6.2 | **计划工具 (plan_tools.py)** | |
| 6.2.1 | create_plan / update_plan 工具 | v0.6.2 |
| 6.2.2 | Agent 可自主调用计划工具 | v0.6.2 |
| 6.3 | **自动规划 (AutoPlanTool)** | |
| 6.3.1 | 复杂度超阈值自动触发拆解 | v0.6.2 |
| 6.3.2 | 拆解结果注入上下文 | v0.6.2 |
| 6.4 | **上下文传递** | |
| 6.4.1 | 跨步骤上下文传递 | v0.6.0 |

---

#### 7. Orchestrate 编排

| # | 功能子项 | 版本 |
|---|---------|------|
| 7.1 | **Plan 生命周期管理** | |
| 7.1.1 | decompose → schedule → execute → verify | v0.6.0 |
| 7.1.2 | complete 全状态流转 | v0.6.0 |
| 7.2 | **子系统注入 (Subsystems)** | |
| 7.2.1 | 统一注入 memory/router/confirmation/... | v0.7.19 |
| 7.2.2 | 解耦子系统依赖 | v0.7.19 |
| 7.3 | **预算感知执行** | |
| 7.3.1 | TokenBudget 预算分配与追踪 | v0.7.5 |
| 7.3.2 | Budget 多维约束 (token/复杂度/轮次) | v0.6.0 |
| 7.3.3 | 复杂度预算分配 | v0.7.16 |
| 7.4 | **失败处理** | |
| 7.4.1 | 失败子任务重试 | v0.6.0 |
| 7.4.2 | 重试失败 → 标记 blocked + 调整依赖 | v0.6.0 |
| 7.5 | **并发控制** | |
| 7.5.1 | 无依赖子任务并行调度 | v0.6.0 |

---

#### 8. Monitor 监控

| # | 功能子项 | 版本 |
|---|---------|------|
| 8.1 | **卡死检测 (StallDetector)** | |
| 8.1.1 | 重复循环检测 | v0.7.16 |
| 8.1.2 | 空转检测 | v0.7.16 |
| 8.1.3 | 死胡同检测 | v0.7.16 |
| 8.1.4 | 检测后触发恢复策略 | v0.7.16 |
| 8.2 | **置信度追踪 (ConfidenceTracker)** | |
| 8.2.1 | 每步置信度评估 | v0.7.5 |
| 8.2.2 | 连续下降触发 early stop | v0.7.5 |
| 8.3 | **预判机制 (Prejudgment)** | |
| 8.3.1 | 任务可行性预估 | v0.7.14 |
| 8.3.2 | 低可行性提前阻断 | v0.7.14 |
| 8.4 | **重复检测 (DuplicateDetector)** | |
| 8.4.1 | 相似工具调用去重 | v0.7.10 |
| 8.5 | **协同机制** | |
| 8.5.1 | prejudgment 预判 → confidence 追踪 → stall 兜底 | v0.7.16 |

---

### 第三层：Output 输出端

#### 9. Format 格式化

| # | 功能子项 | 版本 |
|---|---------|------|
| 9.1 | **标准化输出 (StandardOutput)** | |
| 9.1.1 | 统一返回值 {status/data/message/metadata} | v0.7.15 |
| 9.1.2 | 格式校验 | v0.7.15 |
| 9.2 | **输出精简 (OutputSimplifier)** | |
| 9.2.1 | 冗长输出摘要简化 | v0.7.15 |
| 9.2.2 | 按工具类型定制精简策略 | v0.7.15 |
| 9.2.3 | 激进精简模式 (concise 风格) | v0.7.15 |
| 9.3 | **结果摘要 (ResultSummarizer)** | |
| 9.3.1 | 执行结束生成结构化摘要 | v0.7.2 |
| 9.3.2 | 多工具结果汇总 | v0.7.2 |
| 9.4 | **风格约束** | |
| 9.4.1 | StyleModule 约束输出格式 (Markdown/JSON) | v0.7.6 |

---

#### 10. Guard 护栏

| # | 功能子项 | 版本 |
|---|---------|------|
| 10.1 | **中间件框架** | |
| 10.1.1 | ToolMiddleware before/after hook | v0.6.4 |
| 10.1.2 | requires_confirmation 强制确认 | v0.6.4 |
| 10.2 | **危险命令过滤** | |
| 10.2.1 | Shell 工具黑名单过滤 | v0.6.4 |
| 10.3 | **输出安全过滤** | |
| 10.3.1 | 敏感信息泄露拦截 (API key/密码/token) | v0.8.5 |
| 10.3.2 | 有害内容过滤 | v0.8.6 (可选) |
| 10.4 | **安全规则扩充** | |
| 10.4.1 | 当前仅确认拦截，需补充自动拦截规则 | v0.8.5 |

---

#### 11. Validate 校验

| # | 功能子项 | 版本 |
|---|---------|------|
| 11.1 | **格式校验** | |
| 11.1.1 | StandardOutput 格式校验 | v0.7.15 |
| 11.1.2 | 工具返回值类型检查 | v0.7.15 |
| 11.2 | **置信度评估** | |
| 11.2.1 | 结果置信度评分 | v0.7.5 |
| 11.3 | **预估偏差记录** | |
| 11.3.1 | EstimationAudit 偏差追踪 | v0.7.18 |
| 11.4 | **业务语义校验** | |
| 11.4.1 | 结果正确性验证 hook | v0.8.7 |
| 11.4.2 | Schema-based 校验 | v0.8.8 |
| 11.5 | **自动修复** | |
| 11.5.1 | 校验失败自动修复 | (并入 v0.8.8) |

---

#### 12. Feedback 反馈

| # | 功能子项 | 版本 |
|---|---------|------|
| 12.1 | **异常检测** | |
| 12.1.1 | StallDetector 检测卡死 → 触发恢复策略 | v0.7.16 |
| 12.1.2 | EstimationAudit 记录预估偏差 | v0.7.18 |
| 12.2 | **执行轨迹记录** | |
| 12.2.1 | tracker.py 完整执行轨迹 | v0.4.0 |
| 12.2.2 | metrics.py 执行指标采集 | v0.4.0 |
| 12.3 | **反馈闭环** | |
| 12.3.1 | 偏差信号回流到执行策略层 | v0.8.9 |
| 12.3.2 | 自纠正循环 (执行→校验→偏差→调整→重执行) | v0.8.9 |
| 12.4 | **动态调节** | |
| 12.4.1 | 基于反馈的动态策略调节 | (并入 v0.8.9) |

---

### 第四层：Runtime 运行兜底

#### 13. ToolGuard 工具防护

| # | 功能子项 | 版本 |
|---|---------|------|
| 13.1 | **工具元信息** | |
| 13.1.1 | ToolBase 元信息定义 (name/description/...) | v0.1.0 |
| 13.1.2 | requires_confirmation 标记 | v0.6.4 |
| 13.1.3 | dangerous 标记 | v0.6.4 |
| 13.2 | **中间件防护** | |
| 13.2.1 | ToolMiddleware before/after hook | v0.6.4 |
| 13.2.2 | Shell 工具危险命令黑名单 | v0.6.4 |
| 13.3 | **资源限制** | |
| 13.3.1 | 工具执行超时上限 | v0.8.10 |
| 13.3.2 | 工具调用频率限制 | v0.8.10 |
| 13.4 | **沙箱隔离** | |
| 13.4.1 | 进程级隔离 | v0.8.11 (可选) |

---

#### 14. Stability 稳控

| # | 功能子项 | 版本 |
|---|---------|------|
| 14.1 | **Token 预算 (间接关联)** | |
| 14.1.1 | TokenBudget 预算分配与追踪 | v0.7.5 |
| 14.2 | **API 调用管控** | |
| 14.2.1 | LLM API 调用频率限制 | v0.8.1 |
| 14.2.2 | 熔断器 (连续失败后自动熔断) | v0.8.2 |
| 14.2.3 | 指数退避重试 | v0.8.0 |
| 14.3 | **成本控制** | |
| 14.3.1 | Token 消耗硬上限 | v0.8.0 |

---

#### 15. MemoryGC 记忆迭代

| # | 功能子项 | 版本 |
|---|---------|------|
| 15.1 | **短时记忆淘汰** | |
| 15.1.1 | 基于 token 预算的 FIFO 淘汰 | v0.1.0 |
| 15.1.2 | 时间戳排序 | v0.1.0 |
| 15.2 | **记忆分流** | |
| 15.2.1 | HybridMemory 按重要性自动分流 | v0.5.0 |
| 15.3 | **上下文剪枝** | |
| 15.3.1 | ContextManager 剪枝时淘汰低相关性记忆 | v0.6.1 |
| 15.4 | **记忆衰减与去重** | |
| 15.4.1 | 时间衰减权重 | v0.8.12 |
| 15.4.2 | 记忆去重/合并 | v0.8.12 |
| 15.4.3 | 长时记忆淘汰 (低重要性/过期清理) | v0.8.13 |
| 15.5 | **知识漂移对抗** | |
| 15.5.1 | 过期知识主动更新 | (并入 v0.8.13) |

---

#### 16. Rollback & Audit 回溯兜底

| # | 功能子项 | 版本 |
|---|---------|------|
| 16.1 | **操作级撤销** | |
| 16.1.1 | UndoManager undo() / undo_all() | v0.5.1 |
| 16.1.2 | 记忆操作即时撤销 | v0.5.1 |
| 16.2 | **Git 级回滚** | |
| 16.2.1 | GitManager 文件操作 Git 回滚 | v0.6.5 |
| 16.3 | **执行审计** | |
| 16.3.1 | tracker.py 完整执行轨迹 | v0.4.0 |
| 16.3.2 | metrics.py 执行指标采集 | v0.4.0 |
| 16.4 | **全局快照** | |
| 16.4.1 | 全局状态快照保存/恢复 | v0.8.14 |
| 16.4.2 | 审计-回滚关联 | v0.8.15 |
| 16.5 | **自动回滚** | |
| 16.5.1 | 条件触发自动回滚 (连续失败 N 次) | v0.8.15 |

---

## 工作项清单（23 项）

> 按优先级分组，带编号便于追踪

### ✅ 已完成（22 项）

**P0 - Stability 稳控** (#1-4)

| # | 工作项 | 实现版本 | 核心实现 |
|---|--------|---------|----------|
| 1 | LLM API 限流器 | v0.8.1 | `llm/rate_limiter.py` — TokenBucketRateLimiter |
| 2 | 熔断器 | v0.8.2 | `agent/circuit_breaker.py` — 三触发条件 + AUTO→SUPERVISED 降级 |
| 3 | 指数退避重试 | v0.8.0 | `llm/retry.py` — 429/5xx + SDK 异常 + jitter |
| 4 | Token 消耗硬上限 | v0.8.0 | `agent/token_budget.py` — is_exhausted() + 多级预警 |

**P1 - Safety 安全** (#5-10)

| # | 工作项 | 实现版本 | 核心实现 |
|---|--------|---------|----------|
| 5 | Prompt injection 特征过滤 | v0.8.3 | `agent/sanitizer.py` — 硬性拦截中英文注入模式 |
| 6 | 输入长度/格式校验 | v0.8.3 | `agent/sanitizer.py` — 超长截断/拒绝 + 控制字符剥离 |
| 7 | PII 脱敏 | v0.8.4 | `agent/sanitizer.py` — PIIDesensitizer（可选，默认关闭） |
| 8 | 输出敏感信息拦截 | v0.8.5 | `agent/output_guard.py` — password/key/PII 检测 + mask/block/warn |
| 9 | 有害内容过滤 | v0.8.6 | `agent/harmful_filter.py` — violence/hate/dangerous/illegal（可选，默认关闭） |
| 10 | 中间件安全规则扩充 | v0.8.5 | `tools/middleware.py` — SensitiveOutputMiddleware + HarmfulContentMiddleware |

**P2 - Robustness 鲁棒性** (#11-16, #18-20)

| # | 工作项 | 实现版本 | 核心实现 |
|---|--------|---------|----------|
| 11 | 结果正确性验证 hook | v0.8.7 | `agent/result_validator.py` — file_exists/code_syntax/command_success |
| 12 | Schema-based 校验 | v0.8.8 | `agent/result_validator.py` — validate_tool_output() |
| 13 | 偏差信号回流 | v0.8.9 | `agent/feedback_loop.py` — check_deviation() + 纠正提示注入 |
| 14 | 自纠正循环 | v0.8.9 | `agent/feedback_loop.py` — should_retry() + build_correction_feedback() |
| 15 | 工具执行超时 | v0.8.10 | `tools/resource_limiter.py` — ToolTimeoutWrapper (signal/ThreadPool) |
| 16 | 工具调用频率限制 | v0.8.10 | `tools/resource_limiter.py` — ToolRateLimiter (per-tool + global) |
| 18 | 记忆衰减策略 | v0.8.12 | `memory/gc.py` + `memory/long_term.py` — 指数衰减 + 半衰期 |
| 19 | 记忆去重/合并 | v0.8.12 | `memory/long_term.py` — Jaccard > 0.7 合并 + mention_count |
| 20 | 长时记忆淘汰 | v0.8.13 | `memory/gc.py` — Phase 2 容量淘汰 + 保护类别 |

**P3 - Completeness 完备性** (#21-23)

| # | 工作项 | 实现版本 | 核心实现 |
|---|--------|---------|----------|
| 21 | 全局状态快照 | v0.8.14 | `agent/snapshot.py` — 12 子系统状态序列化 + 自动存档 |
| 22 | 审计-回滚关联 | v0.8.15 | `agent/snapshot.py` — AuditLogEntry + rollback_from_audit() |
| 23 | 条件触发自动回滚 | v0.8.15 | `agent/snapshot.py` + `agent/consecutive_failure_detector.py` |

---

### ❌ 未实现（1 项，可选）

**P2 - Robustness 鲁棒性**

| # | 工作项 | 说明 | 复杂度 | 建议位置 |
|---|--------|------|--------|----------|
| 17 | 工具沙箱隔离 | 进程级隔离（实现成本高，可选） | 高 | `nano_agent/tools/sandbox.py` |

---

### 工作项统计

| 优先级 | 工作项编号 | 数量 | 已完成 | 未实现 |
|--------|-----------|------|--------|--------|
| P0 生产必需 | #1-4 | 4 | 4 | 0 |
| P1 安全必需 | #5-10 | 6 | 6 | 0 |
| P2 鲁棒性 | #11-20 | 10 | 9 | 1 (#17 可选) |
| P3 完备性 | #21-23 | 3 | 3 | 0 |
| **合计** | | **23** | **22** | **1** |

---

## 参考链接

- [ROADMAP.md](../ROADMAP.md) - 版本规划
- [BUGLIST.md](../BUGLIST.md) - BUG 记录与经验教训
- [docs/architecture.md](architecture.md) - 架构文档
