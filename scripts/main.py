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
