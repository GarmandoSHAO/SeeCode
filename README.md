# SceCode

基于 [OpenHands Software Agent SDK](https://github.com/OpenHands/software-agent-sdk) 构建的 AI 编码助手 REPL 环境。

## 项目结构

```
SceCode/
├── test.py                 # 单次调用示例
├── scripts/
│   ├── main.py             # REPL 入口
│   ├── initai.py           # AI 生命周期管理（LLM/Agent/Conversation）
│   ├── presets.py          # LLM 和 Agent 预设注册表
│   ├── command.py          # REPL 指令系统（/help /model /agent 等）
│   ├── .env                # API Key（不提交）
│   └── .env.example        # 环境变量模板
├── docs/                   # 设计文档
│   ├── arch/               # 架构分析
│   └── answer/             # 方案设计
└── .gitignore
```

## 快速开始

### 1. 环境准备

```bash
# 创建虚拟环境
python -m venv venv
venv\Scripts\activate

# 安装依赖
pip install openhands-sdk openhands-tools python-dotenv
```

### 2. 配置 API Key

```bash
# 复制模板
cp scripts\.env.example scripts\.env

# 编辑 scripts\.env，填入你的 DeepSeek API Key
```

### 3. 运行

```bash
# REPL 交互模式（推荐）
python scripts\main.py

# 或单次调用
python test.py
```

## REPL 指令

| 指令 | 别名 | 说明 |
|------|------|------|
| `/help` | `/?` | 显示可用指令 |
| `/status` | `/st` | 显示当前 LLM/Agent 配置和绑定 |
| `/model <name>` | `/m` | 切换 LLM 模型，同时更新当前 Agent 的模型绑定 |
| `/agent <name>` | `/a` | 切换 Agent，自动切换到该 Agent 绑定的模型 |
| `/agent --reset <name>` | | 重置指定 Agent 的模型绑定为出厂默认 |
| `/clear` | | 重置对话，开始新 Conversation |
| `/save [path]` | | 保存对话历史到文件 |
| `/quit` | `/q` `/exit` | 退出 REPL |

## 可用预设

### LLM

| 名称 | 模型 |
|------|------|
| `ds-flash` | deepseek-v4-flash |
| `ds-chat` | deepseek-chat |
| `ds-reasoner` | deepseek-reasoner |
| `ds-pro` | deepseek-v4-pro |

### Agent

| 名称 | 默认模型 | 工具 | 说明 |
|------|---------|------|------|
| `coder` | ds-flash | terminal + file_editor + task_tracker | 全功能编码 |
| `planner` | ds-reasoner | terminal + file_editor（只读） | 规划分析 |
| `executor` | ds-flash | terminal | 纯命令执行 |
| `long` | ds-chat | terminal + file_editor + task_tracker | 长任务 |

## Agent-Model 绑定机制

每个 Agent 绑定一个默认模型。切换 Agent 时会自动切换到其绑定的模型；手动切换模型会修改当前 Agent 的绑定，下次切回该 Agent 时生效。

```
>>> /a planner          # Agent→planner, LLM 自动→ds-reasoner
>>> /m ds-pro           # LLM→pro, planner 绑定记为 pro
>>> /a coder            # Agent→coder, LLM→ds-flash
>>> /a planner          # Agent→planner, LLM→pro（不是 reasoner！绑定持久化）
>>> /a planner --reset  # 绑定恢复为 ds-reasoner
```
