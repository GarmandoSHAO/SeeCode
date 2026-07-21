# REPL 指令系统设计

> **日期**: 2026-07-19
> **问题**: 在 `command.py` 中定义可扩展的指令系统，支持 `/quit`、`/help` 等

---

## 1. 整体架构

```
用户输入
  │
  ▼
main.py (REPL 循环)
  │
  ├─ 以 / 开头 ──▶ command.py ──▶ 执行指令（退出/帮助/切换模型等）
  │
  └─ 其他文本 ──▶ conversation.send_message() → Agent 处理
```

**判别规则**：`/` 开头 = 指令，其他 = 发给 Agent。

---

## 2. command.py — 完整实现

```python
"""指令系统 — 所有 REPL 指令在这里定义。

新增指令: 写一个 do_xxx 函数，加到 COMMANDS 字典即可。
"""
from openhands.sdk import LLM, Agent, Tool
from openhands.tools.file_editor import FileEditorTool
from openhands.tools.task_tracker import TaskTrackerTool
from openhands.tools.terminal import TerminalTool


# ═══════════════════════════════════════════════════════════════
#  LLM 和 Agent 切换预设（如果你有多个模型/Agent 可换）
# ═══════════════════════════════════════════════════════════════

LLM_PRESETS = {
    "ds-flash":    LLM(model="deepseek/deepseek-v4-flash", api_key=os.getenv("LLM_API_KEY")),
    "ds-chat":     LLM(model="deepseek/deepseek-chat", api_key=os.getenv("LLM_API_KEY")),
}


def _make_agent(llm, preset="coder"):
    if preset == "coder":
        return Agent(llm=llm, tools=[
            Tool(name=TerminalTool.name),
            Tool(name=FileEditorTool.name),
            Tool(name=TaskTrackerTool.name),
        ])
    elif preset == "planner":
        return Agent(llm=llm, tools=[
            Tool(name=TerminalTool.name),
            Tool(name=FileEditorTool.name),
        ], system_prompt_filename="system_prompt_planning.j2")
    raise ValueError(f"未知 Agent 预设: {preset}")


# ═══════════════════════════════════════════════════════════════
#  指令处理函数 — 每个函数签名: (conversation, args: str) → Action
#
#  Action 有三种返回值:
#    Continue()        → 继续 REPL 循环
#    Quit()            → 退出 REPL
#    AgentMessage(str) → 把文本发给 Agent
# ═══════════════════════════════════════════════════════════════

class Action:
    """指令的返回动作。"""

class Continue(Action):
    """继续循环，不干别的。"""

class Quit(Action):
    """退出 REPL。"""

class AgentMessage(Action):
    """发给 Agent 的消息。"""
    __slots__ = ("text",)
    def __init__(self, text: str):
        self.text = text


# ── 指令处理器 ──

def cmd_help(conv, args: str) -> Action:
    """显示帮助信息。"""
    print("\n可用指令:")
    for name, handler in COMMANDS.items():
        desc = (handler.__doc__ or "").strip().split("\n")[0]
        print(f"  {name:<12}  {desc}")
    print()
    return Continue()


def cmd_quit(conv, args: str) -> Action:
    """退出程序。"""
    print("Bye.")
    return Quit()


def cmd_clear(conv, args: str) -> Action:
    """开始新一轮对话（旧的上下文保留在历史中）。"""
    print("(开始新对话)\n")
    # 注意: 新的 send_message 会自动在新的 turn 中运行
    return Continue()


def cmd_model(conv, args: str) -> Action:
    """切换 LLM 模型。用法: /model ds-flash | /model ds-chat"""
    args = args.strip()
    if args not in LLM_PRESETS:
        print(f"未知模型: '{args}'。可用: {list(LLM_PRESETS.keys())}")
        return Continue()
    conv.agent.llm = LLM_PRESETS[args]
    print(f"已切换到模型: {args}")
    return Continue()


def cmd_agent(conv, args: str) -> Action:
    """切换 Agent 类型。用法: /agent coder | /agent planner"""
    args = args.strip()
    if args not in ("coder", "planner"):
        print(f"未知 Agent: '{args}'。可用: coder, planner")
        return Continue()
    conv.agent = _make_agent(conv.agent.llm, args)
    print(f"已切换到 Agent: {args}")
    return Continue()


def cmd_save(conv, args: str) -> Action:
    """保存当前对话历史到文件。用法: /save [文件名, 默认 conversation.log]"""
    path = args.strip() or "conversation.log"
    # Conversation 的事件可以通过 state.events 访问
    with open(path, "w", encoding="utf-8") as f:
        for event in conv.state.events:
            f.write(str(event) + "\n---\n")
    print(f"对话已保存到: {path}")
    return Continue()


def cmd_status(conv, args: str) -> Action:
    """显示当前 LLM 和 Agent 的配置状态。"""
    llm = conv.agent.llm
    agent = conv.agent
    print(f"LLM:    {llm.model}")
    print(f"Tools:  {[t.name for t in agent.tools]}")
    print(f"Prompt: {agent.system_prompt_filename}")
    print(f"Workspace: {conv.state.workspace.working_dir}")
    return Continue()


# ═══════════════════════════════════════════════════════════════
#  指令注册表 — 新增指令只需在这里加一行
# ═══════════════════════════════════════════════════════════════

COMMANDS: dict[str, callable] = {
    "/help":   cmd_help,
    "/quit":   cmd_quit,
    "/exit":   cmd_quit,       # /exit 和 /quit 一样
    "/clear":  cmd_clear,
    "/model":  cmd_model,
    "/agent":  cmd_agent,
    "/save":   cmd_save,
    "/status": cmd_status,
}


# ═══════════════════════════════════════════════════════════════
#  入口函数 — main.py 只需要调用这一个函数
# ═══════════════════════════════════════════════════════════════

def dispatch(conversation, user_input: str) -> Action:
    """解析用户输入，分发到指令或返回 AgentMessage。

    Args:
        conversation: LocalConversation 实例
        user_input: 用户输入（已 strip）

    Returns:
        Action 对象，决定 REPL 下一步行为
    """
    # 不以 / 开头 → 发给 Agent
    if not user_input.startswith("/"):
        return AgentMessage(user_input)

    # 以 / 开头 → 解析指令名和参数
    parts = user_input.split(maxsplit=1)  # 最多分割一次，保留参数中的空格
    cmd_name = parts[0].lower()
    args = parts[1] if len(parts) > 1 else ""

    handler = COMMANDS.get(cmd_name)
    if handler is None:
        print(f"未知指令: '{cmd_name}'。输入 /help 查看可用指令。")
        return Continue()

    return handler(conversation, args)
```

---

## 3. main.py — 修改后

```python
from initai import InitAi
from command import dispatch, Continue, Quit, AgentMessage

conversation = InitAi.conversation

# ── 循环接受消息 ──
while True:
    try:
        msg = input(">>> ").strip()
    except (EOFError, KeyboardInterrupt):
        print("\nBye.")
        break

    if not msg:
        continue

    # ── 分发到指令系统 ──
    action = dispatch(conversation, msg)

    if isinstance(action, Quit):
        break
    elif isinstance(action, AgentMessage):
        conversation.send_message(action.text)
        conversation.run()
        print()
    # else: Continue → 回到循环开头
```

---

## 4. 交互效果

```
>>> /help
可用指令:
  /help         显示帮助信息
  /quit         退出程序
  /exit         退出程序
  /clear        开始新一轮对话
  /model        切换 LLM 模型
  /agent        切换 Agent 类型
  /save         保存当前对话历史到文件
  /status       显示当前 LLM 和 Agent 的配置状态

>>> /status
LLM:    deepseek/deepseek-v4-flash
Tools:  ['terminal', 'file_editor', 'task_tracker']
Prompt: system_prompt.j2
Workspace: E:\WorkSpace\PySpace\pythonProject\Project\SceCode

>>> 帮我看看项目结构
(Agent 执行...)

>>> /model ds-chat
已切换到模型: ds-chat

>>> 再用新模型做一次分析
(Agent 用新模型执行...)

>>> /quit
Bye.
```

---

## 5. 扩展方式

新增一个指令只需要两步：

**步骤 1**：在 `command.py` 中写一个 `cmd_xxx` 函数：

```python
def cmd_find(conv, args: str) -> Action:
    """搜索文件中的内容。用法: /find <关键词>"""
    keyword = args.strip()
    if not keyword:
        print("用法: /find <关键词>")
        return Continue()
    # 自动把搜索需求发给 Agent
    return AgentMessage(f"用 grep 搜索所有文件中包含 '{keyword}' 的地方，列出文件名和行号")
```

**步骤 2**：在 `COMMANDS` 字典中加一行：

```python
COMMANDS = {
    ...
    "/find":   cmd_find,     # ← 新增这一行
}
```

不需要修改任何其他文件。

---

## 6. 数据流

```
用户输入 "/model ds-chat"
  │
  ▼
main.py → dispatch(conv, "/model ds-chat")
  │
  ▼
command.py:
  ├─ startswith("/")? YES
  ├─ split → cmd_name="/model", args="ds-chat"
  ├─ COMMANDS["/model"] → cmd_model
  └─ return cmd_model(conv, "ds-chat")
         │
         ├─ 检查 args 是否在 LLM_PRESETS 中
         ├─ conv.agent.llm = LLM_PRESETS["ds-chat"]
         └─ return Continue()
  │
  ▼
main.py:
  ├─ isinstance(action, Continue)? YES
  └─ 回到 while 循环开头，打印下一个 >>>
```
