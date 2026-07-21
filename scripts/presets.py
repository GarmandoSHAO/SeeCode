"""LLM 和 Agent 预设注册表。新增模型/Agent 只改这一个文件。"""
import os
from pathlib import Path
from dotenv import load_dotenv

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
#  但 default_model 是初始值，同时也是 /agent --reset 的目标值。
# ═══════════════════════════════════════════════════════════════

def _coder(llm):
    return Agent(llm=llm, tools=[Tool(name=t.name) for t in ALL_TOOLS])


def _planner(llm):
    return Agent(llm=llm, tools=[Tool(name=t.name) for t in READONLY_TOOLS],
                 system_prompt_filename="system_prompt_planning.j2",
                 include_default_tools=["FinishTool"])


def _executor(llm):
    return Agent(llm=llm, tools=[Tool(name=t.name) for t in EXEC_ONLY],
                 include_default_tools=["FinishTool"])


def _long(llm):
    return Agent(llm=llm, tools=[Tool(name=t.name) for t in ALL_TOOLS],
                 system_prompt_filename="system_prompt_long_horizon.j2")


AGENT_PRESETS = {
    "coder": {
        "factory":       _coder,
        "default_model": "ds-flash",
    },
    "planner": {
        "factory":       _planner,
        "default_model": "ds-reasoner",
    },
    "executor": {
        "factory":       _executor,
        "default_model": "ds-flash",
    },
    "long": {
        "factory":       _long,
        "default_model": "ds-chat",
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


def list_llms():
    return list(LLM_PRESETS.keys())


def list_agents():
    return list(AGENT_PRESETS.keys())
