# NanoAgent 代码更新后固定更新清单

> 基于 git 历史分析，整理出每次代码更新后需要检查和更新的固定内容。

---

## 一、版本发布时必更新

当发布新版本（如 v0.7.x → v0.7.y）时，以下文件**必须同步更新**：

| 文件 | 更新内容 | 检查命令 |
|------|----------|----------|
| `pyproject.toml` | `version = "x.y.z"` | `grep "^version" pyproject.toml` |
| `nano_agent/__init__.py` | `__version__ = "x.y.z"` | `grep "__version__" nano_agent/__init__.py` |
| `ROADMAP.md` | 标记版本完成状态、更新版本规划 | 检查版本章节 |
| `docs/api.md` | 新增 API 文档（如有新功能） | 检查是否需要补充 |

**注意**：`pyproject.toml` 和 `__init__.py` 的版本号必须一致！

---

## 二、新增功能时必更新

### 2.1 配置相关链路

新增配置项时，按顺序检查：

```
1. config/schema.py        → 添加配置定义
2. config/loader.py        → 解析新配置字段 + save() 序列化
3. cli/main.py _show_config() → 显示新配置
4. cli/main.py _init_config_file() → 保存默认值
5. core/builder.py create_agent() → 使用新配置
```

**常见遗漏**：
- 配置添加了但忘记在 `_show_config()` 显示
- 核心模块实现了但忘记在 `create_agent()` 调用
- `config/loader.py` 添加了解析但忘记 `save()` 序列化

### 2.2 CLI 命令相关

新增 CLI 命令或斜杠命令时：

```
1. cli/main.py _show_help() → 更新帮助文本
2. docs/api.md             → 添加命令文档
3. docs/tutorial.md        → 更新使用教程（如影响用户工作流）
```

### 2.3 接口扩展

给基类添加新方法时：

```
1. 列出所有子类: grep -r "class.*BaseX" nano_agent/
2. 逐个检查实现
3. 添加接口一致性测试: tests/test_*_interface.py
4. 测试所有组合场景
```

---

## 三、测试相关

### 3.1 新增测试后

```
tests/test_cases.xlsx → 补充测试类、测试点、测试内容
```

### 3.2 BUG 修复后

```
1. 补充回归测试（防止再次出现）
2. 更新 BUGLIST.md（记录复盘经验）
3. 检查测试覆盖率
```

---

## 四、文档更新矩阵

| 变更类型 | CLAUDE.md | ROADMAP.md | BUGLIST.md | docs/api.md | docs/tutorial.md | docs/architecture.md | docs/constraints.md |
|----------|-----------|------------|------------|-------------|------------------|---------------------|---------------------|
| 新版本发布 | - | ✅ 标记完成 | - | ✅ 如有新API | - | - | - |
| 新功能 | - | ✅ 规划/记录 | - | ✅ | ✅ 如影响工作流 | ✅ 新组件/流程 | ✅ 新约束/限制 |
| BUG修复 | - | - | ✅ 复盘记录 | - | - | - | - |
| 架构变更 | ✅ 更新架构图 | ✅ | - | ✅ | - | ✅ 更新架构图 | - |
| 配置变更 | ✅ 更新配置说明 | - | - | ✅ | - | - | ✅ 新约束项 |
| CLI命令变更 | ✅ 更新命令表 | - | - | ✅ | ✅ | - | - |
| 新终止/检测机制 | - | ✅ | - | ✅ 枚举+API | ✅ FAQ | ✅ 流程图 | ✅ 硬限制+交互图 |

---

## 五、提交前检查清单

```bash
# 1. 运行测试
pytest tests/ -v

# 2. 检查覆盖率（修复BUG或新增功能时）
python tests/run_tests.py --coverage

# 3. 检查版本号一致性
grep "^version" pyproject.toml && grep "__version__" nano_agent/__init__.py

# 4. 格式化代码
black .
```

---

## 六、快速检查脚本

```bash
#!/bin/bash
# check-version.sh - 检查版本一致性

PY_VER=$(grep "^version" pyproject.toml | head -1 | cut -d'"' -f2)
INIT_VER=$(grep "__version__" nano_agent/__init__.py | cut -d'"' -f2)

if [ "$PY_VER" != "$INIT_VER" ]; then
    echo "❌ 版本不一致: pyproject.toml=$PY_VER, __init__.py=$INIT_VER"
    exit 1
else
    echo "✅ 版本一致: $PY_VER"
fi
```

---

## 七、历史数据参考

基于 git 历史统计，更新频率最高的文件：

| 排名 | 文件 | 更新次数 | 说明 |
|------|------|----------|------|
| 1 | `nano_agent/cli/main.py` | 93 | 核心入口，几乎每次都改 |
| 2 | `ROADMAP.md` | 47 | 版本规划，每次版本都更新 |
| 3 | `nano_agent/agent/react.py` | 37 | 核心逻辑 |
| 4 | `nano_agent/config/schema.py` | 27 | 配置定义 |
| 5 | `CLAUDE.md` | 19 | 开发指南 |
| 6 | `pyproject.toml` | 11 | 版本号 |
| 7 | `docs/api.md` | 11 | API文档 |
| 8 | `BUGLIST.md` | 7 | BUG记录 |

---

## 八、自动化检查（pre-commit hooks）

已通过 pre-commit 框架实现以下自动检查，`git commit` 时自动运行，失败则阻止提交：

| Hook ID | 脚本 | 检查内容 |
|---------|------|----------|
| `check-version-consistency` | `scripts/check_version_consistency.sh` | `pyproject.toml` 和 `__init__.py` 版本号一致 |
| `check-doc-updates` | `scripts/check_doc_updates.sh` | `schema.py` 变更时 `docs/` 文档也需更新 |
| `check-test-cases` | `scripts/check_test_cases.sh` | 新增测试文件时 `test_cases.xlsx` 也需更新 |
| `check-config-chain` | `scripts/check_config_chain.sh` | `schema.py` 新增字段时 `loader.py` 解析+保存也需更新 |
| `black` | `black` | Python 代码格式化 |

**安装方式**：

```bash
pip install pre-commit
pre-commit install
```

**手动运行**：

```bash
pre-commit run --all-files           # 运行所有 hook
pre-commit run check-version-consistency --all-files  # 运行单个 hook
```
