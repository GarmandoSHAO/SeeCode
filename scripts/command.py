"""REPL 指令系统。新增指令：写 cmd_xxx 函数 + 在 COMMANDS 加一行。"""
from presets import list_llms, list_agents


# ═══════════════════════════════════════════════════
#  Action 三态
# ═══════════════════════════════════════════════════
class Action:
    """指令返回的基类。"""


class Continue(Action):
    """继续 REPL 循环。"""


class Quit(Action):
    """退出 REPL。"""


class AgentMessage(Action):
    """发给 Agent 的消息。"""
    __slots__ = ("text",)

    def __init__(self, text: str):
        self.text = text


# ═══════════════════════════════════════════════════
#  指令处理器
# ═══════════════════════════════════════════════════

def cmd_help(conv, args: str) -> Action:
    """显示帮助"""
    print("\n可用指令:")
    for name, h in COMMANDS.items():
        if name.startswith("/") and len(name) <= 8:  # 只显示主指令，忽略别名
            desc = (h.__doc__ or "").strip().split("\n")[0]
            print(f"  {name:<12} {desc}")
    print()
    return Continue()


def cmd_quit(conv, args: str) -> Action:
    """退出"""
    print("Bye.")
    return Quit()


def cmd_status(conv, args: str) -> Action:
    """显示当前 LLM/Agent 配置和所有绑定"""
    print(InitAi.status())
    return Continue()


def cmd_model(conv, args: str) -> Action:
    """切换 LLM: /model <名字>。同时更新当前 Agent 的模型绑定"""
    name = args.strip()
    if not name:
        print(f"用法: /model <名字>。可用: {list_llms()}")
        return Continue()
    InitAi.switch_llm(name)
    return Continue()


def cmd_agent(conv, args: str) -> Action:
    """切换 Agent: /agent <名字>。自动切换到该 Agent 绑定的模型"""
    name = args.strip()

    # /agent --reset <名字> → 重置绑定后切换
    if name.startswith("--reset"):
        parts = name.split(maxsplit=1)
        target = parts[1].strip() if len(parts) > 1 else ""
        if target:
            InitAi.reset_binding(target)
            name = target
        else:
            print("用法: /agent --reset <名字>")
            return Continue()

    if not name:
        print(f"用法: /agent <名字>。可用: {list_agents()}")
        return Continue()

    InitAi.switch_agent(name)
    return Continue()


def cmd_clear(conv, args: str) -> Action:
    """重置对话（开始新 Conversation）"""
    from openhands.sdk import Conversation
    InitAi.conversation = Conversation(
        agent=InitAi.agent,
        workspace=InitAi.conversation.state.workspace.working_dir,
    )
    print("✅ 对话已重置")
    return Continue()


def cmd_save(conv, args: str) -> Action:
    """保存对话历史: /save [路径]"""
    path = args.strip() or "conversation.log"
    with open(path, "w", encoding="utf-8") as f:
        for ev in conv.state.events:
            f.write(repr(ev) + "\n---\n")
    print(f"✅ 已保存到 {path}")
    return Continue()


# ═══════════════════════════════════════════════════
#  注册表 + 入口
# ═══════════════════════════════════════════════════
COMMANDS = {
    "/help":   cmd_help,   "/?":      cmd_help,
    "/quit":   cmd_quit,   "/exit":   cmd_quit,   "/q": cmd_quit,
    "/status": cmd_status, "/st":     cmd_status,
    "/model":  cmd_model,  "/m":      cmd_model,
    "/agent":  cmd_agent,  "/a":      cmd_agent,
    "/clear":  cmd_clear,
    "/save":   cmd_save,
}


def dispatch(conversation, user_input: str) -> Action:
    """入口：解析用户输入。非 / 开头 → AgentMessage，/ 开头 → 指令。"""
    if not user_input.startswith("/"):
        return AgentMessage(user_input)

    parts = user_input.split(maxsplit=1)
    cmd_name = parts[0].lower()
    args = parts[1] if len(parts) > 1 else ""

    handler = COMMANDS.get(cmd_name)
    if handler is None:
        print(f"未知指令 '{cmd_name}'。输入 /help 查看。")
        return Continue()
    return handler(conversation, args)


# 延迟 import — InitAi 在 main.py 导入后才可用
from initai import InitAi
