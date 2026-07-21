# OpenHands SDK 使用指南 & 架构分析

> **日期**: 2026-07-19
> **方案概述**: 分析 SceCode/test.py 中 OpenHands SDK 的使用方式，指出问题并给出修正方案和架构设计。

---

## 1. 项目现状

### 1.1 文件结构

```
E:\WorkSpace\PySpace\pythonProject\Project\
├── SceCode\
│   └── test.py          ← OpenHands SDK 测试脚本（唯一文件）
└── docs\
    └── arch\
        └── ...          ← 架构文档（本文件）
```

### 1.2 运行环境

| 组件 | 路径 |
|------|------|
| Python 虚拟环境 | `E:\WorkSpace\PySpace\Interpreter\` (标准 venv) |
| 工作目录 | `E:\WorkSpace\PySpace\pythonProject\Project\SceCode\` |
| 代码入口 | `test.py` |

---

## 2. 架构图

```
┌─────────────────────────────────────────────────────────────────┐
│                        test.py (入口脚本)                         │
│                                                                  │
│  ┌───────────┐    ┌──────────────┐    ┌──────────────────────┐  │
│  │   LLM     │───▶│    Agent     │───▶│    Conversation      │  │
│  │ (模型配置) │    │  (AI 代理)    │    │    (对话生命周期)      │  │
│  │           │    │              │    │                      │  │
│  │ - model   │    │ - llm        │    │ - agent              │  │
│  │ - api_key │    │ - tools[]    │    │ - workspace (路径)    │  │
│  │ - base_url│    │              │    │ - callbacks[]        │  │
│  └───────────┘    └──────┬───────┘    └──────────┬───────────┘  │
│                          │                       │               │
│                          │    ┌──────────────────┘               │
│                          ▼    ▼                                  │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │                      Tools (工具层)                        │   │
│  │                                                           │   │
│  │  ┌────────────────┐ ┌────────────────┐ ┌───────────────┐  │   │
│  │  │ TerminalTool   │ │ FileEditorTool │ │TaskTrackerTool│  │   │
│  │  │ (bash 执行)     │ │ (文件 CRUD)    │ │ (任务状态管理) │  │   │
│  │  └───────┬────────┘ └───────┬────────┘ └───────┬───────┘  │   │
│  │          │                  │                   │          │   │
│  └──────────┼──────────────────┼───────────────────┼──────────┘   │
│             │                  │                   │              │
│             ▼                  ▼                   ▼              │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │                  Workspace (沙箱工作区)                    │   │
│  │            E:\...\SceCode\  (本地目录模式)                 │   │
│  │                                                           │   │
│  │  Agent 在此目录中：                                         │   │
│  │  - 执行 bash 命令 (TerminalTool)                           │   │
│  │  - 创建/编辑/删除文件 (FileEditorTool)                      │   │
│  │  - 管理任务的 TODO 列表 (TaskTrackerTool)                   │   │
│  └──────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘

数据流：
  User ──send_message()──▶ Conversation ──prompt──▶ Agent ──API call──▶ LLM
  LLM ──response/tool_call──▶ Agent ──execute──▶ Tool ──action──▶ Workspace
  Workspace ──result──▶ Tool ──output──▶ Agent ──next prompt──▶ LLM
  ...循环直到 Agent 判定任务完成...
  Agent ──final response──▶ Conversation ──return──▶ User
```

---

## 3. 模块职责

| 模块 | 包路径 | 职责 |
|------|--------|------|
| **LLM** | `openhands.sdk.LLM` | 封装模型配置：model 名称、api_key、base_url、reasoning_effort 等 |
| **Agent** | `openhands.sdk.Agent` | AI 代理核心：接收 LLM 和工具列表，负责推理-执行循环 |
| **Conversation** | `openhands.sdk.Conversation` | 对话管理器：绑定 Agent + Workspace，管理消息收发和生命周期 |
| **Tool** | `openhands.sdk.Tool` | 工具包装器：将 Tool 类注册到 Agent |
| **TerminalTool** | `openhands.tools.terminal` | 在 workspace 中执行任意 bash 命令 |
| **FileEditorTool** | `openhands.tools.file_editor` | 文件的查看、创建、编辑（基于 str_replace 的编辑器） |
| **TaskTrackerTool** | `openhands.tools.task_tracker` | 任务状态追踪，Agent 用它管理自己的 TODO list |
| **Workspace** | 隐式（目录路径） | 本地目录作为沙箱；也可切换为 `DockerWorkspace` 实现隔离 |

---

## 4. test.py 问题诊断

### 问题 1：API Key 获取方式错误（严重 bug）

```python
# ❌ 当前代码（第 8-11 行）
LLM_API_KEY = "sk-your-api-key-here"
llm = LLM(
    model="deepseek-v4-flash",
    api_key=os.getenv(LLM_API_KEY),  # BUG: 等价于 os.getenv("sk-6490...")
)
```

`os.getenv(LLM_API_KEY)` 会去查找名为 `"sk-xxx..."`（即 API Key 字符串本身）的环境变量，这永远返回 `None`。

### 问题 2：API Key 硬编码（安全风险）

API Key 明文写在源码中，一旦提交到 git 就会泄露。

### 问题 3：workspace 未显式指定

```python
cwd = os.getcwd()    # 取决于从哪里运行脚本
conversation = Conversation(agent=agent, workspace=cwd)
```

`os.getcwd()` 返回的是运行脚本时的工作目录，不是 SceCode 目录，Agent 可能操作错误目录。

### 问题 4：缺少 base_url 配置

`model="deepseek-v4-flash"` 是 DeepSeek 的模型，但未配置 `base_url`。OpenHands 默认走 Anthropic API，需要显式指向 DeepSeek 的 API 端点。

---

## 5. 修正方案

### 方案 A：最小修正（推荐，风险：低）

只修复 bug，保持结构不变。

```python
import os
from openhands.sdk import LLM, Agent, Conversation, Tool
from openhands.tools.file_editor import FileEditorTool
from openhands.tools.task_tracker import TaskTrackerTool
from openhands.tools.terminal import TerminalTool

llm = LLM(
    model="deepseek-v4-flash",
    api_key=os.getenv("LLM_API_KEY"),            # ✅ 读取环境变量
    base_url="https://api.deepseek.com",           # ✅ DeepSeek API 端点
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
    workspace=r"E:\WorkSpace\PySpace\pythonProject\Project\SceCode",  # ✅ 显式指定
)

conversation.send_message("Write 3 facts about the current project into FACTS.txt.")
conversation.run()
print("All done!")
```

**使用方式**：
```bash
# 1. 激活 venv
E:\WorkSpace\PySpace\Interpreter\Scripts\activate

# 2. 安装依赖
pip install openhands-sdk openhands-tools

# 3. 设置环境变量
export LLM_API_KEY="sk-your-api-key-here"

# 4. 运行
python E:\WorkSpace\PySpace\pythonProject\Project\SceCode\test.py
```

### 方案 B：使用 .env 文件管理配置（风险：低）

增加 python-dotenv 来管理环境变量，更规范。

```
SceCode/
├── test.py
├── .env              ← API Key 放这里（加入 .gitignore）
└── .gitignore
```

```python
import os
from dotenv import load_dotenv
load_dotenv()  # 自动读取 .env

from openhands.sdk import LLM, Agent, Conversation, Tool
# ... 其余同方案 A
```

### 方案 C：多 Agent 协作流水线（风险：中）

适用于需要多个 Agent 分工的复杂场景（如代码生成 + 代码审查）：

```python
# 定义不同角色的 Agent
coder = Agent(llm=coder_llm, tools=[TerminalTool, FileEditorTool])
reviewer = Agent(llm=reviewer_llm, tools=[FileEditorTool])

# 串行流水线
conv1 = Conversation(agent=coder, workspace=workspace)
conv1.send_message("Implement feature X")
conv1.run()

conv2 = Conversation(agent=reviewer, workspace=workspace)
conv2.send_message("Review the changes and suggest improvements")
conv2.run()
```

---

## 6. 接口设计参考

### LLM 构造函数

```python
LLM(
    model: str,                        # 模型标识符，如 "anthropic/claude-sonnet-4-5"
    api_key: str | SecretStr | None,   # API 密钥
    base_url: str | None = None,       # 自定义 API 端点 (DeepSeek/OpenAI 等)
    usage_id: str = "agent",           # 成本追踪标识
    reasoning_effort: str | None = None,  # "low" | "medium" | "high" | "xhigh" | "max"
    # 更多参数见: https://docs.openhands.dev/sdk
)
```

### Agent 构造函数

```python
Agent(
    llm: LLM,                              # 必需：语言模型配置
    tools: list[Tool] = [],                 # 工具列表
    system_prompt: str | None = None,       # 自定义系统提示词
    # 更多参数见官方文档
)
```

### Conversation 构造函数

```python
Conversation(
    agent: Agent,                           # 必需：AI 代理
    workspace: str | Workspace,             # 工作区路径或 Workspace 对象
    callbacks: list[Callable] | None = None, # 事件回调
)
```

### Conversation 关键方法

```python
conversation.send_message(message: str | Message)  # 发送消息
conversation.run()                                   # 运行 Agent 循环（阻塞）
conversation.fork(title: str) -> Conversation        # 分叉对话
conversation.close()                                 # 关闭/清理资源
```

---

## 7. 文件改动清单

> ⚠️ 以下仅列出需要改动的文件路径，不执行任何修改。

| 文件 | 操作 | 说明 |
|------|------|------|
| `SceCode/test.py` | 修改 | 修复第 10 行 os.getenv 的 bug，显式指定 workspace，添加 base_url |
| `SceCode/.env` | 新建 | 存放 `LLM_API_KEY` 环境变量 |
| `SceCode/.gitignore` | 新建 | 添加 `.env` 到忽略列表 |

---

## 8. 风险评估

| 方案 | 风险等级 | 说明 |
|------|---------|------|
| A: 最小修正 | **低** | 只修 bug，改动最小，零风险 |
| B: .env 管理 | **低** | 增加 dotenv 依赖，成熟稳定 |
| C: 多 Agent | **中** | 增加复杂度，需要理解 Agent 间通信；当前场景不需要 |

**建议**：当前 `test.py` 只是探索性测试脚本，推荐 **方案 A**。

---

## 9. 后续扩展方向

如果后续要构建更复杂的 Agent 应用：

1. **Docker 沙箱隔离**：使用 `DockerWorkspace` 替代本地目录，防止 Agent 误操作影响宿主机
2. **自定义 Tool**：继承 `openhands.sdk.Tool` 基类，实现项目特定的工具
3. **MCP 集成**：通过 MCP 协议接入外部工具服务
4. **Agent Server**：使用 `openhands-agent-server` 将 Agent 部署为 REST API 服务
5. **回调监控**：通过 `callbacks` 参数监听 Agent 的每一步思考和行动

---

## 参考资源

- 官方文档: https://docs.openhands.dev/sdk
- GitHub 仓库: https://github.com/OpenHands/software-agent-sdk
- 示例代码: https://github.com/OpenHands/software-agent-sdk/tree/main/examples
