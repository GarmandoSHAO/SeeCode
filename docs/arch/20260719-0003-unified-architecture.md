# SceCode 项目统一架构设计

> **日期**: 2026-07-19
> **概述**: 整合三篇设计文档 + 现有代码，给出项目完整架构方案

---

## 1. 现状与问题清单

### 1.1 当前文件

```
SceCode/
├── .env                              ← (空/残留) 已废弃
├── .gitignore                        ← 忽略 scripts/.env, __pycache__
├── test.py                           ← ✅ 已修复的单次脚本
├── FACTS.txt                         ← Agent 输出
├── scripts/
│   ├── .env                          ← API Key 实际存放位置
│   ├── initai.py                     ← 硬编码 InitAi，load_dotenv() 路径有 bug
│   ├── main.py                       ← 简易 REPL，内联指令处理
│   └── command.py                    ← 空文件
├── docs/
│   ├── arch/20260719-0000-*.md       ← SDK 原理分析
│   └── answer/
│       ├── 20260719-0001-*.md        ← 可切换 LLM/Agent 设计
│       └── 20260719-0002-*.md        ← 指令系统设计
```

### 1.2 已有问题

| # | 位置 | 问题 |
|---|------|------|
| 1 | `initai.py:3` | `load_dotenv()` 无参数，从 scripts/ 运行找不到 `.env` |
| 2 | `initai.py:12-15` | LLM 和 Agent 硬编码，无法切换 |
| 3 | `main.py:13` | 指令逻辑写死在循环里，不便于扩展 |
| 4 | `command.py` | 空文件，未实现指令系统 |
| 5 | 缺少 `presets.py` | 注册表模式未落地 |

### 1.3 三篇文档的覆盖范围

```
doc 0000: SDK 原理         →  理解 LLM / Agent / Conversation / Tool 的机制
doc 0001: 可切换 LLM/Agent  →  presets.py 注册表 + run.py CLI 入口
doc 0002: 指令系统          →  command.py dispatch() + Action 三态
```

三篇文档之间有两个重叠：
- doc 0001 的 `presets.py` 和 doc 0002 的 `command.py` 都重复定义了 `LLM_PRESETS`
- doc 0001 的 `run.py` REPL 循环 和 doc 0002 的 `main.py` REPL 循环功能重叠

---

## 2. 目标架构

### 2.1 文件职责

```
SceCode/
├── test.py                       ← 单次脚本（独立，不依赖 scripts/）
├── scripts/
│   ├── .env                      ← API Key 存储
│   ├── presets.py                ← [新建] LLM_PRESETS + AGENT_PRESETS 注册表
│   ├── initai.py                 ← [重构] AI 初始化 + 生命周期管理
│   ├── command.py                ← [新建] 指令系统：dispatch() + COMMANDS
│   └── main.py                   ← [重构] REPL 入口（极薄，只做循环+分发）
├── docs/                         ← 设计文档
├── prompts/                      ← (可选) 自定义系统提示词模板
└── .gitignore
```

### 2.2 模块依赖图

```
                         ┌──────────────┐
                         │  presets.py  │  (数据层)
                         │ LLM_PRESETS  │
                         │ AGENT_PRESETS│
                         └──┬───────┬───┘
                            │       │
              ┌─────────────┘       └─────────────┐
              ▼                                    ▼
      ┌──────────────┐                    ┌──────────────┐
      │  initai.py   │                    │  command.py  │  (逻辑层)
      │  InitAi 类   │                    │  dispatch()  │
      │  创建/切换   │                    │  COMMANDS{}  │
      │  LLM+Agent   │                    │  Action 类型 │
      │  +Conversation                   └──────┬───────┘
      └──────┬───────┘                          │
             │                                  │
             └────────────┬─────────────────────┘
                          │
                          ▼
                   ┌──────────────┐
                   │   main.py    │  (入口层)
                   │  REPL 循环   │
                   │  input()     │
                   │  dispatch()  │
                   │  send+run    │
                   └──────────────┘
```

依赖规则：**上层依赖下层，下层不依赖上层。不存在循环依赖。**

| 模块 | 导入什么 | 被谁导入 |
|------|---------|---------|
| `presets.py` | `openhands.sdk`, `dotenv` | initai, command |
| `initai.py` | `presets` | main |
| `command.py` | `presets` | main |
| `main.py` | `initai`, `command` | 无（入口） |

### 2.3 数据流（一次用户交互的完整路径）

```
用户输入 "帮我写个脚本"
  │
  ▼
main.py: msg = input(">>> ")
  │
  ▼
command.py: dispatch(conversation, msg)
  ├─ startswith("/")?  NO
  └─ return AgentMessage("帮我写个脚本")
  │
  ▼
main.py: isinstance(action, AgentMessage)? YES
  conversation.send_message(action.text)
  conversation.run()
  │
  ▼
OpenHands 内部: Agent ↔ LLM ↔ Tools → Workspace
  │
  ▼
终端输出 Agent 的响应
  │
  ▼
下一个 >>> 等待输入
```

---

## 3. 各模块详细设计

### 3.1 `presets.py` — 注册表（纯数据 + Agent-Model 绑定）

职责：定义所有可用的 LLM 和 Agent 预设，以及 **Agent 的默认模型绑定**。
**除此之外什么都不做。** 这是全项目唯一修改模型/Agent 列表的地方。

```python
"""LLM 和 Agent 预设注册表。新增模型/Agent 只改这一个文件。"""
import os
from pathlib import Path
from dotenv import load_dotenv

# 固定：从 scripts/.env 加载
load_dotenv(Path(__file__).resolve().parent / ".env")

from openhands.sdk import LLM, Agent, Tool
from openhands.tools.file_editor import FileEditorTool
from openhands.tools.task_tracker import TaskTrackerTool
from openhands.tools.terminal import TerminalTool

# ── 常用工具组合 ──
ALL_TOOLS      = [TerminalTool, FileEditorTool, TaskTrackerTool]
READONLY_TOOLS = [TerminalTool, FileEditorTool]
EXEC_ONLY      = [TerminalTool]


# ═══════════════════════════════════════════════════════════════
#  LLM 注册表
# ═══════════════════════════════════════════════════════════════

LLM_PRESETS = {
    "ds-flash":    LLM(model="deepseek/deepseek-v4-flash",
                       api_key=os.getenv("LLM_API_KEY")),
    "ds-chat":     LLM(model="deepseek/deepseek-chat",
                       api_key=os.getenv("LLM_API_KEY")),
    "ds-reasoner": LLM(model="deepseek/deepseek-reasoner",
                       api_key=os.getenv("LLM_API_KEY"),
                       reasoning_effort="high"),
    "ds-pro":      LLM(model="deepseek/deepseek-v4-pro",
                       api_key=os.getenv("DS_PRO_API_KEY") or os.getenv("LLM_API_KEY")),
}

DEFAULT_LLM = "ds-flash"


# ═══════════════════════════════════════════════════════════════
#  Agent 注册表
#  每个 Agent 描述符包含:
#    factory:      工厂函数 (LLM → Agent)
#    default_model: 该 Agent 的默认绑定模型
#
#  Agent-Model 绑定是可变的（运行时可以被 /model 覆盖），
#  但 default_model 是初始值，同时也是 /agent 切换时的默认行为。
# ═══════════════════════════════════════════════════════════════

def _coder(llm):   return Agent(llm=llm, tools=[Tool(name=t.name) for t in ALL_TOOLS])
def _planner(llm): return Agent(llm=llm, tools=[Tool(name=t.name) for t in READONLY_TOOLS],
                                system_prompt_filename="system_prompt_planning.j2",
                                include_default_tools=["FinishTool"])
def _executor(llm):return Agent(llm=llm, tools=[Tool(name=t.name) for t in EXEC_ONLY],
                                include_default_tools=["FinishTool"])
def _long(llm):    return Agent(llm=llm, tools=[Tool(name=t.name) for t in ALL_TOOLS],
                                system_prompt_filename="system_prompt_long_horizon.j2")

AGENT_PRESETS = {
    "coder": {
        "factory":       _coder,
        "default_model": "ds-flash",       # 编码用快模型
    },
    "planner": {
        "factory":       _planner,
        "default_model": "ds-reasoner",    # 规划用推理模型
    },
    "executor": {
        "factory":       _executor,
        "default_model": "ds-flash",
    },
    "long": {
        "factory":       _long,
        "default_model": "ds-chat",        # 长任务用均衡模型
    },
}

DEFAULT_AGENT = "coder"


# ── 工厂入口 ──
def create_llm(name=None):
    return LLM_PRESETS[name or DEFAULT_LLM]

def create_agent(llm, name=None):
    return AGENT_PRESETS[name or DEFAULT_AGENT]["factory"](llm)

def get_default_model_for_agent(agent_name: str) -> str:
    """获取 agent 的默认模型绑定。"""
    return AGENT_PRESETS[agent_name]["default_model"]

def list_llms():   return list(LLM_PRESETS.keys())
def list_agents(): return list(AGENT_PRESETS.keys())
```

关键设计决策：
- `AGENT_PRESETS` 从纯函数升级为 `{"factory": ..., "default_model": ...}` 描述符 — 每个 Agent 携带自己偏好的模型
- `default_model` 是 Agent 的出厂默认模型，但运行时可以被覆盖（见 initai.py）
- `load_dotenv()` 用 `Path(__file__).resolve().parent / ".env"` 定位
- **不做初始化，只做定义**

### 3.2 `initai.py` — AI 生命周期管理（含 Agent-Model 可变绑定）

职责：持有 Conversation 实例，提供创建和切换能力。**维护 Agent 和 Model 之间的可变绑定关系。**

核心机制：每个 Agent 有一个绑定的 Model。切换 Agent 会自动切换到该 Agent 当前绑定的 Model。
手动切换 Model 会修改当前 Agent 的绑定，下次切回该 Agent 时生效。

```
绑定规则:
  ┌─────────────┬──────────────────┬─────────────────────────┐
  │ 操作         │ Agent 变化        │ Model 变化               │
  ├─────────────┼──────────────────┼─────────────────────────┤
  │ /a planner  │ coder → planner  │ flash → reasoner (自动)   │
  │ /m ds-pro   │ 不变 (planner)    │ reasoner → pro (绑定写入)  │
  │ /a coder    │ planner → coder  │ pro → flash (coder初始值) │
  │ /a planner  │ coder → planner  │ flash → pro (上次绑定的值!) │
  └─────────────┴──────────────────┴─────────────────────────┘

  关键: 最后一次 /a planner 时 Model 是 pro（因为上上次 /m ds-pro 写入了绑定），
        不是 reasoner（那只是 initial default）。
```

```python
"""AI 初始化与生命周期管理。维护 Agent-Model 可变绑定。"""
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent / ".env")

from openhands.sdk import Conversation
from presets import (
    create_llm, create_agent,
    LLM_PRESETS, AGENT_PRESETS,
    DEFAULT_LLM, DEFAULT_AGENT,
    get_default_model_for_agent,
    list_llms, list_agents,
)

WORKSPACE = str(Path(__file__).resolve().parent.parent)


class InitAi:
    """持有 LLM + Agent + Conversation 的单例。

    类属性 = 模块级单例，import 时初始化一次。
    维护 _bindings 来记录每个 Agent 当前绑定的 Model。
    """

    # ── 运行时状态 ──
    current_llm_name   = DEFAULT_LLM
    current_agent_name = DEFAULT_AGENT

    llm          = create_llm(DEFAULT_LLM)
    agent        = create_agent(llm, DEFAULT_AGENT)
    conversation = Conversation(agent=agent, workspace=WORKSPACE)

    # ── Agent → Model 可变绑定 ──
    # 初始化时，每个 agent 绑定到它自己的 default_model
    _bindings: dict[str, str] = {
        name: info["default_model"]
        for name, info in AGENT_PRESETS.items()
    }

    @classmethod
    def _rebuild_conversation(cls):
        """用当前 llm 和 agent 重建 Conversation。"""
        cls.conversation = Conversation(agent=cls.agent, workspace=WORKSPACE)

    # ═══════════════════════════════════════════════════════════
    #  切换 LLM（同时写到当前 Agent 的绑定）
    # ═══════════════════════════════════════════════════════════
    @classmethod
    def switch_llm(cls, name: str) -> bool:
        """热切换 LLM。同时更新当前 Agent 的模型绑定。

        这意味着下次切回这个 Agent 时，会用这次选的 Model。
        """
        if name not in LLM_PRESETS:
            print(f"未知 LLM: '{name}'。可用: {list_llms()}")
            return False

        cls.llm = create_llm(name)
        cls.agent = create_agent(cls.llm, cls.current_agent_name)
        cls._rebuild_conversation()

        # ★ 关键: 写绑定 — 当前 Agent 记住这个 Model
        cls._bindings[cls.current_agent_name] = name
        cls.current_llm_name = name

        print(f"✅ LLM → {name}（Agent '{cls.current_agent_name}' 已绑定此模型）")
        return True

    # ═══════════════════════════════════════════════════════════
    #  切换 Agent（同时切换到该 Agent 绑定的 Model）
    # ═══════════════════════════════════════════════════════════
    @classmethod
    def switch_agent(cls, name: str) -> bool:
        """热切换 Agent。同时自动切换到该 Agent 当前绑定的 Model。

        如果该 Agent 之前被 /model 改过绑定，用的是绑定值而非 default_model。
        """
        if name not in AGENT_PRESETS:
            print(f"未知 Agent: '{name}'。可用: {list_agents()}")
            return False

        # ★ 关键: 读绑定 — 用该 Agent 当前绑定的 Model
        bound_model = cls._bindings.get(name, get_default_model_for_agent(name))

        old_model = cls.current_llm_name

        cls.llm = create_llm(bound_model)
        cls.agent = create_agent(cls.llm, name)
        cls._rebuild_conversation()

        cls.current_agent_name = name
        cls.current_llm_name = bound_model

        if bound_model != old_model:
            print(f"✅ Agent → {name}，LLM 自动切换 → {bound_model}")
        else:
            print(f"✅ Agent → {name}（LLM 不变: {bound_model}）")
        return True

    # ═══════════════════════════════════════════════════════════
    #  状态显示
    # ═══════════════════════════════════════════════════════════
    @classmethod
    def status(cls) -> str:
        lines = [
            f"LLM:    {cls.current_llm_name} ({cls.llm.model})",
            f"Agent:  {cls.current_agent_name}",
            f"Tools:  {[t.name for t in cls.agent.tools]}",
            f"Workspace: {WORKSPACE}",
            "",
            "Agent-Model 绑定:",
        ]
        for a_name in list_agents():
            default = get_default_model_for_agent(a_name)
            current = cls._bindings.get(a_name, default)
            marker  = " ← 当前" if a_name == cls.current_agent_name else ""
            dirty   = " *" if current != default else ""
            lines.append(f"  {a_name}: {current}{dirty}{marker}")
        return "\n".join(lines)

    @classmethod
    def reset_binding(cls, agent_name: str = None) -> bool:
        """重置指定 Agent（或当前 Agent）的模型绑定为出厂默认。"""
        target = agent_name or cls.current_agent_name
        if target not in AGENT_PRESETS:
            return False
        cls._bindings[target] = get_default_model_for_agent(target)
        print(f"✅ '{target}' 的模型绑定已重置为默认: {cls._bindings[target]}")
        return True


print(f"✅ Agent 就绪。LLM={InitAi.current_llm_name} Agent={InitAi.current_agent_name}")
```

### Agent-Model 绑定机制详解

```
初始状态（出厂默认）:
  _bindings = {
    "coder":    "ds-flash",
    "planner":  "ds-reasoner",
    "executor": "ds-flash",
    "long":     "ds-chat",
  }

用户操作序列:

>>> /a planner
  读 _bindings["planner"] = "ds-reasoner"
  → LLM 从 flash 切换到 reasoner，Agent 切换到 planner
  _bindings 不变

>>> /m ds-pro
  写 _bindings["planner"] = "ds-pro"        ← ★ 持久化覆盖
  → LLM 切换到 pro，Agent 保持 planner

>>> /a coder
  读 _bindings["coder"] = "ds-flash"         ← coder 未被改过
  → LLM 从 pro 切回 flash

>>> /a planner
  读 _bindings["planner"] = "ds-pro"         ← ★ 上次 /m 写入的值
  → LLM 切换到 pro（不是 reasoner！）

>>> /a planner --reset
  _bindings["planner"] = "ds-reasoner"      ← 恢复出厂默认
```

Agent-Model 绑定的两个关键操作就是 **读** 和 **写**：
- `switch_agent()`  **读** `_bindings[name]`，决定切换到哪个 Model
- `switch_llm()`   **写** `_bindings[current_agent]`，记住用户的选择

### 3.3 `command.py` — 指令系统

职责：接收用户输入，分发给对应的指令处理函数。**只做解析和分发，不做任何 Agent 逻辑（Agent 逻辑在 initai）。**

```python
"""REPL 指令系统。新增指令：写 cmd_xxx 函数 + 在 COMMANDS 加一行。"""
from presets import list_llms, list_agents

# ═══════════════════════════════════════════════════
#  Action 三态
# ═══════════════════════════════════════════════════
class Action:       """指令返回的基类。"""
class Continue(Action):   """继续 REPL 循环。"""
class Quit(Action):       """退出 REPL。"""
class AgentMessage(Action):
    __slots__ = ("text",)
    def __init__(self, text): self.text = text


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
            print(f"  绑定已重置，正在切换...")
            name = target
        else:
            print("用法: /agent --reset <名字>")
            return Continue()

    if not name:
        print(f"用法: /agent <名字>。可用: {list_agents()}")
        return Continue()

    if hasattr(InitAi, 'reset_binding') and args.startswith("--reset"):
        pass  # handled above
    InitAi.switch_agent(name)
    return Continue()

def cmd_clear(conv, args: str) -> Action:
    """重置对话（开始新 Conversation）"""
    from openhands.sdk import Conversation
    InitAi.conversation = Conversation(agent=InitAi.agent, workspace=InitAi.conversation.state.workspace.working_dir)
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


# 延迟 import 避免循环依赖
from initai import InitAi
```

### 3.4 `main.py` — REPL 入口（极薄）

职责：**只有三件事** — 循环、读输入、调 dispatch。逻辑越少越好。

```python
"""SceCode REPL 入口。"""
from initai import InitAi
from command import dispatch, Continue, Quit, AgentMessage

conversation = InitAi.conversation

while True:
    try:
        msg = input(">>> ").strip()
    except (EOFError, KeyboardInterrupt):
        print("\nBye.")
        break

    if not msg:
        continue

    action = dispatch(conversation, msg)

    if isinstance(action, Quit):
        break
    elif isinstance(action, AgentMessage):
        conversation.send_message(action.text)
        conversation.run()
        print()
    # Continue → 回到循环
```

---

## 4. 关键架构决策

| # | 决策 | 选项 A | 选项 B | 选择 | 理由 |
|---|------|--------|--------|------|------|
| 1 | 注册表放哪 | presets.py 独立文件 | 塞进 initai.py | **A** | 单一职责：initai 管生命周期，presets 管定义 |
| 2 | LLM 切换方式 | 替换 `InitAi.llm` 属性 | 每次新建 `Conversation` | **B** | Agent 和 Conversation 都绑定了旧 LLM，只换 llm 不够 |
| 3 | Agent 预设的 tools | 每个工厂函数手写 | 提到模块顶层常量 | **B** | 三个工厂函数共享同样的工具组合，避免重复 |
| 4 | command.py 如何拿到 InitAi | 传参（dispatch 多一个参数） | 延迟 import | **B** | 传参会污染 dispatch 签名；延迟 import 简单且无循环依赖 |
| 5 | load_dotenv 放哪个文件 | 每个文件自己调 | 只在 main.py 调一次 | **A** | 每个模块可能被单独导入/测试，各自保证 env 就绪更 robust |
| 6 | 切换 Agent 后 Conversation | 保持旧的（历史延续） | 重置新的 | **B** | 切换 Agent 类型后提示词变了，旧上下文可能不兼容新行为 |
| 7 | 错误处理 | 指令内 try/except | main.py 统一 try | **A** | 不同指令的错误也不同，内聚在指令处理器中更清晰 |
| 8 | Agent-Model 绑定存储 | 存在 Agent 本身 | 存在 InitAi 的 `_bindings` dict | **B** | Agent 对象由 OpenHands 管理，不便于附加自定义属性；InitAi 自己的 dict 更清晰可控 |
| 9 | 绑定的生命周期 | 切换 Agent 就重置 | 持久化直到显式复位 | **B** | 用户手动选的 Model 应该记住；切换 Agent 自动用绑定值，不丢失用户偏好 |
| 10 | 绑定重置 | 单独的 /reset 指令 | /agent --reset <name> | **B** | 绑定是和 Agent 紧密相关的，挂在 /agent 下语义更直接 |

---

## 5. 与三篇文档的差异

| 文档 | 提出的设计 | 统一后的变化 | 原因 |
|------|----------|------------|------|
| doc 0001 | `presets.py` + `run.py`（CLI 入口） | `presets.py` 保留，`run.py` 合并到 `main.py` | 避免两个入口（argparse CLI vs REPL），用一个 main.py 统一 |
| doc 0001 | Agent 工厂函数各自手写 tools | tools 提到模块顶层 `ALL_TOOLS` 常量 | 减少重复 |
| doc 0002 | `command.py` 自己维护 `LLM_PRESETS` | 删掉，统一从 `presets.py` 导入 | 单一数据源，避免两处维护 |
| doc 0002 | `command.py` 的 `_make_agent()` | 移到 `presets.py` 统一管理 | 同上 |
| doc 0002 | `cmd_model` 直接替换 `conv.agent.llm` | 委托 `InitAi.switch_llm()` | 不只是换 llm，还要重建 Agent 和 Conversation |

---

## 6. 渐进式实施路径

不需要一次全改完，可以分步：

| 步骤 | 改动 | 影响 |
|------|------|------|
| **Step 1** | 新建 `presets.py` | 零风险，新文件 |
| **Step 2** | 重构 `initai.py`，使用 `presets` | 改动 initai.py 内部实现，main.py 不受影响 |
| **Step 3** | 实现 `command.py` | 新文件，不影响现有 |
| **Step 4** | 重构 `main.py`，使用 `command.dispatch()` | 去掉 main.py 中的内联指令逻辑 |

每一步之后都可以独立测试——项目始终可运行。

---

## 7. 使用效果

```
$ python scripts/main.py
✅ Agent 就绪。LLM=ds-flash Agent=coder

>>> /st
LLM:    ds-flash (deepseek/deepseek-v4-flash)
Agent:  coder
Tools:  ['terminal', 'file_editor', 'task_tracker']
Workspace: E:\WorkSpace\PySpace\pythonProject\Project\SceCode

Agent-Model 绑定:
  coder:    ds-flash ← 当前
  planner:  ds-reasoner
  executor: ds-flash
  long:     ds-chat

>>> /a planner
✅ Agent → planner，LLM 自动切换 → ds-reasoner

   说明: planner 的默认模型是 ds-reasoner，切 Agent 自动带 Model

>>> /st
Agent-Model 绑定:
  coder:    ds-flash
  planner:  ds-reasoner ← 当前
  executor: ds-flash
  long:     ds-chat

>>> /m ds-pro
✅ LLM → ds-pro（Agent 'planner' 已绑定此模型）

   说明: 手动换 Model → planner 的绑定从 reasoner 改成 pro（持久化）

>>> /st
Agent-Model 绑定:
  coder:    ds-flash
  planner:  ds-pro * ← 当前     ← ★ * 表示被修改过（不等于 default_model）
  executor: ds-flash
  long:     ds-chat

>>> /a coder
✅ Agent → coder，LLM 自动切换 → ds-flash

   说明: coder 没被改过，切过去还是 flash

>>> /a planner
✅ Agent → planner，LLM 自动切换 → ds-pro

   说明: ★ 关键！切回 planner，Model 是 pro 而不是 reasoner
          因为上次 /m ds-pro 写入了绑定，persist 住了

>>> /a planner --reset
✅ 'planner' 的模型绑定已重置为默认: ds-reasoner
  绑定已重置，正在切换...

   说明: 复位 planner 的绑定为出厂默认

>>> /q
Bye.
```
