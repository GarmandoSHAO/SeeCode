import os, sys
from dotenv import load_dotenv
load_dotenv()

from openhands.sdk import LLM, Agent, Conversation, Tool
from openhands.tools.file_editor import FileEditorTool
from openhands.tools.task_tracker import TaskTrackerTool
from openhands.tools.terminal import TerminalTool

# ── 只做一次 ──
llm = LLM(
    model="deepseek/deepseek-v4-flash",
    api_key=os.getenv("LLM_API_KEY"),
)

agent = Agent(
    llm=llm,
    tools=[
        Tool(name=TerminalTool.name),
        Tool(name=FileEditorTool.name),
        Tool(name=TaskTrackerTool.name),
    ],
)

conversation = Conversation(
    agent=agent,
    workspace=r"E:\WorkSpace\PySpace\pythonProject\Project\SceCode",
)

print("✅ Agent 就绪。输入消息后回车（输入 /quit 退出）\n")

# ── 循环接受消息 ──
while True:
    try:
        msg = input(">>> ").strip()
    except (EOFError, KeyboardInterrupt):
        print("\nBye.")
        break

    if msg.lower() in ("/quit", "/exit", ""):
        break

    conversation.send_message(msg)
    conversation.run()
    print()  # 空行分隔不同轮次
