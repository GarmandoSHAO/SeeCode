# 可切换 LLM 和 Agent 的架构设计

> **日期**: 2026-07-19
> **问题**: 如何设计一个可在运行时切换不同 LLM 和不同 Agent 的系统

---

## 1. 核心思路

把 LLM 和 Agent 的创建逻辑从硬编码变成**注册表 + 工厂模式**，通过名字就能创建不同的实例。

```
用户输入                      工厂                          产物
──────────              ────────────────              ──────────
--llm deepseek  ────▶  LLM_REGISTRY   ────▶  LLM(model=..., api_key=...)
                                           │
--agent coder   ────▶  AGENT_REGISTRY ────▶  Agent(llm=↑, tools=[...])
```

---

## 2. 文件结构

```
SceCode/
├── .env                          ← 存放所有 API Key
├── scripts/
│   ├── run.py                    ← 入口：解析参数，组装 LLM+Agent，启动对话
│   ├── presets.py                ← LLM 和 Agent 的预设注册表
│   └── repl.py                   ← REPL 循环（复用 run.py 的工厂函数）
```

---

## 3. presets.py — 注册表

这是整个系统的配置中心，所有预设都在这里定义。

```python
"""LLM 和 Agent 的预设注册表。新增预设只需要加一个条目。"""
import os
from dotenv import load_dotenv
from pathlib import Path

# 定位 .env
env_path = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(env_path)

from openhands.sdk import LLM, Agent, Tool
from openhands.tools.file_editor import FileEditorTool
from openhands.tools.task_tracker import TaskTrackerTool
from openhands.tools.terminal import TerminalTool


# ═══════════════════════════════════════════════════════════════
#  LLM 预设 — 格式: { "名字": LLM(参数...) }
#  新增模型只需在这里加一行
# ═══════════════════════════════════════════════════════════════

LLM_PRESETS = {
    "deepseek-flash": LLM(
        model="deepseek/deepseek-v4-flash",
        api_key=os.getenv("DEEPSEEK_API_KEY"),
    ),
    "deepseek-chat": LLM(
        model="deepseek/deepseek-chat",
        api_key=os.getenv("DEEPSEEK_API_KEY"),
    ),
    "deepseek-reasoner": LLM(
        model="deepseek/deepseek-reasoner",
        api_key=os.getenv("DEEPSEEK_API_KEY"),
        reasoning_effort="high",
    ),
    "claude-sonnet": LLM(
        model="anthropic/claude-sonnet-4-5-20250929",
        api_key=os.getenv("ANTHROPIC_API_KEY"),
    ),
    "gpt-5": LLM(
        model="openai/gpt-5",
        api_key=os.getenv("OPENAI_API_KEY"),
    ),
}

# 默认 LLM
DEFAULT_LLM = "deepseek-flash"


# ═══════════════════════════════════════════════════════════════
#  Agent 预设 — 格式: { "名字": 工厂函数(LLM) → Agent }
#  每个预设是一个函数，接收 LLM，返回 Agent
#  因为 Agent 需要绑定 LLM，所以用工厂函数而非直接存 Agent
# ═══════════════════════════════════════════════════════════════

def _make_coder(llm: LLM) -> Agent:
    """全功能编码 Agent — 默认。有 terminal + 文件编辑 + 任务追踪。"""
    return Agent(
        llm=llm,
        tools=[
            Tool(name=TerminalTool.name),
            Tool(name=FileEditorTool.name),
            Tool(name=TaskTrackerTool.name),
        ],
    )


def _make_planner(llm: LLM) -> Agent:
    """规划 Agent — 只读探索 + 输出计划，不改代码。"""
    return Agent(
        llm=llm,
        tools=[
            Tool(name=TerminalTool.name),     # 用来 ls / grep
            Tool(name=FileEditorTool.name),   # 用来 view（不是 create/edit）
        ],
        system_prompt_filename="system_prompt_planning.j2",
        include_default_tools=["FinishTool"],    # 不用 ThinkTool
    )


def _make_executor(llm: LLM) -> Agent:
    """执行 Agent — 只有 terminal，专门跑命令。"""
    return Agent(
        llm=llm,
        tools=[Tool(name=TerminalTool.name)],
        include_default_tools=["FinishTool"],
    )


def _make_long_task(llm: LLM) -> Agent:
    """长任务 Agent — 强化任务追踪，适合复杂多步骤任务。"""
    return Agent(
        llm=llm,
        tools=[
            Tool(name=TerminalTool.name),
            Tool(name=FileEditorTool.name),
            Tool(name=TaskTrackerTool.name),
        ],
        system_prompt_filename="system_prompt_long_horizon.j2",
    )


def _make_custom(llm: LLM) -> Agent:
    """自定义 Agent — 用你写的系统提示词。"""
    custom_prompt = Path(__file__).resolve().parent.parent / "prompts" / "my_system.j2"
    return Agent(
        llm=llm,
        tools=[
            Tool(name=TerminalTool.name),
            Tool(name=FileEditorTool.name),
        ],
        system_prompt_filename=str(custom_prompt) if custom_prompt.exists() else "system_prompt.j2",
    )


# Agent 注册表
AGENT_PRESETS = {
    "coder":     _make_coder,
    "planner":   _make_planner,
    "executor":  _make_executor,
    "long":      _make_long_task,
    "custom":    _make_custom,
}

# 默认 Agent
DEFAULT_AGENT = "coder"


# ═══════════════════════════════════════════════════════════════
#  工厂函数 — 给外部调用的统一入口
# ═══════════════════════════════════════════════════════════════

def create_llm(name: str | None = None) -> LLM:
    """根据名字创建 LLM 实例。不传则用默认。"""
    name = name or DEFAULT_LLM
    if name not in LLM_PRESETS:
        available = list(LLM_PRESETS.keys())
        raise ValueError(f"未知 LLM: '{name}'。可用: {available}")
    return LLM_PRESETS[name]


def create_agent(llm: LLM, name: str | None = None) -> Agent:
    """根据名字 + LLM 创建 Agent 实例。不传则用默认。"""
    name = name or DEFAULT_AGENT
    if name not in AGENT_PRESETS:
        available = list(AGENT_PRESETS.keys())
        raise ValueError(f"未知 Agent: '{name}'。可用: {available}")
    return AGENT_PRESETS[name](llm)


def list_llms() -> list[str]:
    """列出所有可用的 LLM 预设。"""
    return list(LLM_PRESETS.keys())


def list_agents() -> list[str]:
    """列出所有可用的 Agent 预设。"""
    return list(AGENT_PRESETS.keys())
```

### 设计要点

| 设计决策 | 理由 |
|----------|------|
| LLM 预设**直接存实例** | LLM 不依赖其他对象，可以直接创建 |
| Agent 预设**存工厂函数** | Agent 依赖 LLM，必须在拿到 LLM 之后才能创建 |
| `.env` 用 `__file__` 定位 | 无论从哪个目录运行都能找到 |
| 新增预设只需一行 | 修改注册表字典即可，不改其他代码 |

---

## 4. run.py — CLI 入口

```python
"""可切换 LLM 和 Agent 的运行入口。

用法:
    # 默认配置（deepseek-flash + coder）
    python scripts/run.py "帮我创建一个 README.md"

    # 指定 LLM 和 Agent
    python scripts/run.py --llm claude-sonnet --agent planner "分析项目结构"

    # 列出可用的预设
    python scripts/run.py --list-llms
    python scripts/run.py --list-agents

    # REPL 交互模式
    python scripts/run.py --repl --llm deepseek-chat --agent coder
"""
import argparse
from pathlib import Path
from dotenv import load_dotenv

# 确保能找到 .env
env_path = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(env_path)

from openhands.sdk import Conversation
from presets import create_llm, create_agent, list_llms, list_agents

WORKSPACE = str(Path(__file__).resolve().parent.parent)


def main():
    parser = argparse.ArgumentParser(description="OpenHands Agent 运行器")
    parser.add_argument("message", nargs="?", help="要发送的消息")
    parser.add_argument("--llm", default=None, help=f"LLM 预设名。可用: {list_llms()}")
    parser.add_argument("--agent", default=None, help=f"Agent 预设名。可用: {list_agents()}")
    parser.add_argument("--list-llms", action="store_true", help="列出所有 LLM 预设")
    parser.add_argument("--list-agents", action="store_true", help="列出所有 Agent 预设")
    parser.add_argument("--repl", action="store_true", help="进入 REPL 交互模式")
    args = parser.parse_args()

    # 列表模式
    if args.list_llms:
        print("可用 LLM 预设:")
        for name in list_llms():
            mark = " (默认)" if name == "deepseek-flash" else ""
            print(f"  - {name}{mark}")
        return
    if args.list_agents:
        print("可用 Agent 预设:")
        for name in list_agents():
            mark = " (默认)" if name == "coder" else ""
            print(f"  - {name}{mark}")
        return

    # 创建 LLM 和 Agent
    llm = create_llm(args.llm)
    agent = create_agent(llm, args.agent)

    print(f"LLM: {args.llm or 'deepseek-flash'} | Agent: {args.agent or 'coder'}")
    print(f"工作区: {WORKSPACE}\n")

    conversation = Conversation(agent=agent, workspace=WORKSPACE)

    # REPL 模式
    if args.repl:
        print("输入消息后回车。输入 /quit 退出。\n")
        while True:
            try:
                msg = input(">>> ").strip()
            except (EOFError, KeyboardInterrupt):
                print("\nBye.")
                break
            if msg.lower() in ("/quit", "/exit"):
                break
            if not msg:
                continue
            conversation.send_message(msg)
            conversation.run()
            print()
        return

    # 单次模式
    if not args.message:
        parser.error("需要提供消息，或使用 --repl 进入交互模式")
    conversation.send_message(args.message)
    conversation.run()


if __name__ == "__main__":
    main()
```

---

## 5. .env 配置

```bash
# .env — 所有 API Key 集中管理
DEEPSEEK_API_KEY=sk-your-deepseek-api-key-here
ANTHROPIC_API_KEY=sk-ant-xxxxx
OPENAI_API_KEY=sk-xxxxx
```

---

## 6. 使用示例

```bash
# 列出所有可用预设
python scripts/run.py --list-llms
python scripts/run.py --list-agents

# 默认配置运行单次任务
python scripts/run.py "写一个 hello world 到 hello.py"

# 指定 LLM 和 Agent
python scripts/run.py --llm claude-sonnet --agent planner "分析项目架构"

# 用 deepseek-reasoner + 长任务模式做复杂工作
python scripts/run.py --llm deepseek-reasoner --agent long "从零搭建一个 Flask API"

# REPL 交互模式
python scripts/run.py --repl --llm deepseek-flash --agent coder
```

---

## 7. 扩展方式

### 新增 LLM

只需在 `presets.py` 的 `LLM_PRESETS` 字典里加一行：

```python
"my-new-model": LLM(
    model="openai/gpt-4o-mini",
    api_key=os.getenv("OPENAI_API_KEY"),
),
```

### 新增 Agent

只需在 `presets.py` 里写一个 `_make_xxx` 函数，然后加到 `AGENT_PRESETS`：

```python
def _make_code_reviewer(llm: LLM) -> Agent:
    """代码审查 Agent — 只读 + 审查专用提示词。"""
    return Agent(
        llm=llm,
        tools=[Tool(name=FileEditorTool.name)],   # 只 view，不改
        system_prompt="你是一个代码审查专家。只分析代码质量，不做任何修改。",
        include_default_tools=["FinishTool"],
    )

AGENT_PRESETS["reviewer"] = _make_code_reviewer
```

---

## 8. 数据流图

```
命令行参数                     presets.py                      运行时
──────────              ────────────────────          ───────────────────
--llm deepseek-flash                       LLM_PRESETS
        │                                  ┌───────────────┐
        └──────────────────────────────────▶│ deepseek-flash│──▶ LLM 实例
                                           │ claude-sonnet │
                                           │ gpt-5         │
--agent coder                              └───────────────┘
        │
        │                                  AGENT_PRESETS
        │                                  ┌───────────────┐
        │                      LLM ───────▶│ _make_coder   │──▶ Agent 实例
        └──────────────────────────────────▶│ _make_planner │
                                           │ _make_executor│
                                           └───────────────┘
                                                          │
                                                    ┌─────▼──────┐
                                                    │ Conversation│
                                                    └─────────────┘
```

---

## 9. 关键设计决策

| 问题 | 决策 | 理由 |
|------|------|------|
| LLM 预设存实例还是工厂？ | **实例** | LLM 不需要依赖其他对象，提前创建好更简单 |
| Agent 预设存实例还是工厂？ | **工厂函数** | Agent 依赖 LLM，必须在知道用哪个 LLM 之后才能创建 |
| 注册表用字典还是类？ | **字典** | 简单直观，新增一个预设只需一行 |
| CLI 用 argparse 还是 click？ | **argparse** | Python 标准库，零额外依赖 |
| 配置放代码还是 YAML/JSON？ | **代码（Python dict）** | 类型安全 + IDE 自动补全 + 不需要解析库 |
