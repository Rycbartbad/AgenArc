# AgenArc Agent 开发完全指南

## 目录

1. [示例 Agents](#示例-agents)
2. [什么是 .agrc Agent](#1-什么是-agrc-agent)
3. [创建你的第一个 Agent](#2-创建你的第一个-agent)
4. [目录结构详解](#3-目录结构详解)
5. [manifest.json 完全指南](#4-manifestjson-完全指南)
6. [flow.json 完全指南](#5-flowjson-完全指南)
7. [节点类型详解](#6-节点类型详解)
8. [模板语法](#7-模板语法)
9. [VFS 虚拟文件系统](#8-vfs-虚拟文件系统)
10. [运行和调试](#9-运行和调试)
11. [完整示例](#10-完整示例)

---

## 示例 Agents

本目录包含以下示例 Agent，按照复杂度递增排列：

| Agent | 说明 | 关键特性 |
|-------|------|----------|
| **hello_agent** | 最简单的 Hello World | Trigger + Log |
| **chat_agent** | 简单对话 | Trigger + LLM_Task + Log |
| **my_first_agent** | 多轮对话 | Trigger + Prompt_Builder + LLM_Task + Prompt_Builder + Log |
| **router_agent** | 带路由 | Trigger + LLM_Task + Router + Log |
| **full_agent** | 完整功能 | Trigger + LLM_Task + Router + Log + manifest |

### 运行示例

```bash
# Hello Agent（无需 LLM）
PYTHONIOENCODING=utf-8 python -m agenarc.cli run examples/hello_agent.agrc --input '{}'

# Chat Agent（需 LLM）
PYTHONIOENCODING=utf-8 python -m agenarc.cli run examples/chat_agent.agrc --input '{"payload":"Hello!"}'

# 多轮对话 Agent（需 LLM）
PYTHONIOENCODING=utf-8 python -m agenarc.cli run examples/my_first_agent.agrc --input '{"payload":"Hello!"}'
PYTHONIOENCODING=utf-8 python -m agenarc.cli shell examples/my_first_agent.agrc

# Router Agent
PYTHONIOENCODING=utf-8 python -m agenarc.cli run examples/router_agent.agrc --input '{"payload":"Say hello"}'

# Full Agent
PYTHONIOENCODING=utf-8 python -m agenarc.cli run examples/full_agent.agrc --input '{"payload":"What is AI?"}'
```

---

## 1. 什么是 .agrc Agent

`.agrc` 是 AgenArc 的 Agent 资产包格式。每个 Agent 是一个文件夹，包含执行所需的所有组件：

- **prompts/** - 提示词模板
- **scripts/** - 自定义脚本
- **flow.json** - 工作流定义
- **manifest.json** - 配置信息

---

## 2. 创建你的第一个 Agent

本节创建一个支持多轮对话的 Agent，使用 Prompt_Builder 管理对话历史。

### 步骤 1：创建目录结构

```
my_agent.agrc/
├── manifest.json
├── flow.json
└── prompts/
    └── system.pt
```

### 步骤 2：编写 manifest.json

```json
{
  "name": "my_agent",
  "version": "1.0.0",
  "entry": "flow.json"
}
```

### 步骤 3：编写 flow.json

```json
{
  "version": "1.0.0",
  "entryPoint": "trigger_1",
  "nodes": [
    {"id": "trigger_1", "type": "Trigger", "label": "启动"},
    {
      "id": "pb_user",
      "type": "Prompt_Builder",
      "label": "用户输入",
      "config": {"history": "chat_history"}
    },
    {
      "id": "llm_1",
      "type": "LLM_Task",
      "label": "LLM 调用",
      "config": {
        "model": "deepseek-chat",
        "temperature": 0.7,
        "max_tokens": 150,
        "system_prompt": "agrc://prompts/system.pt"
      }
    },
    {
      "id": "pb_assistant",
      "type": "Prompt_Builder",
      "label": "助手响应",
      "config": {"history": "chat_history"}
    },
    {"id": "log_1", "type": "Log", "label": "日志"}
  ],
  "edges": [
    {"source": "trigger_1", "sourcePort": "payload", "target": "pb_user", "targetPort": "user"},
    {"source": "pb_user", "sourcePort": "messages", "target": "llm_1", "targetPort": "messages"},
    {"source": "llm_1", "sourcePort": "response", "target": "pb_assistant", "targetPort": "assistant"},
    {"source": "llm_1", "sourcePort": "response", "target": "log_1", "targetPort": "message"},
    {"source": "pb_assistant", "target": "trigger_1"}
  ]
}
```

**关键设计**：
- `pb_user` 和 `pb_assistant` 配置相同的 `history` 值，共享对话历史
- `pb_assistant → trigger` 的边标识多轮会话
- `llm_1 → log_1` 边将响应输出到日志

### 步骤 4：编写 prompts/system.pt

```jinja2
你是我的人工智能助手，协助我完成各种任务。
```

### 步骤 5：运行 Agent

```bash
# 单次执行
PYTHONIOENCODING=utf-8 python -m agenarc.cli run my_agent.agrc --input '{"payload":"Hello"}'

# 交互式对话（多轮）
PYTHONIOENCODING=utf-8 python -m agenarc.cli shell my_agent.agrc
```

---

## 3. 目录结构详解

### 最小结构（必须）

```
agent_name.agrc/
├── manifest.json    # 必须：Agent 配置
├── flow.json        # 必须：工作流定义
└── prompts/        # 必须：至少一个 .pt 文件
    └── system.pt   # 必须：系统提示词
```

### 完整结构

```
agent_name.agrc/
├── manifest.json      # Agent 元数据
├── flow.json         # 工作流定义
├── prompts/          # Prompt 模板目录
│   ├── system.pt     # 系统提示词（必须）
│   └── user.pt       # 用户提示词（可选）
├── scripts/          # 自定义脚本目录（可选）
│   ├── tool.py       # 工具脚本
│   └── processor.py  # 处理脚本
├── plugins/          # 嵌入式 Python 插件（可选，自动发现）
│   └── my_plugin/
│       ├── agenarc.json
│       └── plugin.py
└── assets/          # 静态资源 + C++/External 插件（可选）
    ├── config.yaml
    └── plugins/      # C++/External 插件（自动安装到全局）
        └── my_plugin/
            ├── agenarc.json
            └── libmy_plugin.so
```

---

## 4. manifest.json 完全指南

### 完整字段说明

```json
{
  "name": "my_agent",
  "version": "1.0.0",
  "entry": "flow.json",
  "description": "我的第一个 Agent",
  "permissions": {
    "allow_script_read": true,
    "allow_script_write": true,
    "allow_prompt_read": true,
    "allow_prompt_write": false,
    "allowed_modules": ["os", "json", "re"],
    "autonomy_level": "level_1",
    "gas_budget": 1000,
    "max_memory_mb": 128
  },
  "immutable_anchors": [
    {"node_id": "trigger_1", "reason": "Entry point cannot be modified"}
  ],
  "hot_reload": true
}
```

### 字段详解

| 字段 | 必填 | 类型 | 说明 |
|------|------|------|------|
| `name` | 是 | string | Agent 名称，只能包含字母、数字、下划线 |
| `version` | 是 | string | 版本号，格式：X.Y.Z |
| `entry` | 是 | string | 入口文件，通常是 "flow.json" |
| `description` | 否 | string | Agent 描述 |
| `permissions` | 否 | object | 权限配置 |
| `immutable_anchors` | 否 | array | 不可变锚点列表（内核锁定） |
| `hot_reload` | 否 | boolean | 是否启用热重载，默认 false |

### permissions 权限配置

| 字段 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `allow_script_read` | boolean | true | 是否允许读取 scripts/ 目录 |
| `allow_script_write` | boolean | false | 是否允许写入 scripts/ 目录 |
| `allow_prompt_read` | boolean | true | 是否允许读取 prompts/ 目录 |
| `allow_prompt_write` | boolean | false | 是否允许写入 prompts/ 目录 |
| `allow_flow_modification` | boolean | false | 是否允许修改 flow.json（level_2+） |
| `allow_manifest_modification` | boolean | false | 是否允许修改 manifest.json（level_3） |
| `autonomy_level` | string | "level_1" | 信任式自主等级 |
| `gas_budget` | integer | 1000 | 表达式求值的 Gas 上限 |
| `max_memory_mb` | integer | 128 | SafeContext 内存限制（MB） |

### autonomy_level 信任式自主等级

| 等级 | 说明 |
|------|------|
| `level_0` | Zero Knowledge - AI 感知不到 agrc:// 协议 |
| `level_1` | Supervised - 仅表达式求值 |
| `level_2` | Autonomous - 可修改 flow.json |
| `level_3` | Self-Evolving - 最高权力 |

**注意**：Script_Node 默认使用 `developer` 模式（完全信任），不受 autonomy_level 限制。可通过 `script_trust_level` 配置覆盖。

### immutable_anchors 不可变锚点

这是一个对象数组，指定哪些节点由内核强制锁定，即使 level_3 也不能修改：

```json
{
  "immutable_anchors": [
    {"node_id": "trigger_1", "reason": "Entry point cannot be modified"},
    {"node_id": "audit_1", "reason": "Security audit node"}
  ]
}
```

---

## 5. flow.json 完全指南

### 基本结构

```json
{
  "version": "1.0.0",
  "entryPoint": "trigger_1",
  "nodes": [...],
  "edges": [...]
}
```

### version 版本号

固定值：`"1.0.0"`

### entryPoint 入口点

必须是某个节点（Node）的 `id`，且该节点类型必须是 `Trigger`。

### nodes 节点列表

节点定义数组，每个节点是一个对象。详见[第6节](#6-节点类型详解)。

### edges 边列表

边定义了节点之间的连接关系：

```json
{
  "source": "node_a",
  "sourcePort": "output_name",
  "target": "node_b",
  "targetPort": "input_name"
}
```

| 字段 | 必填 | 说明 |
|------|------|------|
| `source` | 是 | 源节点 ID |
| `sourcePort` | 否 | 源节点输出端口名，不填则传递所有输出 |
| `target` | 是 | 目标节点 ID |
| `targetPort` | 否 | 目标节点输入端口名，不填则传递到第一个输入端口 |

#### 边的简单表示

如果不需要指定端口，可以简写：

```json
{"source": "trigger_1", "target": "llm_1"}
```

这等同于：

```json
{"source": "trigger_1", "sourcePort": "payload", "target": "llm_1", "targetPort": "message"}
```

#### 连接到 Trigger 的边

当边指向 trigger 时，只需 source 和 target：

```json
{"source": "pb_assistant", "target": "trigger_1"}
```

这类边只起控制流作用（决定是否维护会话），不传递数据。

---

## 6. 节点类型详解

### 6.1 Trigger（触发器）

**作用**：工作流的入口点，每个流程只能有一个 Trigger。

**示例**：

```json
{
  "id": "trigger_1",
  "type": "Trigger",
  "label": "开始",
  "description": "工作流入口"
}
```

**输出端口**：

| 端口名 | 类型 | 说明 |
|--------|------|------|
| `payload` | any | 初始载荷，包含用户输入 |

---

### 6.2 LLM_Task（LLM 任务）

**作用**：调用语言模型生成响应。

**示例**：

```json
{
  "id": "llm_1",
  "type": "LLM_Task",
  "label": "对话",
  "config": {
    "model": "deepseek-chat",
    "temperature": 0.7,
    "system_prompt": "你是智能助手"
  }
}
```

**输入端口**：

| 端口名 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `messages` | array | [] | 对话消息列表 |

**输出端口**：

| 端口名 | 类型 | 说明 |
|--------|------|------|
| `response` | string | LLM 生成的响应 |
| `usage` | object | token 使用统计 |

**config 配置项**：

| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `provider` | string | 必需 | 提供商名称（如 deepseek、openrouter），与 config.yaml 中的 providers 一致 |
| `model` | string | provider.default_model | 模型名称，会覆盖 provider 的 default_model |
| `temperature` | number | 0.7 | 温度参数，控制随机性（0-1） |
| `system_prompt` | string | - | 系统提示词（与 messages 列表区分） |
| `max_tokens` | integer | - | 最大生成 token 数 |

---

### 6.3 Prompt_Builder（消息构建器）

**作用**：管理和追加对话消息历史，支持 user/assistant 交替检查。

**示例**：

```json
{
  "id": "pb_1",
  "type": "Prompt_Builder",
  "config": {
    "history": "chat_history",
    "max_history": 100
  }
}
```

**配置选项**：

| 选项 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `history` | string | node ID | 历史记录键名，多个 PB 节点可通过相同键名共享历史 |
| `max_history` | int | 100 | 最大消息数量，超出时保留最新的消息 |

**输入端口**：

| 端口名 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `user` | string | null | 用户消息（二选一） |
| `assistant` | string | null | 助手消息（二选一） |

**输出端口**：

| 端口名 | 类型 | 说明 |
|--------|------|------|
| `messages` | array | 完整的对话消息列表 |

**行为**：
- 追加 user 或 assistant 消息到 `nodes.{history}.messages`
- 安全检查：确保 user 和 assistant 交替出现
- 超出 `max_history` 限制时，保留最新的消息
- 不同 PB 节点可通过相同的 `history` 值共享对话历史

**多轮对话示例**：

```
trigger.payload ──→ pb_user ──→ llm ──→ pb_assistant ──→ trigger
```

其中 `pb_user` 和 `pb_assistant` 配置相同的 `history` 键值以共享对话历史。

---

### 6.4 Router（路由）

**作用**：根据条件将执行路由到不同的分支（汇编风格跳转）。

**特性**：
- Router **不声明固定输出端口**，输出端口由边（edge）的 `sourcePort` 决定
- `condition.output` 是标签，与 `edge.sourcePort` 匹配
- 可以是任意字符串：`"A"`、`"exit"`、节点 ID 等
- **多输出**：所有满足条件的分支都会输出，并行执行

**示例**：

```json
{
  "id": "router_1",
  "type": "Router",
  "config": {
    "conditions": [
      {
        "ref": "input",
        "operator": "contains",
        "value": "quit",
        "output": "exit"
      }
    ],
    "default": "continue"
  }
}
```

对应的边：

```json
{"source": "router_1", "sourcePort": "exit", "target": "log_1"}
{"source": "router_1", "sourcePort": "continue", "target": "process_1"}
```

**输入端口**：

| 端口名 | 类型 | 说明 |
|--------|------|------|
| `input` | any | 要判断的输入值 |

**config 配置项**：

| 配置项 | 类型 | 说明 |
|--------|------|------|
| `conditions` | array | 条件数组，按顺序匹配 |
| `default` | string | 默认输出标签 |

**conditions 条件数组**：

```json
{
  "ref": "input",
  "operator": "contains",
  "value": "quit",
  "output": "exit"
}
```

| 字段 | 类型 | 说明 |
|------|------|------|
| `ref` | string | 引用的变量名 |
| `operator` | string | 操作符 |
| `value` | any | 比较的值 |
| `output` | string | 匹配时输出的标签（与 edge.sourcePort 匹配） |
| `and` | array | 与条件数组 |
| `or` | array | 或条件数组 |
| `not` | object | 否定条件 |

**操作符 (operator)**：

| 操作符 | 说明 | 示例 |
|--------|------|------|
| `eq` | 等于 | `{"operator": "eq", "value": "yes"}` |
| `ne` | 不等于 | `{"operator": "ne", "value": "no"}` |
| `gt` | 大于 | `{"operator": "gt", "value": 5}` |
| `gte` | 大于等于 | `{"operator": "gte", "value": 5}` |
| `lt` | 小于 | `{"operator": "lt", "value": 10}` |
| `lte` | 小于等于 | `{"operator": "lte", "value": 10}` |
| `contains` | 包含 | `{"operator": "contains", "value": "help"}` |
| `notContains` | 不包含 | `{"operator": "notContains", "value": "bad"}` |
| `startsWith` | 开头是 | `{"operator": "startsWith", "value": "!"}` |
| `endsWith` | 结尾是 | `{"operator": "endsWith", "value": "?"}` |
| `in` | 在数组中 | `{"operator": "in", "value": ["a", "b"]}` |
| `notIn` | 不在数组中 | `{"operator": "notIn", "value": ["x", "y"]}` |
| `exists` | 存在 | `{"operator": "exists"}` |
| `notExists` | 不存在 | `{"operator": "notExists"}` |

**ref 引用路径**：

| 路径格式 | 说明 | 示例 |
|----------|------|------|
| `input` | 输入值 | 直接引用 input 端口 |
| `context.xxx` | 全局上下文 | `context.user_input` |
| `nodes.xxx.outputs.yyy` | 节点输出 | `nodes.llm_1.outputs.response` |

**复合条件示例**：

```json
{
  "and": [
    {"ref": "input", "operator": "contains", "value": "help"},
    {"ref": "context.level", "operator": "gte", "value": 5}
  ]
}
```

```json
{
  "or": [
    {"ref": "input", "operator": "contains", "value": "quit"},
    {"ref": "input", "operator": "contains", "value": "exit"}
  ]
}
```

**Router 循环模式（汇编风格跳转）**

Router 的 `condition.output` 可以是节点 ID，形成环状结构：

```json
{
  "id": "router_1",
  "type": "Router",
  "config": {
    "conditions": [
      {
        "ref": "context._count",
        "operator": "lt",
        "value": 3,
        "output": "counter_inc"
      }
    ],
    "default": "exit"
  }
}
```

对应的边配置：

```json
{
  "edges": [
    {"source": "router_1", "sourcePort": "counter_inc", "target": "counter_inc"},
    {"source": "counter_inc", "target": "router_1"},
    {"source": "router_1", "sourcePort": "exit", "target": "log_1"}
  ]
}
```

**工作原理**：
1. `condition.output` 是标签，与 `edge.sourcePort` 匹配
2. Router 执行后找到 `sourcePort` 匹配的边，执行其 `target` 节点
3. 如果 target 是已执行过的节点，则形成循环（重新执行）
4. 通过 Script_Node 自行实现循环退出条件控制

### Router 多输出模式

当多个条件同时满足时，Router 会**同时输出到所有匹配的分支**：

```json
{
  "id": "router_1",
  "type": "Router",
  "config": {
    "conditions": [
      {"ref": "input", "operator": "gte", "value": 10, "output": "high"},
      {"ref": "input", "operator": "gte", "value": 5, "output": "medium"},
      {"ref": "input", "operator": "gte", "value": 0, "output": "low"}
    ],
    "default": "invalid"
  }
}
```

对应的边配置：

```json
{
  "edges": [
    {"source": "router_1", "sourcePort": "high", "target": "process_high"},
    {"source": "router_1", "sourcePort": "medium", "target": "process_medium"},
    {"source": "router_1", "sourcePort": "low", "target": "process_low"},
    {"source": "router_1", "sourcePort": "invalid", "target": "handle_invalid"}
  ]
}
```

**执行行为**：

- 输入值 `15` → 同时触发 `high`、`medium`、`low` 三个分支（并行执行）
- Router 将输入值存储到 `nodes.router_1.{output_label}`，供各分支读取
- 使用 Join 节点合并多分支结果

**示例流程**：
```
trigger → counter_init → router_1
                          ↓ (counter_inc)
                      counter_inc
                          ↓
                       router_1 (再次执行)
                          ↓ (exit)
                         log_1
```

---

### 6.5 Memory_I/O（记忆 I/O）

**作用**：读写持久化存储。

**示例**：

```json
{
  "id": "memory_1",
  "type": "Memory_I/O",
  "label": "记忆",
  "inputs": [
    {"name": "key", "type": "string"},
    {"name": "value", "type": "any"}
  ],
  "outputs": [
    {"name": "value", "type": "any"},
    {"name": "success", "type": "boolean"}
  ]
}
```

**输入端口**：

| 端口名 | 类型 | 说明 |
|--------|------|------|
| `key` | string | 存储键名 |
| `value` | any | 要存储的值（写模式） |

**输出端口**：

| 端口名 | 类型 | 说明 |
|--------|------|------|
| `value` | any | 读取的值 |
| `success` | boolean | 操作是否成功 |

---

### 6.6 Script_Node（脚本节点）

**作用**：执行自定义 Python 脚本。

**示例**：

```json
{
  "id": "script_1",
  "type": "Script_Node",
  "label": "处理",
  "inputs": [
    {"name": "script", "type": "string", "default": "result = input"},
    {"name": "timeout", "type": "integer", "default": 30}
  ],
  "outputs": [
    {"name": "result", "type": "any"},
    {"name": "success", "type": "boolean"},
    {"name": "error", "type": "string"}
  ]
}
```

**输入端口**：

| 端口名 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `script` | string | - | 要执行的 Python 代码 |
| `timeout` | integer | 30 | 超时时间（秒） |

**输出端口**：

| 端口名 | 类型 | 说明 |
|--------|------|------|
| `result` | any | 脚本执行结果 |
| `success` | boolean | 是否成功 |
| `error` | string | 错误信息 |

**脚本示例**：

```python
# 获取输入
text = context.get('input', '')

# 处理
words = text.split()
word_count = len(words)

# 返回结果
result = {
    'word_count': word_count,
    'upper': text.upper(),
    'lower': text.lower()
}
```

**可用的上下文变量**：

| 变量 | 说明 |
|------|------|
| `context` | 执行上下文对象 |
| `input` | 输入端口的值 |
| `loop` | 循环信息（iteration, current_item, accumulator） |

**信任级别**：Script_Node 默认使用 `developer` 模式（完全信任），可按需通过 `config.script_trust_level` 覆盖。

| trust_level | 说明 |
|-------------|------|
| `locked` | 仅支持表达式，拒绝语句 |
| `trusted` | 支持安全语句执行 |
| `developer` | **默认**，完全信任所有 Python 代码 |

---

### 6.7 Join（并行同步）

**作用**：同步多个并行分支的输入并合并。

**特性**：
- Join **不声明固定输入端口**，基于 `_incoming_edges` 动态读取
- 根据边的 source 信息从 context 中读取数据：`nodes.{source}.{sourcePort}`
- 使用配置指定合并策略

**使用场景**：当多个节点并行执行后需要汇合时使用。

**示例**：

```json
{
  "id": "join_1",
  "type": "Join",
  "config": {
    "strategy": "merge"
  }
}
```

对应的边配置：

```json
{
  "edges": [
    {"source": "branch_A", "sourcePort": "output", "target": "join_1"},
    {"source": "branch_B", "sourcePort": "output", "target": "join_1"}
  ]
}
```

**输出端口**：

| 端口名 | 类型 | 说明 |
|--------|------|------|
| `output` | any | 合并后的结果 |

**合并策略**：

| 策略 | 行为 |
|------|------|
| `first` | 返回第一个输入的值 |
| `last` | 返回最后一个输入的值 |
| `merge` | 合并为 `{"branch_A.output": ..., "branch_B.output": ...}` |
| `concat` | 拼接所有输入为列表 |

---

### 6.8 Log（日志节点）

**作用**：输出调试信息。

**示例**：

```json
{
  "id": "log_1",
  "type": "Log",
  "label": "日志",
  "inputs": [
    {"name": "message", "type": "string", "default": ""},
    {"name": "data", "type": "any", "default": null}
  ],
  "outputs": [
    {"name": "message", "type": "string"},
    {"name": "data", "type": "any"}
  ]
}
```

**输入端口**：

| 端口名 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `message` | string | "" | 日志消息 |
| `data` | any | null | 要输出的数据 |

---

### 6.9 Context_Set（设置上下文）

**作用**：向全局上下文写入变量。

**示例**：

```json
{
  "id": "set_ctx",
  "type": "Context_Set",
  "label": "设置变量",
  "inputs": [
    {"name": "key", "type": "string"},
    {"name": "value", "type": "any"}
  ],
  "outputs": [
    {"name": "success", "type": "boolean"}
  ]
}
```

**输入端口**：

| 端口名 | 类型 | 说明 |
|--------|------|------|
| `key` | string | 变量名 |
| `value` | any | 变量值 |

---

### 6.10 Context_Get（获取上下文）

**作用**：从全局上下文读取变量。

**示例**：

```json
{
  "id": "get_ctx",
  "type": "Context_Get",
  "label": "获取变量",
  "inputs": [
    {"name": "key", "type": "string"},
    {"name": "default", "type": "any", "default": null}
  ],
  "outputs": [
    {"name": "value", "type": "any"}
  ]
}
```

**输入端口**：

| 端口名 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `key` | string | - | 变量名 |
| `default` | any | null | 默认值（变量不存在时返回） |

---



### 6.11 Plugin（自定义插件算子）

**作用**：调用自定义插件实现的算子。

**示例**：

```json
{
  "id": "my_plugin_op",
  "type": "Plugin",
  "label": "自定义算子",
  "inputs": [
    {"name": "input", "type": "string"},
    {"name": "options", "type": "object", "default": {}}
  ],
  "outputs": [
    {"name": "result", "type": "any"},
    {"name": "success", "type": "boolean"}
  ],
  "config": {
    "plugin": "my_plugin",
    "function": "process"
  }
}
```

**config 配置项**：

| 配置项 | 类型 | 说明 |
|--------|------|------|
| `plugin` | string | 插件名称（agenarc.json 中的 name） |
| `function` | string | 算子名称 |

**详细说明**：

要使用 Plugin 节点，需要：
1. 将插件放入配置的插件目录（默认为 `~/.agenarc/plugins`）
2. 或将 Python 插件内嵌到 Agent 的 `plugins/` 目录中（随 Agent 分发）
3. 或将 C++/External 插件放到 `assets/plugins/` 目录（首次运行自动安装到全局）
4. 在 flow.json 中使用 `type: "Plugin"` 并配置 `config.plugin` 和 `config.function`

详见：[插件开发指南](plugins/README.md)

---

### 6.12 Asset_Reader（资产读取）

**作用**：读取 Bundle 内的资产文件。

**示例**：

```json
{
  "id": "reader_1",
  "type": "Asset_Reader",
  "config": {
    "path": "agrc://prompts/system.pt",
    "encoding": "utf-8"
  }
}
```

**输入端口**：

| 端口名 | 类型 | 说明 |
|--------|------|------|
| `path` | string | agrc:// 相对路径 |

**输出端口**：

| 端口名 | 类型 | 说明 |
|--------|------|------|
| `content` | string | 文件原文 |
| `metadata` | object | 文件元信息 |

**config 配置项**：

| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `path` | string | - | VFS 路径（必需） |
| `encoding` | string | utf-8 | 文件编码 |
| `required` | boolean | true | 文件不存在时是否报错 |

---

### 6.13 Asset_Writer（资产写入）

**作用**：向 Bundle 内写入/创建资产文件。

**示例**：

```json
{
  "id": "writer_1",
  "type": "Asset_Writer",
  "config": {
    "path": "agrc://scripts/tool.py",
    "atomic": true
  }
}
```

**输入端口**：

| 端口名 | 类型 | 说明 |
|--------|------|------|
| `path` | string | 目标路径 |
| `content` | string | 文件内容 |
| `operation` | string | 操作类型：create/update/delete |

**输出端口**：

| 端口名 | 类型 | 说明 |
|--------|------|------|
| `success` | boolean | 操作是否成功 |
| `path` | string | 实际写入的路径 |

**config 配置项**：

| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `atomic` | boolean | true | 启用原子写入（失败立即回滚） |
| `allow_create` | boolean | true | 允许创建新文件 |

**原子性保证**：
- 写入前先创建 `.tmp` 文件
- 写入成功后 rename
- 失败则删除 `.tmp`，原文件保持不变

---

### 6.14 Runtime_Reload（运行时重载）

**作用**：触发引擎热重载，刷新插件注册表。

**示例**：

```json
{
  "id": "reload_1",
  "type": "Runtime_Reload",
  "config": {
    "target": "both"
  }
}
```

**输出端口**：

| 端口名 | 类型 | 说明 |
|--------|------|------|
| `reloaded_scripts` | array | 重载的脚本列表 |
| `success` | boolean | 重载是否成功 |

**config 配置项**：

| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `target` | string | both | 重载目标：plugins/scripts/both |

**执行流程**：
1. **静默期**：暂停接收新任务，等待当前原子节点执行完毕
2. **Snapshot 保存**：保存当前 Global Context 完整状态
3. 扫描 `scripts/` 目录
4. 对新增/修改的 `.py` 文件执行 AST 扫描
5. 刷新 PluginManager 注册表
6. 恢复 Context（保持不丢失）
7. 返回重载结果

---

## 7. 模板语法

在 prompts/*.pt 文件和节点配置中，可以使用 `{{key}}` 模板变量。模板在**节点执行时解析**（保证实时性）。

### 7.1 模板特性

- **递归解析**：`{{a}}` → `{{b}}` → value（最大深度10）
- **点号访问**：`{{user.name}}` 支持 dict 和 object 属性访问
- **VFS 集成**：`agrc://prompts/system.pt` 先读取文件内容再解析模板

### 7.2 上下文变量

| 语法 | 说明 |
|------|------|
| `{{context}}` | 整个上下文对象 |
| `{{context.xxx}}` | 上下文中的特定字段 |
| `{{user.name}}` | 点号访问嵌套字段 |

### 7.3 节点输出变量

| 语法 | 说明 |
|------|------|
| `{{nodes.xxx.yyy}}` | 获取节点 xxx 的 yyy 输出 |

**示例**：

```jinja2
The LLM said: {{nodes.llm_1.response}}
Token usage: {{nodes.llm_1.usage.total_tokens}}
```

### 7.4 循环变量

| 语法 | 说明 |
|------|------|
| `{{loop.current_item}}` | 当前迭代项 |
| `{{loop.iteration}}` | 当前迭代数 |
| `{{loop.accumulator}}` | 累积值 |

### 7.5 环境变量

| 语法 | 说明 |
|------|------|
| `{{env.VAR_NAME}}` | 系统环境变量 |

### 7.6 条件模板

```jinja2
{% if context.is_admin %}
Welcome, admin!
{% else %}
Welcome, user!
{% endif %}
```

### 7.7 循环模板

```jinja2
{% for item in items %}
- {{ item }}
{% endfor %}
```

### 7.8 模板使用示例

**prompts/system.pt**：

```jinja2
You are {{agent_name}}, a helpful AI assistant.

User context: {{context.user_context}}

{% if context.is_premium %}
You have premium access.
{% endif %}

Current conversation:
{{context.history}}
```

**prompts/user.pt**：

```jinja2
{{user_input}}

{% if context.attachments %}
Attachments: {{context.attachments}}
{% endif %}
```

### 7.9 VFS + 模板组合

VFS 路径中的文件内容会先被读取，然后进行模板解析：

```json
{
  "config": {
    "system_prompt": "agrc://prompts/system.pt",
    "model": "{{default_model}}"
  }
}
```

这允许：
1. `agrc://prompts/system.pt` → 读取文件内容
2. `{{default_model}}` → 从 context 获取当前模型名称

---

## 8. VFS 虚拟文件系统

VFS 允许通过 `agrc://` 协议安全地访问 bundle 内部的资源，而不需要暴露实际文件系统路径。

### 8.1 VFS 路径映射

| VFS 路径 | 实际路径 |
|----------|----------|
| `agrc://prompts/` | `<bundle>/prompts/` |
| `agrc://scripts/` | `<bundle>/scripts/` |
| `agrc://assets/` | `<bundle>/assets/` |
| `agrc://flow.json` | `<bundle>/flow.json` |

### 8.2 在配置中使用 VFS

**LLM_Task 配置示例**：

```json
{
  "id": "llm_1",
  "type": "LLM_Task",
  "config": {
    "system_prompt": "agrc://prompts/system.pt"
  }
}
```

**Asset_Reader 配置示例**：

```json
{
  "id": "reader_1",
  "type": "Asset_Reader",
  "config": {
    "path": "agrc://scripts/tool.py"
  }
}
```

### 8.3 完整 VFS 路径示例

| 用途 | VFS 路径 |
|------|----------|
| 系统提示词 | `agrc://prompts/system.pt` |
| 用户提示词 | `agrc://prompts/user.pt` |
| 工具脚本 | `agrc://scripts/tool.py` |
| 配置文件 | `agrc://assets/config.yaml` |
| 流程定义 | `agrc://flow.json` |

---

## 9. 运行和调试

### 9.1 配置 API Key

配置文件位置（按优先级递减）：

1. `~/.agenarc/config.yaml`（用户全局配置）
2. `项目根目录/config.yaml`（项目级配置）

**多提供商配置**：

```yaml
providers:
  openrouter:
    api_key: your-openrouter-key
    base_url: https://openrouter.ai/api/v1
    default_model: openrouter/free

  deepseek:
    api_key: your-deepseek-key
    base_url: https://api.deepseek.com
    default_model: deepseek-chat
    temperature: 0.7
```

然后在 flow.json 中指定使用哪个 provider 和 model：

```json
{
  "id": "llm_1",
  "type": "LLM_Task",
  "config": {
    "provider": "openrouter",
    "model": "openrouter/free"
  }
}
```

- `provider`：必需，指定使用哪个提供商
- `model`：可选，不指定则使用 config.yaml 中的 default_model

**常用 API 端点**：

| 服务商 | base_url | 模型示例 |
|--------|----------|----------|
| DeepSeek | `https://api.deepseek.com` | deepseek-chat |
| OpenAI | `https://api.openai.com/v1` | gpt-4, gpt-3.5-turbo |
| OpenRouter | `https://openrouter.ai/api/v1` | openrouter/free, openrouter/deepseek(deepseek-chat) |
| Anthropic | `https://api.anthropic.com` | claude-3-5-sonnet-20240620 |
| Ollama (本地) | `http://localhost:11434/v1` | llama2, mistral |

### 9.2 运行命令

```bash
PYTHONIOENCODING=utf-8 python -m agenarc.cli run <agent-path> --input '<json>'
```

### 9.3 输入格式

`--input` 参数必须是有效的 JSON：

**简单字符串**：

```bash
--input '{"payload": "Hello"}'
```

**带上下文的输入**：

```bash
--input '{"payload": {"user_input": "Hello", "context": {"name": "Alice"}}}'
```

**多字段输入**：

```bash
--input '{"user_input": "Help me", "mode": "detailed", "language": "zh"}'
```

### 9.4 运行选项

| 选项 | 说明 |
|------|------|
| `--input <json>` | 输入数据（JSON 格式） |
| `--mode <mode>` | 执行模式：sync, async, parallel（默认 async） |
| `-v, --verbose` | 显示详细输出 |

### 9.5 交互式 Shell

交互式 Shell 允许你以 REPL 模式运行 Agent，无需每次输入完整的 JSON：

```bash
PYTHONIOENCODING=utf-8 python -m agenarc.cli shell examples/hello_agent.agrc
```

**输入格式**：

| 输入类型 | 示例 | 处理方式 |
|----------|------|----------|
| 纯文本 | `Hello` | 自动转换为 `{"input": "Hello"}` |
| JSON 对象 | `{"payload":"Hi"}` | 直接作为完整 payload |

**会话持久化**：

Shell 根据 flow.json 的结构决定会话行为：

| Trigger 连接状态 | 行为 |
|-----------------|------|
| 无边连接到 trigger | 每次执行都是全新状态 |
| 有边连接到 trigger | 维护会话状态（多轮对话） |

**说明**：边可以连接到 trigger，但 trigger 忽略边的数据，只使用外部输入。

| 命令 | 说明 |
|------|------|
| `:reset` | 重置会话，开启新对话（清空 context） |
| `:quit` / `:exit` | 退出 Shell |

**`_session_first_run` 标志**：

| 标志值 | 含义 | 用途 |
|--------|------|------|
| `{{context._session_first_run}} == true` | 会话首次执行 | 初始化、欢迎语、加载历史 |
| `{{context._session_first_run}} == false` | 会话后续执行 | 直接对话、读取 Memory_I/O |

**示例会话**：

```
==================================================
AgenArc Interactive Shell
==================================================
Agent: examples/hello_agent.agrc
Context persists during session, resets on new session
Type input and press Enter to execute
  - Plain text: treated as payload
  - JSON object: used as full payload
Commands: :quit/:exit to exit, :reset to start new session
          :info to show agent info, :logs to toggle logs
==================================================

> Hello
[AGENARC] Hello from AgenArc!

> World
[AGENARC] World from AgenArc!

> :reset
Session reset (new conversation started).

> Hello again
[AGENARC] Hello again from AgenArc!

> :quit
Goodbye!
```

### 9.6 调试技巧

1. **使用 Log 节点**：在关键节点后添加 Log 节点查看输出
2. **简化流程**：先用一个 LLM_Task 测试，再逐步添加其他节点
3. **检查输出**：使用 `-v` 查看完整的节点输出

### 9.7 Python 模块接入与会话持久化

除了 CLI 和 Shell，还可以通过 Python 模块直接调用 Engine：

```python
from agenarc.engine.executor import ExecutionEngine
from agenarc.engine.state import StateManager

# 创建 Engine
engine = ExecutionEngine()
engine.load_protocol("my_agent.agrc")

# 创建会话 StateManager（只创建一次）
session_state = StateManager(auto_checkpoint=False)
session_state.initialize("session_id", engine._graph.entryPoint)

# 多轮对话：每次执行前绑定 session StateManager
while True:
    user_input = input("> ")
    if user_input == "quit":
        break

    # 绑定 session StateManager
    engine._state = session_state

    # 执行（StateManager 不会被重新创建）
    result = engine.execute({"input": user_input})
    print(result.final_outputs)

    # session_state 中已保存所有 context，可继续累积
```

**核心原理**：每次 `execute()` 会创建新的 `StateManager`，通过手动绑定 `engine._state`，实现跨执行的 context 持久化。

**`_session_first_run` 标志**：

```python
session_state.set_global("_session_first_run", True)  # 首次执行
session_state.set_global("_session_first_run", False) # 后续执行
```

---

## 10. 完整示例

### 10.1 hello_agent.agrc - 最简单的 Agent

**目录结构**：

```
hello_agent.agrc/
├── manifest.json
└── flow.json
```

**manifest.json**：

```json
{
  "name": "hello_agent",
  "version": "1.0.0",
  "entry": "flow.json"
}
```

**flow.json**：

```json
{
  "version": "1.0.0",
  "entryPoint": "trigger_1",
  "nodes": [
    {"id": "trigger_1", "type": "Trigger", "label": "开始"},
    {
      "id": "log_1",
      "type": "Log",
      "label": "输出",
      "inputs": [
        {"name": "message", "type": "string", "default": "Hello from AgenArc!"}
      ]
    }
  ],
  "edges": [
    {"source": "trigger_1", "sourcePort": "payload", "target": "log_1", "targetPort": "message"}
  ]
}
```

**运行**（无需 LLM）：

```bash
PYTHONIOENCODING=utf-8 python -m agenarc.cli run examples/hello_agent.agrc --input '{}'
```

---

### 10.2 chat_agent.agrc - 简单对话 Agent

**目录结构**：

```
chat_agent.agrc/
├── manifest.json
├── flow.json
└── prompts/
    └── system.pt
```

**manifest.json**：

```json
{
  "name": "chat_agent",
  "version": "1.0.0",
  "entry": "flow.json"
}
```

**flow.json**：

```json
{
  "version": "1.0.0",
  "entryPoint": "trigger_1",
  "nodes": [
    {"id": "trigger_1", "type": "Trigger", "label": "开始"},
    {
      "id": "llm_1",
      "type": "LLM_Task",
      "label": "对话",
      "inputs": [{"name": "prompt", "type": "string"}],
      "config": {
        "model": "deepseek-chat",
        "temperature": 0.7,
        "system_prompt": "agrc://prompts/system.pt"
      }
    },
    {"id": "log_response", "type": "Log", "label": "输出回复"}
  ],
  "edges": [
    {"source": "trigger_1", "sourcePort": "payload", "target": "llm_1", "targetPort": "prompt"},
    {"source": "llm_1", "sourcePort": "response", "target": "log_response", "targetPort": "message"}
  ]
}
```

**prompts/system.pt**：

```jinja2
You are a helpful and friendly AI assistant.

Guidelines:
- Respond in the same language as the user
- Be concise and helpful
- Use friendly tone

Context: {{context}}
```

**运行**：

```bash
PYTHONIOENCODING=utf-8 python -m agenarc.cli run examples/chat_agent.agrc --input '{"payload":"Hello!"}'
```

---

### 10.3 router_agent.agrc - 带路由的 Agent

**目录结构**：

```
router_agent.agrc/
├── manifest.json
└── flow.json
```

**flow.json**（关键部分）：

```json
{
  "version": "1.0.0",
  "entryPoint": "trigger_1",
  "nodes": [
    {"id": "trigger_1", "type": "Trigger", "label": "开始"},
    {"id": "llm_1", "type": "LLM_Task", "label": "处理请求"},
    {
      "id": "router_1",
      "type": "Router",
      "label": "检查结束",
      "inputs": [{"name": "input", "type": "any"}],
      "config": {
        "conditions": [
          {"ref": "input", "operator": "contains", "value": "quit", "output": "B"},
          {"ref": "input", "operator": "contains", "value": "bye", "output": "B"},
          {"ref": "input", "operator": "contains", "value": "goodbye", "output": "B"}
        ],
        "default": "A"
      }
    },
    {"id": "log_goodbye", "type": "Log", "label": "结束语"},
    {"id": "log_continue", "type": "Log", "label": "继续"}
  ],
  "edges": [
    {"source": "trigger_1", "sourcePort": "payload", "target": "llm_1", "targetPort": "prompt"},
    {"source": "llm_1", "sourcePort": "response", "target": "router_1", "targetPort": "input"},
    {"source": "router_1", "sourcePort": "output_A", "target": "log_continue"},
    {"source": "router_1", "sourcePort": "output_B", "target": "log_goodbye"}
  ]
}
```

**运行**：

```bash
PYTHONIOENCODING=utf-8 python -m agenarc.cli run examples/router_agent.agrc --input '{"payload":"Say hello"}'
```

---

### 10.4 full_agent.agrc - 完整功能 Agent

**目录结构**：

```text
full_agent.agrc/
├── manifest.json
├── flow.json
├── prompts/
│   └── system.pt
└── scripts/
    └── text_tools.py
```

**manifest.json**：

```json
{
  "name": "full_agent",
  "version": "1.0.0",
  "entry": "flow.json",
  "permissions": {
    "allow_script_read": true,
    "allow_script_write": false,
    "autonomy_level": "level_2"
  },
  "immutable_anchors": [
    {"node_id": "trigger_1", "reason": "Entry point cannot be modified"}
  ],
  "hot_reload": true
}
```

**flow.json**（关键部分）：

```json
{
  "version": "1.0.0",
  "entryPoint": "trigger_1",
  "nodes": [
    {"id": "trigger_1", "type": "Trigger", "label": "开始"},
    {"id": "llm_1", "type": "LLM_Task", "label": "AI 处理"},
    {
      "id": "router_1",
      "type": "Router",
      "label": "路由",
      "config": {
        "conditions": [
          {"ref": "input", "operator": "contains", "value": "?", "output": "A"}
        ],
        "default": "B"
      }
    },
    {"id": "log_question", "type": "Log", "label": "问题日志"},
    {"id": "log_statement", "type": "Log", "label": "陈述日志"},
    {"id": "log_final", "type": "Log", "label": "最终输出"}
  ],
  "edges": [
    {"source": "trigger_1", "sourcePort": "payload", "target": "llm_1", "targetPort": "prompt"},
    {"source": "llm_1", "sourcePort": "response", "target": "router_1", "targetPort": "input"},
    {"source": "router_1", "sourcePort": "output_A", "target": "log_question"},
    {"source": "router_1", "sourcePort": "output_B", "target": "log_statement"},
    {"source": "llm_1", "sourcePort": "response", "target": "log_final", "targetPort": "message"}
  ]
}
```

**运行**：

```bash
PYTHONIOENCODING=utf-8 python -m agenarc.cli run examples/full_agent.agrc --input '{"payload":"What is AI?"}'
```

---

## 附录：常见问题

### Q: 如何创建新的节点类型？
A: 目前节点类型是预定义的，不能自定义添加新的内置类型。但可以通过 Script_Node 实现自定义逻辑。

### Q: 如何处理错误？
A: 在节点中添加 errorHandling 配置：

```json
{
  "errorHandling": {
    "strategy": "retry",
    "maxRetries": 3,
    "fallbackNode": "fallback_id"
  }
}
```

### Q: 如何实现多轮对话？
A: 使用 Prompt_Builder 节点的 `history` 配置实现多轮对话：

```json
{
  "nodes": [
    {"id": "trigger_1", "type": "Trigger"},
    {"id": "pb_user", "type": "Prompt_Builder", "config": {"history": "chat_history"}},
    {"id": "llm_1", "type": "LLM_Task", "config": {...}},
    {"id": "pb_assistant", "type": "Prompt_Builder", "config": {"history": "chat_history"}}
  ],
  "edges": [
    {"source": "trigger_1", "sourcePort": "payload", "target": "pb_user", "targetPort": "user"},
    {"source": "pb_user", "sourcePort": "messages", "target": "llm_1", "targetPort": "messages"},
    {"source": "llm_1", "sourcePort": "response", "target": "pb_assistant", "targetPort": "assistant"},
    {"source": "pb_assistant", "target": "trigger_1"}
  ]
}
```

关键点：
- `pb_user` 和 `pb_assistant` 配置相同的 `history` 值以共享对话历史
- `pb_assistant → trigger` 的边用于标识多轮对话会话
- Shell 中输入纯文本会自动作为 `payload` 传递

### Q: 支持哪些编程语言？
A: Script_Node 目前只支持 Python。
