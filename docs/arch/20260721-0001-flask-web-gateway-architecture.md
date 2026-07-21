# SceCode Flask Web Gateway 架构设计

> **日期**: 2026-07-21
> **方案概述**: 基于 Flask 构建类 OpenClaw 风格的 Web Gateway，将 SceCode 从 CLI REPL 升级为多会话、实时流式、气泡聊天界面的 Web 应用，每实现一个功能即交付对应测试。

---

## 1. 需求分析

### 1.1 用户明确需求

| # | 需求 | 说明 |
|---|------|------|
| R1 | 实时流式聊天 | AI 回复逐 token 流式显示，页面无需手动刷新 |
| R2 | SQL 会话存储 | 用 SQL 存储 session，每次启动自动读取，支持多 session 并存 |
| R3 | 气泡 UI + 工具卡片 | 对话框采用气泡样式；AI 调用工具时展示专门的工具调用 UI 卡片 |
| R4 | 左侧功能栏 | 可展开/收起，包含：切换 Agent、切换 Session、查看 Tools、查看 Skills |
| R5 | 右侧配置栏 | 可展开/收起，查看和修改当前 Agent 的配置 |
| R6 | 测试覆盖 | 每实现一个功能模块交付对应测试 |

### 1.2 架构师补充需求（对标 OpenClaw Web UI）

| # | 需求 | 说明 |
|---|------|------|
| R7 | 会话管理 CRUD | 创建、重命名、删除、归档/取消归档、置顶会话 |
| R8 | Markdown 渲染 | 消息内容支持 Markdown，代码块语法高亮（highlight.js） |
| R9 | 复制代码块 | 每条代码块右上角有"复制"按钮，点击复制到剪贴板 |
| R10 | 重新生成 | 对任意 AI 回复可"重新生成"，覆盖该回复并重试 |
| R11 | 停止生成 | 流式输出过程中可点击"停止"按钮中断生成 |
| R12 | 暗色/亮色主题 | 顶部栏主题切换按钮，偏好写入 localStorage + 数据库 |
| R13 | 消息搜索 | 支持在当前会话或全局搜索消息内容（关键词匹配） |
| R14 | Token 用量统计 | 每条消息记录 token 数，会话级和全局级用量面板 |
| R15 | 对话导出 | 导出当前会话为 Markdown 或 JSON 文件下载 |
| R16 | 系统提示词编辑器 | 右侧面板可查看和编辑当前 Agent 的 system_prompt |
| R17 | 工具权限开关 | 右侧面板可勾选/取消具体 Tool 的启用状态 |
| R18 | 模型参数调节 | 右侧面板可调 temperature、max_tokens、top_p 等参数 |
| R19 | 工作区文件浏览器 | 左侧面板可浏览 workspace 目录结构，点击预览文件内容 |
| R20 | 任务看板 | 独立页面，将 TaskTrackerTool 管理中的 TODO 列表可视化为看板卡片 |
| R21 | 键盘快捷键 | Ctrl+Enter 发送、Ctrl+K 命令面板、Ctrl+B 切换左侧栏、Ctrl+J 切换右侧栏、Esc 关闭面板 |
| R22 | 连接状态指示 | 顶部显示 WebSocket 连接状态（绿色已连接/红色断开/黄色重连中） |
| R23 | Toast 通知系统 | 操作反馈（成功/失败/警告）以右上角弹出 Toast 形式呈现 |
| R24 | 消息编辑重发 | 用户可编辑自己已发送的消息，修改后重新发送 |
| R25 | 对话分叉 | 从任意消息节点 fork 出新分支会话，保留原始会话不变 |
| R26 | 响应式布局 | 移动端自动折叠侧栏，聊天区占满屏幕 |
| R27 | 拖拽调整面板 | 左右侧栏宽度可拖拽调整 |
| R28 | 正在输入指示 | AI 思考时显示跳跃三点的"正在输入…"动画 |
| R29 | 推理过程展示 | 当使用 reasoning 模型时，可折叠展示模型的思考链（CoT） |
| R30 | API Key 管理 | 设置页面集中管理各模型的 API Key，密文显示可切换可见 |

---

## 2. 整体架构图

### 2.1 系统全景

```
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                              SceCode Web Gateway                                      │
│                                                                                       │
│  ┌─────────────────────────────────────────────────────────────────────────────────┐ │
│  │                              浏览器 (Frontend)                                    │ │
│  │                                                                                   │ │
│  │  ┌──────────┐  ┌──────────────────────────────┐  ┌──────────────┐               │ │
│  │  │ 左侧栏    │  │        聊天主区域              │  │ 右侧栏       │               │ │
│  │  │ (可收起)  │  │                              │  │ (可收起)     │               │ │
│  │  │          │  │  ┌─────────────────────────┐  │  │              │               │ │
│  │  │ 🔍 搜索  │  │  │    消息列表 (滚动)       │  │  │ Agent 配置   │               │ │
│  │  │ 💬 会话  │  │  │                         │  │  │              │               │ │
│  │  │ 🤖 Agent │  │  │  ┌───────────────────┐  │  │  │ - 模型选择   │               │ │
│  │  │ 🔧 工具  │  │  │  │ 用户气泡 (右对齐)  │  │  │  │ - 工具开关   │               │ │
│  │  │ 🎯 技能  │  │  │  └───────────────────┘  │  │  │ - 参数滑块   │               │ │
│  │  │ 📁 文件  │  │  │                         │  │  │ - 提示词编辑 │               │ │
│  │  │          │  │  │  ┌───────────────────┐  │  │  │ - 用量统计   │               │ │
│  │  │          │  │  │  │ AI 气泡 (左对齐)   │  │  │  └──────────────┘               │ │
│  │  │          │  │  │  │ + 工具调用卡片     │  │  │                                  │ │
│  │  │          │  │  │  └───────────────────┘  │  │                                  │ │
│  │  │          │  │  └─────────────────────────┘  │                                  │ │
│  │  │          │  │  ┌─────────────────────────┐  │                                  │ │
│  │  │          │  │  │ 输入框 + 发送/停止按钮   │  │                                  │ │
│  │  └──────────┘  │  └─────────────────────────┘  │                                  │ │
│  │                 └──────────────────────────────┘                                  │ │
│  └───────────────────────────────────────────────────────────────────────────────────┘ │
│                                          │                                              │
│                    HTTP (REST)            │           WebSocket (实时)                   │
│                                          │                                              │
│  ┌───────────────────────────────────────┼───────────────────────────────────────────┐ │
│  │                            Flask 应用服务器                                         │ │
│  │                                       │                                            │ │
│  │  ┌────────────────────────────────────┼──────────────────────────────────────┐    │ │
│  │  │                           路由层 (Routes)                                   │    │ │
│  │  │                                                                             │    │ │
│  │  │  /api/chat/*        /api/session/*      /api/agent/*      /api/tools/*     │    │ │
│  │  │  /api/skills/*      /api/files/*        /api/settings/*   /api/export/*    │    │ │
│  │  │  /api/tasks/*       /api/search/*       /api/stats/*                       │    │ │
│  │  │                                                                             │    │ │
│  │  │  /socket.io/chat/   ← WebSocket 事件 (send_message, stop, stream_token)     │    │ │
│  │  └──────────────────────────────┬──────────────────────────────────────────────┘    │ │
│  │                                 │                                                    │ │
│  │  ┌──────────────────────────────┼──────────────────────────────────────────────┐    │ │
│  │  │                        服务层 (Services)                                      │    │ │
│  │  │                                                                              │    │ │
│  │  │  ChatService    SessionService   AgentService    StreamService              │    │ │
│  │  │  ExportService  SearchService    FileService     StatsService               │    │ │
│  │  │  TaskService    SettingsService                                               │    │ │
│  │  └──────────────────────────────┬───────────────────────────────────────────────┘    │ │
│  │                                 │                                                    │ │
│  │  ┌──────────────────────────────┼──────────────────────────────────────────────┐    │ │
│  │  │                      核心适配层 (Core Adapter)                                 │    │ │
│  │  │                                                                              │    │ │
│  │  │  SessionManager         ← 管理多用户 Session，替代原 InitAi 单例              │    │ │
│  │  │  StreamCallbackHandler  ← 包装 OpenHands callbacks → 可迭代的 token 流        │    │ │
│  │  │  ToolEventFormatter     ← 将 Tool 调用事件格式化为前端可渲染的 JSON            │    │ │
│  │  └──────────────────────────────┬───────────────────────────────────────────────┘    │ │
│  │                                 │                                                    │ │
│  │  ┌──────────────────────────────┼──────────────────────────────────────────────┐    │ │
│  │  │                    SceCode 核心 (现有代码 — 最小改动)                          │    │ │
│  │  │                                                                              │    │ │
│  │  │  scripts/presets.py   (注册表)     scripts/initai.py   (实例化版本)          │    │ │
│  │  │  scripts/command.py   (指令解析)                                            │    │ │
│  │  └──────────────────────────────┬───────────────────────────────────────────────┘    │ │
│  │                                 │                                                    │ │
│  │  ┌──────────────────────────────┼──────────────────────────────────────────────┐    │ │
│  │  │                        OpenHands SDK                                          │    │ │
│  │  │                                                                              │    │ │
│  │  │  LLM  ←→  Agent  ←→  Tools (TerminalTool / FileEditorTool / TaskTracker)    │    │ │
│  │  │              ↕                                                               │    │ │
│  │  │         Conversation (对话实例)                                               │    │ │
│  │  └──────────────────────────────────────────────────────────────────────────────┘    │ │
│  └──────────────────────────────────────────────────────────────────────────────────────┘ │
│                                          │                                              │
│  ┌───────────────────────────────────────┼───────────────────────────────────────────┐ │
│  │                              数据层 (SQLite)                                       │ │
│  │                                                                                   │ │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐          │ │
│  │  │ Session  │  │ Message  │  │ AgentCfg │  │ ToolCfg  │  │ Setting  │          │ │
│  │  │   表     │  │    表    │  │    表    │  │    表    │  │    表    │          │ │
│  │  └──────────┘  └──────────┘  └──────────┘  └──────────┘  └──────────┘          │ │
│  │                                                                                   │ │
│  │  SQLite 文件: SceCode/data/scecode.db                                             │ │
│  └───────────────────────────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────────────────────┘
```

### 2.2 模块依赖图（Web 版）

```
                        ┌─────────────────┐
                        │   presets.py    │  (数据层 — 不改动)
                        │ LLM/Agent 注册表 │
                        └────┬───────┬────┘
                             │       │
              ┌──────────────┘       └──────────────┐
              ▼                                     ▼
      ┌──────────────┐                     ┌──────────────┐
      │  initai.py   │                     │  command.py  │  (逻辑层 — 轻度改造)
      │ (改为实例化)  │                     │ (dispatch)   │
      └──────┬───────┘                     └──────────────┘
             │
             ▼
      ┌──────────────────────────────────────────────────┐
      │              core_adapter/                        │  (新增 — Web 适配层)
      │  session_manager.py     ← 管理多用户会话实例       │
      │  stream_handler.py      ← 流式回调封装             │
      │  tool_formatter.py      ← 工具事件格式化            │
      └──────────────┬───────────────────────────────────┘
                     │
           ┌─────────┼─────────┐
           ▼         ▼         ▼
    ┌──────────┐ ┌───────┐ ┌──────────┐
    │ services/│ │models/│ │sockets/  │  (新增 — Web 层)
    └────┬─────┘ └───┬───┘ └────┬─────┘
         │           │          │
         ▼           ▼          ▼
    ┌──────────┐ ┌───────┐ ┌──────────┐
    │ routes/  │ │  DB   │ │ static/  │  (新增 — Web 层)
    └────┬─────┘ └───────┘ └────┬─────┘
         │                      │
         ▼                      ▼
    ┌──────────┐         ┌──────────┐
    │   app.py │         │templates/│  (新增 — 入口)
    └──────────┘         └──────────┘
```

依赖规则：
- 现有 `scripts/` 目录代码最小改动（`initai.py` 从类单例改为支持实例化）
- Web 层全部放在新的 `scecode_web/` 目录下，不污染现有结构
- Web 层依赖 scripts 层，scripts 层不感知 Web 层
- services 层是 routes 和 core_adapter 之间的桥梁

---

## 3. 目录结构设计

```
SceCode/
├── scripts/                        ← 现有 CLI 代码（最小改动）
│   ├── presets.py                  ← 不改动
│   ├── initai.py                   ← 改造：类单例 → 支持实例化
│   ├── command.py                  ← 轻度改造：提供非 print 版本
│   ├── main.py                     ← 不改动（CLI 入口保留）
│   └── .env                        ← 不改动
│
├── scecode_web/                    ← 新建：Web 应用全部代码
│   ├── __init__.py                 ← 包声明
│   ├── app.py                      ← Flask 工厂函数 create_app()
│   ├── config.py                   ← 配置管理（DB路径、SECRET_KEY、WS端口等）
│   │
│   ├── core_adapter/               ← Web 适配层（连接 scripts 和 Web）
│   │   ├── __init__.py
│   │   ├── session_manager.py      ← 多用户会话管理器（替代 InitAi 单例）
│   │   ├── stream_handler.py       ← 流式回调 → SSE/WS token 流
│   │   └── tool_formatter.py       ← OpenHands Tool 事件 → 前端 JSON schema
│   │
│   ├── models/                     ← SQLAlchemy ORM 模型
│   │   ├── __init__.py
│   │   ├── session.py              ← SessionModel (会话表)
│   │   ├── message.py              ← MessageModel (消息表)
│   │   ├── agent_config.py         ← AgentConfigModel (agent 配置表)
│   │   └── setting.py              ← SettingModel (用户设置表)
│   │
│   ├── services/                   ← 业务逻辑层
│   │   ├── __init__.py
│   │   ├── chat_service.py         ← 消息发送、流式生成、重新生成、停止
│   │   ├── session_service.py      ← 会话 CRUD、归档、置顶
│   │   ├── agent_service.py        ← Agent 配置读取/写入
│   │   ├── stream_service.py       ← SSE/WS 流管理
│   │   ├── file_service.py         ← 工作区文件浏览
│   │   ├── search_service.py       ← 消息搜索
│   │   ├── export_service.py       ← 对话导出 (MD/JSON)
│   │   ├── stats_service.py        ← Token 用量统计
│   │   └── settings_service.py     ← 用户设置管理
│   │
│   ├── routes/                     ← HTTP REST 路由
│   │   ├── __init__.py             ← Blueprint 注册
│   │   ├── chat_routes.py          ← /api/chat/*
│   │   ├── session_routes.py       ← /api/session/*
│   │   ├── agent_routes.py         ← /api/agent/*
│   │   ├── tool_routes.py          ← /api/tools/*
│   │   ├── file_routes.py          ← /api/files/*
│   │   ├── search_routes.py        ← /api/search/*
│   │   ├── export_routes.py        ← /api/export/*
│   │   ├── stats_routes.py         ← /api/stats/*
│   │   ├── settings_routes.py      ← /api/settings/*
│   │   └── pages.py                ← 页面渲染路由 (/, /settings, /tasks)
│   │
│   ├── sockets/                    ← WebSocket 事件处理
│   │   ├── __init__.py
│   │   └── chat_socket.py          ← send_message, stop_generation, typing 等事件
│   │
│   ├── templates/                  ← Jinja2 模板
│   │   ├── base.html               ← 基础布局（head, meta, 全局 CSS/JS 引用）
│   │   ├── index.html              ← 主聊天页（左-中-右三栏布局）
│   │   ├── pages/
│   │   │   ├── settings.html       ← 设置页（API Key 管理、主题、导出）
│   │   │   └── tasks.html          ← 任务看板页
│   │   └── components/
│   │       ├── chat_bubble.html    ← 聊天气泡组件（用户/AI 两种样式）
│   │       ├── tool_card.html      ← 工具调用卡片组件
│   │       ├── sidebar_left.html   ← 左侧栏组件
│   │       ├── sidebar_right.html  ← 右侧栏组件
│   │       ├── session_item.html   ← 会话列表项组件
│   │       ├── file_tree.html      ← 文件树组件
│   │       └── toast.html          ← Toast 通知组件
│   │
│   ├── static/                     ← 静态资源
│   │   ├── css/
│   │   │   ├── main.css            ← 全局样式、CSS 变量、主题
│   │   │   ├── chat.css            ← 聊天气泡、消息列表样式
│   │   │   ├── sidebar.css         ← 左右侧栏样式
│   │   │   ├── tools.css           ← 工具卡片样式
│   │   │   ├── markdown.css        ← Markdown 渲染样式
│   │   │   └── mobile.css          ← 响应式/移动端样式
│   │   └── js/
│   │       ├── app.js              ← 应用初始化、全局事件总线
│   │       ├── chat.js             ← 聊天核心逻辑（发送、接收、渲染）
│   │       ├── stream.js           ← WebSocket/SSE 流管理
│   │       ├── sidebar.js          ← 侧栏展开/收起/拖拽
│   │       ├── session.js          ← 会话列表、切换、CRUD
│   │       ├── bubble.js           ← 气泡渲染（Markdown + 代码高亮）
│   │       ├── tool_card.js        ← 工具卡片渲染和交互
│   │       ├── settings.js         ← 设置面板逻辑
│   │       ├── file_browser.js     ← 文件树浏览
│   │       ├── search.js           ← 消息搜索
│   │       ├── shortcuts.js        ← 键盘快捷键
│   │       ├── toast.js            ← Toast 通知
│   │       ├── theme.js            ← 主题切换
│   │       └── utils.js            ← 通用工具函数
│   │
│   └── data/                       ← 运行时数据目录
│       └── .gitkeep                ← scecode.db 在此生成（gitignore）
│
├── tests/                          ← 新建：测试目录
│   ├── __init__.py
│   ├── conftest.py                 ← pytest fixtures（app、client、db、sample session）
│   ├── test_presets.py             ← 现有 presets.py 的测试
│   ├── test_initai.py              ← 改造后 initai.py 的测试（实例化）
│   ├── test_command.py             ← 现有 command.py 的测试
│   ├── test_session_manager.py     ← session_manager 测试
│   ├── test_stream_handler.py      ← stream_handler 测试
│   ├── test_tool_formatter.py      ← tool_formatter 测试
│   ├── test_models/                ← ORM 模型测试
│   │   ├── test_session_model.py
│   │   ├── test_message_model.py
│   │   ├── test_agent_config_model.py
│   │   └── test_setting_model.py
│   ├── test_routes/                ← 路由测试
│   │   ├── test_chat_routes.py
│   │   ├── test_session_routes.py
│   │   ├── test_agent_routes.py
│   │   ├── test_tool_routes.py
│   │   ├── test_file_routes.py
│   │   ├── test_search_routes.py
│   │   ├── test_export_routes.py
│   │   ├── test_stats_routes.py
│   │   └── test_settings_routes.py
│   ├── test_services/              ← 服务层测试
│   │   ├── test_chat_service.py
│   │   ├── test_session_service.py
│   │   ├── test_agent_service.py
│   │   └── test_export_service.py
│   └── test_sockets/               ← WebSocket 测试
│       └── test_chat_socket.py
│
├── docs/
│   ├── arch/                       ← 架构文档（本文件在此）
│   └── answer/
│
└── README.md
```

**关键设计约束**：
- `scripts/` 目录下除 `initai.py` 外**不做任何改动**——保护现有 CLI 功能
- `initai.py` 仅做最小改造：从**类单例**改为**支持实例化**（类方法 → 实例方法），保留类方法作为兼容层
- 所有 Web 代码集中在 `scecode_web/`，所有测试集中在 `tests/`
- `command.py` 保留不变——Web 端通过 API 调用，不经过 CLI 指令系统

---

## 4. 数据库设计

### 4.1 ER 图

```
┌─────────────────┐       ┌─────────────────────────┐
│    Session      │       │       Message           │
├─────────────────┤       ├─────────────────────────┤
│ id (PK)         │──1:N──│ id (PK)                 │
│ name            │       │ session_id (FK)         │
│ agent_name      │       │ role (user/assistant/   │
│ model_name      │       │       tool/system)      │
│ is_archived     │       │ content (TEXT)          │
│ is_pinned       │       │ tool_name (nullable)    │
│ created_at      │       │ tool_input (JSON, null) │
│ updated_at      │       │ tool_output (JSON, null)│
│ total_tokens    │       │ token_count             │
└─────────────────┘       │ parent_message_id (FK)  │
                          │ is_regenerated          │
                          │ is_fork_point           │
                          │ created_at              │
                          └─────────────────────────┘

┌──────────────────┐      ┌──────────────────┐
│   AgentConfig    │      │    Setting       │
├──────────────────┤      ├──────────────────┤
│ id (PK)          │      │ id (PK)          │
│ session_id (FK)  │      │ key (UNIQUE)     │
│ agent_name       │      │ value (TEXT)     │
│ model_name       │      │ updated_at       │
│ system_prompt    │      └──────────────────┘
│ temperature      │
│ max_tokens       │
│ top_p            │
│ enabled_tools    │      (JSON array)
│ extra_params     │      (JSON object)
│ updated_at       │
└──────────────────┘
```

### 4.2 表结构详细定义

**Session 表**：
| 列名 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | TEXT (UUID) | PK | 会话唯一标识 |
| name | TEXT | NOT NULL, DEFAULT '新会话' | 会话名称 |
| agent_name | TEXT | NOT NULL, DEFAULT 'coder' | 绑定的 Agent |
| model_name | TEXT | NOT NULL, DEFAULT 'ds-flash' | 绑定的 LLM |
| is_archived | BOOLEAN | DEFAULT FALSE | 是否归档 |
| is_pinned | BOOLEAN | DEFAULT FALSE | 是否置顶 |
| created_at | DATETIME | NOT NULL | 创建时间 |
| updated_at | DATETIME | NOT NULL | 最后活动时间 |
| total_tokens | INTEGER | DEFAULT 0 | 累计 token 消耗 |

**Message 表**：
| 列名 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | INTEGER | PK, AUTOINCREMENT | 消息 ID |
| session_id | TEXT | FK → Session.id, NOT NULL | 所属会话 |
| role | TEXT | NOT NULL | user / assistant / tool / system |
| content | TEXT | NULLABLE | 消息正文（Markdown） |
| tool_name | TEXT | NULLABLE | 工具名称（role=tool 时） |
| tool_input | TEXT (JSON) | NULLABLE | 工具输入参数 |
| tool_output | TEXT (JSON) | NULLABLE | 工具输出结果 |
| token_count | INTEGER | DEFAULT 0 | 该消息消耗 token |
| parent_message_id | INTEGER | FK → Message.id, NULLABLE | 重新生成时指向上一个版本 |
| is_regenerated | BOOLEAN | DEFAULT FALSE | 是否已被重新生成覆盖 |
| is_fork_point | BOOLEAN | DEFAULT FALSE | 是否被 fork 过 |
| created_at | DATETIME | NOT NULL | 创建时间 |

**AgentConfig 表**：
| 列名 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | INTEGER | PK, AUTOINCREMENT | 配置 ID |
| session_id | TEXT | FK → Session.id, UNIQUE | 一对一关联会话 |
| agent_name | TEXT | NOT NULL | Agent 名称 |
| model_name | TEXT | NOT NULL | 模型名称 |
| system_prompt | TEXT | NULLABLE | 自定义系统提示词 |
| temperature | REAL | NULLABLE | 温度参数 |
| max_tokens | INTEGER | NULLABLE | 最大输出 token |
| top_p | REAL | NULLABLE | Top-P 参数 |
| enabled_tools | TEXT (JSON) | NOT NULL | 启用的工具列表 |
| extra_params | TEXT (JSON) | NULLABLE | 扩展参数 |
| updated_at | DATETIME | NOT NULL | 更新时间 |

**Setting 表**（键值存储，用于用户级全局设置）：
| 列名 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | INTEGER | PK, AUTOINCREMENT | ID |
| key | TEXT | UNIQUE, NOT NULL | 设置键 |
| value | TEXT | NOT NULL | 设置值（JSON string） |
| updated_at | DATETIME | NOT NULL | 更新时间 |

常用 Setting 键：
- `theme`: `"dark"` / `"light"`
- `sidebar_left_width`: `"280"` (px)
- `sidebar_right_width`: `"320"` (px)
- `last_active_session_id`: UUID 字符串
- `api_keys`: `{"deepseek": "sk-***", "openai": "sk-***"}` (加密存储)

---

## 5. 核心适配层设计

### 5.1 SessionManager（替代 InitAi 单例）

当前问题：`InitAi` 使用**类属性**作为模块级单例，所有用户共享同一个 LLM/Agent/Conversation。

解决方案：`SessionManager` 管理一个 `Dict[str, SessionContext]` 的映射。

```
SessionManager
├── _sessions: Dict[str, SessionContext]
│   └── key = session_id (UUID)
│   └── value = SessionContext
│       ├── llm: LLM
│       ├── agent: Agent
│       ├── conversation: Conversation
│       ├── bindings: Dict[str, str]      ← Agent-Model 绑定（与 InitAi._bindings 同义）
│       ├── current_llm_name: str
│       ├── current_agent_name: str
│       └── agent_config: AgentConfig     ← 来自 DB 的配置
│
├── get_or_create(session_id: str) → SessionContext
├── switch_agent(session_id: str, agent_name: str) → bool
├── switch_model(session_id: str, model_name: str) → bool
├── reset_binding(session_id: str, agent_name: str) → bool
├── get_status(session_id: str) → dict
├── destroy(session_id: str) → bool
└── get_all_active() → List[str]
```

**与 InitAi 的关系**：
- `initai.py` 中的 `InitAi` 保留类方法，作为对 `SessionManager` 的薄封装（向后兼容 CLI）
- `SessionManager` 内部调用 `presets.py` 的 `create_llm()` 和 `create_agent()`
- `InitAi` 的类方法内部持有唯一的 `SessionManager` 实例

### 5.2 StreamCallbackHandler（流式回调封装）

OpenHands SDK 的 `Conversation` 构造函数接受 `callbacks` 参数。我们需要将其封装为可迭代的流。

```
StreamCallbackHandler
├── __init__(callbacks: List[Callable])
├── on_token(token: str)              ← token 级流式回调
├── on_tool_start(tool_name: str, input: dict)
├── on_tool_end(tool_name: str, output: dict)
├── on_thinking(text: str)            ← reasoning 模型的思考过程
├── on_complete(final_response: str)
├── on_error(error: Exception)
│
└── 与外部通信方式（二选一）:
    ├── 方案 A: queue.Queue — 生成者线程 put，消费者(Flask) get
    └── 方案 B: AsyncGenerator — asyncio 异步生成器
```

### 5.3 ToolEventFormatter（工具事件格式化）

将 OpenHands SDK 内部不同 Tool 的调用事件转换为前端统一 JSON schema：

```
ToolEventFormatter
├── format_tool_call(tool_name: str, input: dict) → ToolCallCard
│   └── ToolCallCard: {type, icon, title, summary, detail, status}
├── format_tool_result(tool_name: str, output: dict) → ToolResultCard
│   └── ToolResultCard: {type, success, summary, detail, code_snippet?}
└── Tool → Icon/Color 映射表:
    ├── TerminalTool      → 🖥️ 终端 (色: #1a1a2e)
    ├── FileEditorTool    → 📝 文件编辑 (色: #16213e)
    └── TaskTrackerTool   → 📋 任务追踪 (色: #0f3460)
```

---

## 6. API 接口设计

### 6.1 REST API 一览

| 方法 | 路径 | 说明 | 请求体 | 响应 |
|------|------|------|--------|------|
| **聊天** |||||
| POST | `/api/chat/send` | 发送消息（非流式） | `{session_id, message}` | `{message_id, content}` |
| GET | `/api/chat/history/<session_id>` | 获取消息历史 | - | `{messages: [...]}` |
| POST | `/api/chat/regenerate/<message_id>` | 重新生成回复 | `{session_id}` | `{new_message_id}` |
| POST | `/api/chat/stop` | 停止生成 | `{session_id}` | `{success}` |
| POST | `/api/chat/edit/<message_id>` | 编辑重发 | `{session_id, new_content}` | `{new_message_id}` |
| POST | `/api/chat/fork/<message_id>` | 从指定消息分叉 | `{session_id, new_session_name}` | `{new_session_id}` |
| **会话** |||||
| GET | `/api/session/list` | 获取会话列表 | - | `{sessions: [...]}` |
| POST | `/api/session/create` | 创建新会话 | `{name, agent_name?}` | `{session}` |
| PUT | `/api/session/<id>` | 更新会话 | `{name?, is_archived?, is_pinned?}` | `{session}` |
| DELETE | `/api/session/<id>` | 删除会话 | - | `{success}` |
| **Agent** |||||
| GET | `/api/agent/list` | 列出可用 Agent | - | `{agents: [...]}` |
| GET | `/api/agent/config/<session_id>` | 获取 Agent 配置 | - | `{config}` |
| PUT | `/api/agent/switch` | 切换 Agent | `{session_id, agent_name}` | `{new_config}` |
| PUT | `/api/agent/model` | 切换模型 | `{session_id, model_name}` | `{new_config}` |
| PUT | `/api/agent/config/<session_id>` | 更新 Agent 配置 | `{temperature?, max_tokens?, ...}` | `{config}` |
| PUT | `/api/agent/prompt/<session_id>` | 更新系统提示词 | `{system_prompt}` | `{success}` |
| POST | `/api/agent/reset-binding` | 重置 Agent-Model 绑定 | `{session_id, agent_name}` | `{success}` |
| **工具** |||||
| GET | `/api/tools/list` | 列出所有可用工具 | - | `{tools: [{name, description, icon}]}` |
| GET | `/api/tools/status/<session_id>` | 获取工具启用状态 | - | `{tools: [{name, enabled}]}` |
| PUT | `/api/tools/toggle` | 切换工具启用 | `{session_id, tool_name, enabled}` | `{success}` |
| **文件** |||||
| GET | `/api/files/tree` | 获取工作区目录树 | `?path=` | `{tree: [...]}` |
| GET | `/api/files/read` | 读取文件内容 | `?path=` | `{content, language}` |
| **搜索** |||||
| GET | `/api/search` | 搜索消息 | `?q=&session_id=&limit=` | `{results: [...]}` |
| **导出** |||||
| GET | `/api/export/<session_id>` | 导出会话 | `?format=md\|json` | 文件下载 |
| **统计** |||||
| GET | `/api/stats/session/<session_id>` | 会话用量统计 | - | `{tokens, messages, tools_used}` |
| GET | `/api/stats/global` | 全局用量统计 | - | `{total_tokens, total_sessions, ...}` |
| **设置** |||||
| GET | `/api/settings` | 获取所有设置 | - | `{settings: {...}}` |
| PUT | `/api/settings` | 更新设置 | `{key, value}` | `{success}` |
| **任务** |||||
| GET | `/api/tasks/<session_id>` | 获取任务列表 | - | `{tasks: [...]}` |
| **页面** |||||
| GET | `/` | 主聊天页面 | - | HTML |
| GET | `/settings` | 设置页面 | - | HTML |
| GET | `/tasks/<session_id>` | 任务看板页 | - | HTML |

### 6.2 WebSocket 事件

| 事件名 | 方向 | 数据结构 | 说明 |
|--------|------|----------|------|
| `send_message` | Client→Server | `{session_id: str, message: str}` | 发送消息触发流式生成 |
| `stop_generation` | Client→Server | `{session_id: str}` | 中断当前生成 |
| `stream_token` | Server→Client | `{message_id: int, token: str, is_first: bool}` | 逐 token 推送 |
| `tool_call_start` | Server→Client | `{message_id: int, tool_name: str, input: dict, icon: str, color: str}` | 工具调用开始 |
| `tool_call_end` | Server→Client | `{message_id: int, tool_name: str, output: dict, success: bool}` | 工具调用结束 |
| `thinking` | Server→Client | `{session_id: str, text: str}` | 推理过程 |
| `message_complete` | Server→Client | `{message_id: int, full_content: str, token_count: int}` | 消息生成完成 |
| `generation_error` | Server→Client | `{session_id: str, error: str}` | 生成出错 |
| `agent_status` | Server→Client | `{session_id: str, agent_name: str, model_name: str, tools: [...]}` | 配置变更通知 |
| `typing` | Client→Server | `{session_id: str, is_typing: bool}` | 用户正在输入 |
| `connection_status` | Server→Client | `{status: 'connected'\|'reconnecting'\|'disconnected'}` | 连接状态 |

### 6.3 接口数据类型（类型注解风格，不含实现）

```python
# 请求/响应数据类型定义（概念层，不包含实际代码）

# ── 请求类型 ──
SendMessageRequest:
    session_id: str          # UUID
    message: str             # 用户消息正文
    # 响应：由 WebSocket stream_token 事件推送，最终 message_complete 事件关闭

RegenerateRequest:
    session_id: str
    message_id: int          # 要重新生成的 AI 消息 ID

StopRequest:
    session_id: str

EditResendRequest:
    session_id: str
    new_content: str

ForkRequest:
    session_id: str
    new_session_name: str

CreateSessionRequest:
    name: str | None
    agent_name: str | None

UpdateSessionRequest:
    name: str | None
    is_archived: bool | None
    is_pinned: bool | None

SwitchAgentRequest:
    session_id: str
    agent_name: str          # coder | planner | executor | long

SwitchModelRequest:
    session_id: str
    model_name: str          # ds-flash | ds-chat | ds-reasoner | ds-pro

UpdateAgentConfigRequest:
    temperature: float | None
    max_tokens: int | None
    top_p: float | None
    enabled_tools: list[str] | None

UpdatePromptRequest:
    system_prompt: str

ToggleToolRequest:
    session_id: str
    tool_name: str
    enabled: bool

SearchRequest:
    q: str
    session_id: str | None
    limit: int  # default 20

ExportRequest:
    format: str  # "md" | "json"

UpdateSettingRequest:
    key: str
    value: str   # JSON string

# ── 响应类型 ──
SessionResponse:
    id: str
    name: str
    agent_name: str
    model_name: str
    is_archived: bool
    is_pinned: bool
    created_at: str       # ISO 8601
    updated_at: str
    total_tokens: int
    message_count: int

MessageResponse:
    id: int
    session_id: str
    role: str             # user | assistant | tool | system
    content: str | None
    tool_name: str | None
    tool_input: dict | None
    tool_output: dict | None
    token_count: int
    parent_message_id: int | None
    is_regenerated: bool
    is_fork_point: bool
    created_at: str

AgentConfigResponse:
    session_id: str
    agent_name: str
    model_name: str
    system_prompt: str | None
    temperature: float | None
    max_tokens: int | None
    top_p: float | None
    enabled_tools: list[str]
    available_agents: list[str]
    available_models: list[str]
    bindings: dict[str, str]   # agent_name → model_name
    default_bindings: dict[str, str]

ToolInfo:
    name: str
    description: str
    icon: str
    color: str
    category: str          # execution | file | task

ToolStatusResponse:
    session_id: str
    tools: list[{name: str, enabled: bool, info: ToolInfo}]

FileTreeNode:
    name: str
    path: str
    type: str              # file | directory
    size: int | None
    children: list[FileTreeNode] | None   # 仅目录有

SearchResult:
    message_id: int
    session_id: str
    session_name: str
    role: str
    content_preview: str   # 匹配上下文前后各 50 字
    created_at: str

StatsResponse:
    session_id: str
    total_tokens: int
    message_count: int
    user_message_count: int
    assistant_message_count: int
    tool_call_count: int
    tools_used: dict[str, int]  # tool_name → 使用次数

GlobalStatsResponse:
    total_tokens: int
    total_sessions: int
    total_messages: int
    active_sessions: int
    per_session: list[StatsResponse]

TaskInfo:
    id: str
    title: str
    status: str            # todo | in_progress | done | cancelled
    description: str
    subtasks: list[TaskInfo]
```

---

## 7. 数据流设计

### 7.1 主流程：用户发送消息 → AI 流式回复

```
用户输入消息 "帮我创建一个 Flask 项目"
       │
       ▼
┌──────────────────────────────────────────────────────────────┐
│ 浏览器                                                        │
│                                                               │
│ 1. chat.js 监听 Enter / 点击发送                               │
│ 2. 在消息列表末尾插入用户气泡 (role=user, 右对齐)               │
│ 3. 插入空的 AI 气泡 (role=assistant, 左对齐, 显示"…"输入指示)  │
│ 4. 发出 WebSocket 事件: send_message                          │
│    {session_id: "abc-123", message: "帮我创建一个 Flask 项目"}  │
│ 5. [等待 stream_token 事件...]                                 │
│ 6. stream.js 收到 token → bubble.js 追加到 AI 气泡             │
│ 7. 如果收到 tool_call_start → tool_card.js 渲染工具卡片        │
│ 8. 如果收到 tool_call_end → 更新工具卡片状态 (✓ 完成 / ✗ 失败) │
│ 9. 收到 message_complete → 标记完成, 移除输入指示               │
│ 10. 自动滚动到最新消息                                         │
└──────────────────┬───────────────────────────────────────────┘
                   │ WebSocket
                   ▼
┌──────────────────────────────────────────────────────────────┐
│ Flask 服务器                                                   │
│                                                               │
│ sockets/chat_socket.py:                                       │
│   on_send_message(data):                                      │
│     1. 验证 session_id                                       │
│     2. 保存用户消息到 DB (role=user)                           │
│     3. 调用 ChatService.send_stream(session_id, message)      │
│                                                               │
│ services/chat_service.py:                                     │
│   ChatService.send_stream(session_id, message):               │
│     1. 从 SessionManager 获取 SessionContext                   │
│     2. 创建 StreamCallbackHandler 实例                        │
│     3. 在新线程中调用 context.conversation.send_message()     │
│        + conversation.run(callbacks=[handler])                │
│     4. handler 通过 queue 将事件传回主线程                     │
│     5. 主线程通过 Socket.IO emit 推送给客户端                  │
│     6. 生成完成后，保存 AI 消息到 DB (role=assistant)          │
│     7. 保存工具调用消息到 DB (role=tool)                       │
│                                                               │
│ core_adapter/stream_handler.py:                                │
│   StreamCallbackHandler:                                      │
│     - on_token(token) → emit("stream_token", {token})         │
│     - on_tool_start(name, input) → emit("tool_call_start")    │
│     - on_tool_end(name, output) → emit("tool_call_end")       │
│     - on_complete(content) → emit("message_complete")         │
│     - on_error(e) → emit("generation_error")                  │
└──────────────────────────────────────────────────────────────┘
```

### 7.2 会话切换流程

```
用户点击左侧栏会话 "项目A"
       │
       ▼
session.js 发出: GET /api/session/list
       │
       ▼
session_routes.py → SessionService.get_all_sessions()
       │
       ▼
返回 [{id: "a1", name: "项目A", ...}, {id: "b2", name: "调试B", ...}]
       │
       ▼
左侧栏渲染会话列表
       │
       ▼
用户点击 "项目A"
       │
session.js 发出: GET /api/chat/history/a1
       │
       ▼
chat_routes.py → ChatService.get_history("a1")
       │
       ▼
从 DB 查询 Message WHERE session_id = "a1" ORDER BY created_at
       │
       ▼
返回 messages: [{role: "user", content: "..."}, {role: "assistant", content: "..."}, ...]
       │
       ▼
bubble.js 清空聊天区，逐条渲染气泡
       │
       ▼
session.js 发出: GET /api/agent/config/a1  → 更新右侧栏显示
       │
       ▼
WebSocket join room: socket.emit("join", {session_id: "a1"})
```

### 7.3 重新生成流程

```
用户点击某条 AI 消息的 "⟳ 重新生成" 按钮
       │
       ▼
chat.js 发出: POST /api/chat/regenerate/42  body: {session_id: "a1"}
       │
       ▼
chat_routes.py → ChatService.regenerate("a1", message_id=42):
    1. 查询 message 42，找到它的 parent_message_id (假设=38，即此 AI 回复对应的用户消息)
    2. 如果 message 42 没有 parent，则向前找最近的 user 消息作为"锚点"
    3. 标记 message 42: is_regenerated = TRUE
    4. 标记 message 42 及之后所有消息: is_regenerated = TRUE
    5. 从 DB 中删除这些被标记的消息的后续链（保持 DB 干净）
    6. 重新获取锚点消息的 content
    7. 调用 send_stream(session_id, anchor_content)
    → 新的 AI 回复插入到原位置
       │
       ▼
WebSocket 推送新的 stream_token → 前端在消息 42 原位替换内容
```

### 7.4 Fork 分叉流程

```
用户点击某条消息的 "⑂ 分叉" 按钮
       │
       ▼
chat.js 弹出输入框: "新会话名称"
       │
       ▼
POST /api/chat/fork/25  body: {session_id: "a1", new_session_name: "项目A-方案2"}
       │
       ▼
chat_routes.py → ChatService.fork("a1", message_id=25, "项目A-方案2"):
    1. 创建新 Session (new_id = UUID)
    2. 复制原 Session 的 AgentConfig
    3. 复制 message 1~25 到新 Session
    4. 标记原消息 25: is_fork_point = TRUE
    5. 返回 new_session_id
       │
       ▼
前端自动切换到新会话（触发会话切换流程）
```

---

## 8. 前端组件树与交互设计

### 8.1 页面布局（三层结构）

```
┌──────────────────────────────────────────────────────────────────────┐
│  ┌──────────────────────────────────────────────────────────────────┐│
│  │                        顶部导航栏 (固定 48px)                      ││
│  │                                                                    ││
│  │  ☰ 切换侧栏  │  SceCode Chat              │  🌙 主题  │  ⚙ 设置   ││
│  │              │  [● 已连接]                 │           │          ││
│  └──────────────────────────────────────────────────────────────────┘│
│  ┌────────┐ ┌──────────────────────────────┐ ┌──────────────────────┐│
│  │        │ │                               │ │                      ││
│  │ 左侧栏 │ │         聊天主区域              │ │       右侧栏         ││
│  │        │ │                               │ │                      ││
│  │ 280px  │ │  ┌─────────────────────────┐  │ │       320px          ││
│  │        │ │  │     消息列表 (flex-1)    │  │ │                      ││
│  │ 可拖拽 │ │  │                         │  │ │  可拖拽              ││
│  │        │ │  │  ┌─────────────────┐    │  │ │                      ││
│  │ [搜索] │ │  │  │    AI 气泡       │    │  │ │  🤖 Agent 配置       ││
│  │        │ │  │  │  ┌───────────┐  │    │  │ │  ┌────────────────┐  ││
│  │ [会话] │ │  │  │  │ 工具卡片   │  │    │  │ │  │ 模型: ds-pro ▼ │  ││
│  │  ├ 项目A│ │  │  │  └───────────┘  │    │  │ │  └────────────────┘  ││
│  │  ├ 调试B│ │  │  │    AI 继续...   │    │  │ │                      ││
│  │  └ 新会话│ │  │  └─────────────────┘    │  │ │  🔧 工具管理         ││
│  │        │ │  │                         │  │ │  ├ ☑ TerminalTool   ││
│  │ [Agent]│ │  │  ┌─────────────────┐    │  │ │  ├ ☑ FileEditorTool ││
│  │  ├ coder│ │  │  │   用户气泡(右)   │    │  │ │  └ ☐ TaskTracker   ││
│  │  ├ plan │ │  │  └─────────────────┘    │  │ │                      ││
│  │  └ exec │ │  └─────────────────────────┘  │ │  ⚙ 模型参数          ││
│  │        │ │                                │ │  temp: ──●── 0.7   ││
│  │ [工具] │ │  ┌─────────────────────────┐  │ │  max_t: ──●── 4096  ││
│  │  ├终端  │ │  │ 输入框 │ 发送 │ 停止    │  │ │  top_p: ──●── 0.9   ││
│  │  └编辑器│ │  └─────────────────────────┘  │ │                      ││
│  │        │ │                               │ │  📝 系统提示词         ││
│  │ [技能] │ │                               │ │  ┌────────────────┐  ││
│  │  ├ xxx │ │                               │ │  │ 可编辑文本区    │  ││
│  │  └ yyy │ │                               │ │  └────────────────┘  ││
│  │        │ │                               │ │                      ││
│  │ [文件] │ │                               │ │  📊 用量统计          ││
│  │  ├ dir │ │                               │ │  tokens: 12.5k      ││
│  │  └ ... │ │                               │ │  msgs:  34          ││
│  └────────┘ └──────────────────────────────┘ └──────────────────────┘│
└──────────────────────────────────────────────────────────────────────┘
```

### 8.2 组件层级树

```
index.html
├── 顶部导航栏 (TopBar)
│   ├── 侧栏切换按钮 (ToggleSidebarButton ×2)
│   ├── 应用标题 (AppTitle)
│   ├── 连接状态指示器 (ConnectionIndicator) [绿/黄/红圆点]
│   ├── 主题切换按钮 (ThemeToggle) [☀/🌙]
│   └── 设置齿轮按钮 (SettingsButton) [⚙]
│
├── 左侧栏 (LeftSidebar) [collapsible]
│   ├── 搜索框 (SearchBox)
│   │   └── 搜索结果下拉 (SearchDropdown)
│   ├── 会话区域 (SessionPanel)
│   │   ├── 区域标题 "💬 会话" + 新建按钮 [+]
│   │   └── 会话列表 (SessionList)
│   │       └── 会话项 (SessionItem) × N
│   │           ├── 会话名称 (可双击重命名)
│   │           ├── 消息预览
│   │           ├── 时间戳
│   │           ├── 置顶标记 📌
│   │           └── 右键菜单: [重命名 | 归档 | 导出 | 删除]
│   ├── Agent 面板 (AgentPanel)
│   │   ├── 区域标题 "🤖 Agent"
│   │   └── Agent 列表 (AgentList)
│   │       └── Agent 项 × N (当前 active 高亮)
│   ├── 工具面板 (ToolsPanel)
│   │   ├── 区域标题 "🔧 工具"
│   │   └── 工具列表 (ToolList)
│   │       └── 工具项 × N (显示名称+图标+状态点)
│   ├── 技能面板 (SkillsPanel)
│   │   ├── 区域标题 "🎯 技能"
│   │   └── 技能列表 (SkillList)
│   └── 文件浏览器 (FileBrowser)
│       ├── 区域标题 "📁 文件"
│       └── 文件树 (FileTree)
│           └── FileTreeNode × N (可展开/折叠)
│
├── 聊天主区域 (ChatArea)
│   ├── 消息列表 (MessageList) [scrollable, flex-1]
│   │   └── 消息 (MessageItem) × N
│   │       ├── 用户消息气泡 (UserBubble) [右对齐, 蓝/紫色背景]
│   │       │   ├── 消息内容 (Markdown 渲染)
│   │       │   ├── 操作按钮组 (悬停显示): [✏编辑 | 🔄重新发送]
│   │       │   └── 时间戳
│   │       └── AI 消息气泡 (AIBubble) [左对齐, 灰/暗色背景]
│   │           ├── 推理过程 (ThinkingBlock) [可折叠, 仅 reasoning 模型]
│   │           │   ├── 折叠/展开按钮 "🧠 思考过程"
│   │           │   └── 推理文本
│   │           ├── 消息内容 (Markdown 渲染 + highlight.js)
│   │           │   └── 代码块 (CodeBlock)
│   │           │       ├── 语言标签
│   │           │       └── 复制按钮 (CopyButton) [📋]
│   │           ├── 嵌套工具卡片 (ToolCard) [出现在 AI 调用工具时]
│   │           │   ├── 工具头部 (ToolHeader): 图标 + 工具名 + 状态
│   │           │   ├── 输入区域 (ToolInput) [可折叠]
│   │           │   └── 输出区域 (ToolOutput) [可折叠]
│   │           ├── 操作按钮组 (悬停显示): [⟳重新生成 | ⑂分叉 | 📋复制]
│   │           ├── Token 用量标签
│   │           └── 时间戳
│   ├── "滚动到底部" 浮动按钮 (ScrollToBottom) [未在底部时显示]
│   └── 输入区域 (InputArea) [固定底部]
│       ├── 多行输入框 (TextArea) [auto-resize]
│       ├── 发送按钮 (SendButton) [▶]
│       └── 停止按钮 (StopButton) [■, 仅生成中显示]
│
├── 右侧栏 (RightSidebar) [collapsible]
│   ├── Agent 配置区 (AgentConfigPanel)
│   │   ├── 区域标题 "🤖 Agent 配置"
│   │   ├── Agent 选择器 (AgentSelector) [下拉菜单]
│   │   ├── 模型选择器 (ModelSelector) [下拉菜单 + 绑定标记]
│   │   ├── Agent-Model 绑定表 (BindingTable)
│   │   │   └── 绑定行 × N: agent_name → model_name [* 表示非默认]
│   │   ├── 绑定重置按钮 (ResetBindingButton)
│   │   └── 参数调节区 (ParamSliders)
│   │       ├── Temperature 滑块
│   │       ├── Max Tokens 滑块
│   │       └── Top-P 滑块
│   ├── 工具启用区 (ToolTogglePanel)
│   │   ├── 区域标题 "🔧 启用的工具"
│   │   └── 工具开关列表
│   │       └── 工具开关项 (ToolToggleItem) × N
│   ├── 系统提示词区 (PromptEditor)
│   │   ├── 区域标题 "📝 系统提示词"
│   │   ├── 文本编辑区 (CodeMirror / TextArea)
│   │   └── 保存/重置按钮
│   └── 用量统计区 (StatsPanel)
│       ├── 区域标题 "📊 会话用量"
│       ├── Token 总量
│       ├── 消息数量
│       └── 工具调用次数
│
└── Toast 容器 (ToastContainer) [fixed 右上角]
    └── Toast 通知 (ToastItem) × N [自动消失 3s]
        ├── 图标 (✓ / ✗ / ⚠)
        └── 消息文字
```

### 8.3 交互状态矩阵

| 组件 | 状态 | 说明 |
|------|------|------|
| AIBubble | default / streaming / completed / error | 流式输出中显示闪烁光标，完成移除光标，错误显示红色边框 |
| ToolCard | running / success / failed | 运行中显示旋转动画，成功显示绿色勾，失败显示红色叉 |
| SendButton | enabled / disabled / hidden | 生成中变为 StopButton |
| SessionItem | normal / active / archived | active 高亮，archived 半透明 |
| ConnectionIndicator | connected / reconnecting / disconnected | 对应绿色/黄色/红色圆点 |
| LeftSidebar | expanded / collapsed / dragging | 拖拽时半透明预览 |
| RightSidebar | expanded / collapsed / dragging | 同上 |
| InputArea | idle / composing / sending | composing 时显示字符计数，sending 时输入框变灰 |
| ToastItem | entering / visible / exiting | 入场滑入→停留→出场淡出 |

---

## 9. initai.py 改造方案

### 9.1 当前问题

```python
class InitAi:
    llm: LLM | None = None          # ← 类属性，全局唯一
    agent: Agent | None = None      # ← 类属性，全局唯一
    conversation = ...              # ← 类属性，全局唯一
```

Web 多用户场景下需要每个 session 独立持有自己的 LLM/Agent/Conversation。

### 9.2 改造策略：实例化 + 兼容层

```
改造后 InitAi 结构:

class InitAi:
    """每个实例代表一个独立的 AI 会话上下文。
    保留类方法作为 CLI 的向后兼容层，内部委托给默认实例。
    """

    # ── 实例属性（Web 多会话场景）──
    def __init__(self, workspace: str | None = None):
        self.current_llm_name   = DEFAULT_LLM
        self.current_agent_name = DEFAULT_AGENT
        self.llm                = create_llm(DEFAULT_LLM)
        self.agent              = create_agent(self.llm, DEFAULT_AGENT)
        self.conversation       = Conversation(agent=self.agent, workspace=workspace or WORKSPACE)
        self._bindings          = {...}   # 每个实例独立的绑定

    # ── 实例方法（替换原类方法）──
    def switch_llm(self, name: str) -> bool: ...
    def switch_agent(self, name: str) -> bool: ...
    def status(self) -> str: ...
    def reset_binding(self, agent_name: str = None) -> bool: ...

    # ── 类方法兼容层（CLI 向后兼容）──
    _default_instance: InitAi | None = None

    @classmethod
    def _get_default(cls) -> InitAi:
        if cls._default_instance is None:
            cls._default_instance = cls()
        return cls._default_instance

    @classmethod
    def switch_llm(cls, name: str) -> bool:
        return cls._get_default().switch_llm(name)

    # ... 其余类方法类似委托

# 兼容性保证:
#   现有 CLI 代码 (main.py, command.py) 调用 InitAi.switch_llm("ds-pro")
#   → 自动委托给 _default_instance.switch_llm("ds-pro") → 行为不变
#
#   Web 代码:
#   ctx = InitAi(workspace=WORKSPACE)  → 每个 session 独立的实例
```

**改造影响范围**：
- `initai.py`：添加 `__init__` 实例方法，类方法改为委托（约 +50 行）
- `main.py`：**不需要改动**
- `command.py`：**不需要改动**
- `test.py`：**不需要改动**

---

## 10. 测试策略

### 10.1 测试原则

**铁律：每实现一个功能模块 → 立即交付对应的测试文件。不允许先写所有功能再补测试。**

实现顺序与测试顺序严格对应：
```
Step 1: 写代码 → Step 2: 写测试 → Step 3: 测试通过 → Step 4: 进入下一个功能
```

### 10.2 测试分层

```
┌──────────────────────────────────────────────┐
│              E2E 测试 (可选, Playwright)       │  浏览器自动化，验证完整用户流程
├──────────────────────────────────────────────┤
│              集成测试 (pytest-flask)           │  测试 Route → Service → DB 完整链路
├──────────────────────────────────────────────┤
│               单元测试 (pytest)                │  测试单个函数/类/模块
└──────────────────────────────────────────────┘
```

### 10.3 测试文件与功能对应表

| 实现顺序 | 功能模块 | 代码文件 | 对应测试文件 | 测试类型 |
|----------|---------|---------|-------------|---------|
| 0 | 基础设施 | initai.py 改造 | `test_initai.py` | 单元 |
| 1 | DB 模型 | models/*.py | `test_models/test_session_model.py` | 单元 |
| 1 | DB 模型 | models/*.py | `test_models/test_message_model.py` | 单元 |
| 1 | DB 模型 | models/*.py | `test_models/test_agent_config_model.py` | 单元 |
| 1 | DB 模型 | models/*.py | `test_models/test_setting_model.py` | 单元 |
| 2 | SessionManager | core_adapter/session_manager.py | `test_session_manager.py` | 单元 |
| 3 | StreamHandler | core_adapter/stream_handler.py | `test_stream_handler.py` | 单元 |
| 4 | ToolFormatter | core_adapter/tool_formatter.py | `test_tool_formatter.py` | 单元 |
| 5 | Flask 工厂 | app.py, config.py | 通过后续 routes 测试覆盖 | - |
| 6 | 会话 CRUD API | routes/session_routes.py, services/session_service.py | `test_routes/test_session_routes.py` | 集成 |
| 7 | 聊天发送 API (非流式) | routes/chat_routes.py, services/chat_service.py | `test_routes/test_chat_routes.py` | 集成 |
| 8 | WebSocket 流式 | sockets/chat_socket.py, services/stream_service.py | `test_sockets/test_chat_socket.py` | 集成 |
| 9 | Agent 配置 API | routes/agent_routes.py, services/agent_service.py | `test_routes/test_agent_routes.py` | 集成 |
| 10 | 工具管理 API | routes/tool_routes.py | `test_routes/test_tool_routes.py` | 集成 |
| 11 | 文件浏览 API | routes/file_routes.py, services/file_service.py | `test_routes/test_file_routes.py` | 集成 |
| 12 | 搜索 API | routes/search_routes.py, services/search_service.py | `test_routes/test_search_routes.py` | 集成 |
| 13 | 导出 API | routes/export_routes.py, services/export_service.py | `test_routes/test_export_routes.py` | 集成 |
| 14 | 统计 API | routes/stats_routes.py, services/stats_service.py | `test_routes/test_stats_routes.py` | 集成 |
| 15 | 设置 API | routes/settings_routes.py, services/settings_service.py | `test_routes/test_settings_routes.py` | 集成 |
| 16 | 重新生成 | chat_service.py (regenerate) | `test_services/test_chat_service.py` | 单元 |
| 17 | 停止生成 | stream_service.py (stop) | `test_services/test_chat_service.py` | 单元 |
| 18 | 编辑重发 | chat_service.py (edit_resend) | `test_services/test_chat_service.py` | 单元 |
| 19 | Fork 分叉 | chat_service.py (fork) | `test_services/test_chat_service.py` | 单元 |
| 20 | 前端页面 | templates/*.html, static/js/*.js | 手动验证 + 可选 E2E | E2E(可选) |

### 10.4 测试覆盖要求

| 层级 | 最低覆盖率 | 说明 |
|------|-----------|------|
| 模型层 | 95%+ | ORM 模型方法、关系、约束 |
| 服务层 | 90%+ | 核心业务逻辑：消息发送、会话管理、配置变更 |
| 路由层 | 85%+ | HTTP 状态码、请求验证、响应格式 |
| WebSocket | 80%+ | 事件收发、流式传输完整性 |
| 前端 | 手动验证 | 人工检查 UI 交互（可选 E2E 自动化） |

### 10.5 conftest.py Fixtures 设计

```
pytest fixtures 层级结构:

conftest.py:
  └── app                  ← Flask 应用实例（测试模式, 内存 SQLite）
      ├── client            ← Flask 测试客户端 (app.test_client())
      ├── db                ← 初始化数据库表，每个测试后 rollback
      ├── socketio_client   ← Socket.IO 测试客户端
      └── sample_session    ← 预创建的测试 Session + Messages

  需求可选 fixtures:
      ├── mock_llm          ← Mock LLM 对象（不调用真实 API）
      ├── mock_agent        ← Mock Agent 对象
      └── sample_file_tree  ← 临时工作区文件结构
```

---

## 11. 实施路径（分阶段）

### Phase 0：基础设施（1-2天）

**目标**：跑通 Flask 骨架 + DB 初始化 + 渲染空白聊天页面

改动清单：
- `scripts/initai.py` — 改造为支持实例化
- `scecode_web/app.py` — Flask 工厂函数
- `scecode_web/config.py` — 配置类
- `scecode_web/models/__init__.py` — SQLAlchemy 初始化
- `scecode_web/models/session.py` — SessionModel
- `scecode_web/models/message.py` — MessageModel
- `scecode_web/templates/base.html` — 基础布局
- `scecode_web/templates/index.html` — 空白三栏布局
- `scecode_web/static/css/main.css` — CSS 变量 + 基础样式
- `tests/conftest.py` — pytest fixtures
- `tests/test_presets.py` — 验证现有代码不变
- `tests/test_initai.py` — 验证改造后兼容性
- `tests/test_models/test_session_model.py`
- `tests/test_models/test_message_model.py`

**验收标准**：`python -m scecode_web.app` 启动后浏览器访问 `http://127.0.0.1:5000` 看到三栏空白布局。

### Phase 1：多会话 + 基础聊天（2-3天）

**目标**：创建/切换会话 + 发送消息 + AI 回复（阻塞模式 + 流式模式）

改动清单：
- `scecode_web/core_adapter/session_manager.py`
- `scecode_web/core_adapter/stream_handler.py`
- `scecode_web/core_adapter/tool_formatter.py`
- `scecode_web/services/session_service.py`
- `scecode_web/services/chat_service.py`
- `scecode_web/services/stream_service.py`
- `scecode_web/routes/session_routes.py`
- `scecode_web/routes/chat_routes.py`
- `scecode_web/sockets/chat_socket.py`
- `scecode_web/templates/components/sidebar_left.html`（会话列表）
- `scecode_web/templates/components/chat_bubble.html`
- `scecode_web/templates/components/tool_card.html`
- `scecode_web/static/js/chat.js`
- `scecode_web/static/js/stream.js`
- `scecode_web/static/js/session.js`
- `scecode_web/static/js/bubble.js`
- `scecode_web/static/js/tool_card.js`
- `scecode_web/static/css/chat.css`
- `scecode_web/static/css/tools.css`
- `tests/test_session_manager.py`
- `tests/test_stream_handler.py`
- `tests/test_tool_formatter.py`
- `tests/test_routes/test_session_routes.py`
- `tests/test_routes/test_chat_routes.py`
- `tests/test_sockets/test_chat_socket.py`

**验收标准**：
- 创建/切换/删除会话，刷新页面后会话列表不变（SQL 持久化）
- 发送消息后 AI 回复以流式逐字显示
- AI 调用工具时渲染工具卡片（运行中→完成/失败）

### Phase 2：Agent 配置 + 右侧栏（1-2天）

**目标**：左侧栏的 Agent 切换 + 右侧栏配置面板

改动清单：
- `scecode_web/models/agent_config.py`
- `scecode_web/services/agent_service.py`
- `scecode_web/routes/agent_routes.py`
- `scecode_web/routes/tool_routes.py`
- `scecode_web/templates/components/sidebar_right.html`
- `scecode_web/templates/components/sidebar_left.html`（Agent + 工具列表）
- `scecode_web/static/js/sidebar.js`
- `scecode_web/static/js/settings.js`
- `scecode_web/static/css/sidebar.css`
- `tests/test_models/test_agent_config_model.py`
- `tests/test_routes/test_agent_routes.py`
- `tests/test_routes/test_tool_routes.py`

**验收标准**：
- 左侧栏切换 Agent → 自动切换模型（Agent-Model 绑定生效）
- 右侧栏调整 temperature/max_tokens 后 AI 行为改变
- 右侧栏关闭某个 Tool 后 Agent 不再使用该 Tool

### Phase 3：增强功能（2-3天）

**目标**：搜索、导出、文件浏览、用量统计、设置管理

改动清单：
- `scecode_web/services/file_service.py`
- `scecode_web/services/search_service.py`
- `scecode_web/services/export_service.py`
- `scecode_web/services/stats_service.py`
- `scecode_web/services/settings_service.py`
- `scecode_web/routes/file_routes.py`
- `scecode_web/routes/search_routes.py`
- `scecode_web/routes/export_routes.py`
- `scecode_web/routes/stats_routes.py`
- `scecode_web/routes/settings_routes.py`
- `scecode_web/templates/components/file_tree.html`
- `scecode_web/templates/pages/settings.html`
- `scecode_web/templates/pages/tasks.html`
- `scecode_web/static/js/file_browser.js`
- `scecode_web/static/js/search.js`
- `scecode_web/static/js/theme.js`
- `scecode_web/static/js/toast.js`
- `scecode_web/static/js/shortcuts.js`
- `scecode_web/static/css/markdown.css`
- `scecode_web/static/css/mobile.css`
- 对应 tests/

**验收标准**：
- 搜索 "Flask" 返回包含该关键词的消息列表
- 导出会话为 Markdown 文件下载
- 左侧文件树可浏览 workspace 目录
- 暗色/亮色主题切换

### Phase 4：高级交互 + 打磨（1-2天）

**目标**：重新生成、分叉、编辑重发、推理展示、键盘快捷键、响应式

改动清单：
- `scecode_web/static/js/app.js`（事件总线）
- `scecode_web/static/js/utils.js`
- 对已有 services/routes 添加新方法（regenerate, fork, edit_resend）
- `tests/test_services/test_chat_service.py`（补充）
- `tests/test_services/test_export_service.py`
- `tests/test_services/test_session_service.py`

**验收标准**：
- 重新生成：点击 AI 消息的 ⟳ 按钮，原位替换为新的 AI 回复
- Fork：从中间消息分叉出新会话，原会话不受影响
- 移动端浏览器访问，侧栏自动折叠
- Ctrl+K 弹出命令面板

---

## 12. 技术选型

| 层面 | 技术 | 版本 | 选型理由 |
|------|------|------|---------|
| Web 框架 | Flask | 3.x | 用户指定，轻量灵活 |
| 实时通信 | Flask-SocketIO | 5.x | 支持 WebSocket 长连接，自动降级 HTTP 长轮询 |
| ORM | SQLAlchemy | 2.x | Python ORM 标准，Flask-SQLAlchemy 集成方便 |
| 数据库 | SQLite | 3.x | 零配置，适合单机部署；数据量大后可迁移 PostgreSQL |
| 前端渲染 | Jinja2 + Vanilla JS | - | 避免引入 React/Vue 等重型框架，降低学习成本 |
| Markdown | marked.js | 12.x | 轻量、快速、兼容 GitHub Flavored Markdown |
| 代码高亮 | highlight.js | 11.x | 支持 190+ 语言，主题丰富 |
| 前端 CSS | 手写 CSS + CSS Variables | - | 不使用 Tailwind/Bootstrap（避免额外依赖），用 CSS 变量实现主题切换 |
| 图标 | 纯文本 Emoji | - | 零依赖，兼容性好 |
| 测试 | pytest + pytest-flask | 8.x + 1.x | Python 测试标准 |
| 流式 | threading + queue.Queue | - | 线程安全的生产者-消费者模式 |
| WebSocket 测试 | socketio-client | 0.x | 与 Flask-SocketIO 配套 |

### 备选技术对比

| 决策 | 方案 A（选择） | 方案 B | 理由 |
|------|-------------|--------|------|
| 前端框架 | Vanilla JS | React / Vue | SceCode 是 Python 项目，引入前端构建链（webpack/vite）会大幅增加复杂度；Vanilla JS 足够满足聊天应用需求 |
| 流式传输 | WebSocket | SSE | WebSocket 双向通信可以支持"停止生成"；SSE 只能服务器→客户端单向 |
| 数据库迁移 | 无需（SQLite） | Alembic + PostgreSQL | SQLite 足够个人使用；若未来迁移，SQLAlchemy 的抽象层使迁移成本低 |
| 状态管理 | 事件总线 (EventEmitter) | Redux / Zustand | Vanilla JS 场景下全局事件总线轻量且够用 |

---

## 13. 备选架构方案

### 方案 A：Flask 单体（推荐）

```
[浏览器] ←HTTP/WS→ [Flask (REST + SocketIO)] → [SceCode 核心] → [OpenHands SDK]
```

| 维度 | 评价 |
|------|------|
| 复杂度 | 低 |
| 风险等级 | **低** |
| 开发速度 | 快 |
| 扩展性 | 中等（单机足够） |
| 适合场景 | 个人使用 / 小团队 |
| 文件数 | ~60+ 文件 |

### 方案 B：前后端分离（Flask REST API + React/Vue SPA）

```
[React/Vue SPA] ←HTTP/WS→ [Flask API Server] → [SceCode 核心] → [OpenHands SDK]
```

| 维度 | 评价 |
|------|------|
| 复杂度 | 高 |
| 风险等级 | **中高** |
| 开发速度 | 慢（需要前端构建链 + API 联调） |
| 扩展性 | 高 |
| 适合场景 | 团队协作 / 未来商业化 |
| 新增依赖 | Node.js, npm, webpack/vite |

**不推荐理由**：用户目标是学习 Flask 写网页，前后端分离需要额外学习 React/Vue + Node 生态，偏离了"用 Flask"的初衷。

### 方案 C：FastAPI + Jinja2 + WebSocket

```
[浏览器] ←HTTP/WS→ [FastAPI] → [SceCode 核心] → [OpenHands SDK]
```

| 维度 | 评价 |
|------|------|
| 复杂度 | 中 |
| 风险等级 | **低中** |
| 开发速度 | 中 |
| 扩展性 | 高（原生 asyncio） |
| 适合场景 | 对并发有要求的场景 |

**不做首选的理由**：用户明确说了 Flask。如果未来需要高并发，FastAPI 迁移成本不高（都是 Python）。

---

## 14. 风险识别与缓解

| # | 风险 | 等级 | 影响 | 缓解措施 |
|---|------|------|------|---------|
| 1 | OpenHands SDK 的 `conv.run()` 不支持 callbacks 获取 streaming token | 高 | 无法实现流式输出，退化为阻塞模式 | Phase 1 中优先验证。若不支持，先实现"阻塞等待→一次性返回"的伪流式（先显示 loading，完成后再渲染全文） |
| 2 | `conv.run()` 在后台线程中运行时的线程安全问题 | 中 | 数据竞争或死锁 | SessionManager 加锁（threading.Lock），每个 session 独立实例天然隔离 |
| 3 | LLM API 调用失败未正确处理 | 中 | 用户看到空白或报错 | 所有 API 调用包裹 try/except，错误通过 WebSocket 推送 `generation_error` 事件，Toast 显示友好信息 |
| 4 | 多个用户同时访问导致内存暴涨 | 低 | 服务 OOM | SessionManager 实现闲置超时回收（30分钟无活动自动销毁），限制最大活跃会话数（默认 20） |
| 5 | SQLite 并发写入冲突 | 低 | 单个用户操作偶尔失败 | SQLAlchemy 配置 WAL 模式 + busy_timeout=5000ms |
| 6 | 前端 JS 兼容性 | 低 | 部分浏览器功能异常 | 使用标准 Web API（Fetch、WebSocket、CSS Variables），测试 Chrome/Firefox/Edge |
| 7 | initai.py 改造破坏现有 CLI 功能 | 低 | CLI 无法使用 | 全部类方法保留为兼容层，CI 中保留 CLI 测试，Phase 0 优先验证 |

---

## 15. 设计回顾自检

- [x] 没有改动任何 .py / .json 文件
- [x] 有 ASCII 架构图（系统全景 + 模块依赖 + 页面布局 + 数据流）
- [x] 有至少 2 个备选方案（方案 A/B/C + 各技术选型的备选对比）
- [x] 每个方案有风险等级
- [x] 最终产出是 docs/arch/ 下的 .md 文档
- [x] 包含文件改动清单（分 Phase 列出）
- [x] 包含测试策略（功能→测试一一对应）
- [x] 补充了用户未明确提及的功能需求（R7~R30，共24项补充）
- [x] 接口设计包含类型注解
- [x] 代码实现指南：每实现一个功能 → 写对应测试 → 测试通过 → 进入下一个功能
