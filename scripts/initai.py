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

        # 写绑定 — 当前 Agent 记住这个 Model
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

        # 读绑定 — 用该 Agent 当前绑定的 Model
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
            f"LLM:       {cls.current_llm_name} ({cls.llm.model})",
            f"Agent:     {cls.current_agent_name}",
            f"Tools:     {[t.name for t in cls.agent.tools]}",
            f"Workspace: {WORKSPACE}",
            "",
            "Agent-Model 绑定:",
        ]
        for a_name in list_agents():
            default = get_default_model_for_agent(a_name)
            current = cls._bindings.get(a_name, default)
            marker = " ← 当前" if a_name == cls.current_agent_name else ""
            dirty  = " *" if current != default else ""
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
