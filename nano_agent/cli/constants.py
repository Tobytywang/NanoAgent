"""
CLI 命令常量定义

定义所有交互式命令的字符串常量，避免魔法字符串散布在代码中。
"""


class Commands:
    """交互式命令常量"""

    # 帮助命令
    HELP = {"/?", "/help", "help", "?", "？", "/？"}

    # 退出命令（优雅退出，生成摘要）
    EXIT = {"/exit", "/quit", "/bye"}

    # 直接退出命令（不生成摘要）
    EXIT_DIRECT = {"exit", "quit"}

    # 会话管理
    CLEAR = "/clear"
    UNDO = "/undo"
    SESSIONS = "/sessions"
    HISTORY = "/history"

    # 工具和技能
    TOOLS = "/tools"
    SKILLS = "/skills"
    SKILL = "/skill"

    # 统计和报告
    STATS = "/stats"
    REPORT = "/report"
    USAGE = "/usage"
    CONTEXT = "/context"

    # 配置
    CONFIG = "/config"

    # 记忆
    MEMORY = "/memory"

    # 计划
    PLANS = "/plans"

    # 项目初始化
    INIT = "/init"

    # 名字设置
    SETNAME = "/setname"

    # 熔断器
    AUTO = "/auto"

    # 输出控制
    VERBOSE = "/verbose"


class CommandPrefix:
    """命令前缀（用于带参数的命令）"""

    STATS = "/stats"
    CONFIG = "/config "
    MEMORY = "/memory"
    SKILL = "/skill "
    SETNAME = "/setname"
    PLAN = "/plan "
    HISTORY = "/history"
    SNAPSHOT = "/snapshot"
