# AgenArc Agent 开发完全指南

## 目录

1. [示例 Agents](#示例-agents)
2. [什么是 .arc Agent](#1-什么是-arc-agent)
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
| **router_agent** | 带路由 | Trigger + LLM_Task + Router + Log |
| **loop_agent** | 带循环结构 | Trigger + LLM_Task + Log |
| **full_agent** | 完整功能 | Trigger + LLM_Task + Router + Log + manifest |

### 运行示例

```bash
# Hello Agent（无需 LLM）
PYTHONIOENCODING=utf-8 python -m agenarc.cli run examples/hello_agent.arc --input '{}'

# Chat Agent
PYTHONIOENCODING=utf-8 python -m agenarc.cli run examples/chat_agent.arc --input '{"trigger_payload":"Hello!"}'

# Router Agent
PYTHONIOENCODING=utf-8 python -m agenarc.cli run examples/router_agent.arc --input '{"trigger_payload":"Say hello"}'

# Full Agent
PYTHONIOENCODING=utf-8 python -m agenarc.cli run examples/full_agent.arc --input '{"trigger_payload":"What is AI?"}'
```

---

## 1. 什么是 .arc Agent

`.arc` 是 AgenArc 的 Agent 资产包格式。每个 Agent 是一个文件夹，包含执行所需的所有组件：

- **prompts/** - 提示词模板
- **scripts/** - 自定义脚本
- **flow.json** - 工作流定义
- **manifest.json** - 配置信息

---

## 2. 创建你的第一个 Agent

### 步骤 1：创建目录结构

```
my_agent.arc/
├── manifest.json
├── flow.json
├── prompts/
│   ├── system.pt
│   └── user.pt
└── scripts/
    └── tool.py
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
  "metadata": {"name": "my_agent"},
  "nodes": [
    {"id": "trigger_1", "type": "Trigger", "label": "Start"},
    {
      "id": "llm_1",
      "type": "LLM_Task",
      "label": "Chat",
      "inputs": [{"name": "prompt", "type": "string"}],
      "config": {
        "model": "deepseek-chat",
        "system_prompt": "arc://prompts/system.pt"
      }
    },
    {"id": "log_1", "type": "Log", "label": "Output"}
  ],
  "edges": [
    {"source": "trigger_1", "sourcePort": "payload", "target": "llm_1", "targetPort": "prompt"},
    {"source": "llm_1", "sourcePort": "response", "target": "log_1", "targetPort": "message"}
  ]
}
```

### 步骤 4：编写 prompts/system.pt

```jinja2
You are a helpful AI assistant.
{{context}}
```

### 步骤 5：运行 Agent

```bash
PYTHONIOENCODING=utf-8 python -m agenarc.cli run my_agent.arc --input '{"trigger_payload":"Hello"}'
```

---

## 3. 目录结构详解

### 最小结构（必须）

```
agent_name.arc/
├── manifest.json    # 必须：Agent 配置
├── flow.json        # 必须：工作流定义
└── prompts/        # 必须：至少一个 .pt 文件
    └── system.pt   # 必须：系统提示词
```

### 完整结构

```
agent_name.arc/
├── manifest.json      # Agent 元数据
├── flow.json         # 工作流定义
├── prompts/          # Prompt 模板目录
│   ├── system.pt     # 系统提示词（必须）
│   └── user.pt       # 用户提示词（可选）
├── scripts/          # 自定义脚本目录（可选）
│   ├── tool.py       # 工具脚本
│   └── processor.py  # 处理脚本
└── assets/          # 静态资源目录（可选）
    └── config.yaml  # 配置文件
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

| 等级 | 说明 | Script_Node trust_level |
|------|------|------------------------|
| `level_0` | Zero Knowledge - AI 感知不到 arc:// 协议 | locked |
| `level_1` | Supervised - 仅表达式求值 | locked |
| `level_2` | Autonomous - 可修改 flow.json | trusted |
| `level_3` | Self-Evolving - 最高权力 | developer |

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
  "metadata": {
    "name": "agent_name",
    "description": "描述",
    "author": "作者",
    "tags": ["tag1", "tag2"]
  },
  "nodes": [...],
  "edges": [...]
}
```

### version 版本号

固定值：`"1.0.0"`

### entryPoint 入口点

必须是某个节点（Node）的 `id`，且该节点类型必须是 `Trigger`。

### metadata 元数据

| 字段 | 必填 | 类型 | 说明 |
|------|------|------|------|
| `name` | 是 | string | Agent 名称 |
| `description` | 否 | string | 描述 |
| `author` | 否 | string | 作者 |
| `tags` | 否 | array | 标签列表 |

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
{"source": "trigger_1", "sourcePort": "payload", "target": "llm_1", "targetPort": ""}
```

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
  "inputs": [
    {"name": "prompt", "type": "string"},
    {"name": "context", "type": "object"}
  ],
  "outputs": [
    {"name": "response", "type": "string"},
    {"name": "usage", "type": "object"}
  ],
  "config": {
    "model": "deepseek-chat",
    "temperature": 0.7,
    "system_prompt": "arc://prompts/system.pt"
  }
}
```

**输入端口**：

| 端口名 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `prompt` | string | - | 用户输入的提示词 |
| `context` | object | null | 上下文对象 |

**输出端口**：

| 端口名 | 类型 | 说明 |
|--------|------|------|
| `response` | string | LLM 生成的响应 |
| `usage` | object | token 使用统计 |

**config 配置项**：

| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `model` | string | - | 模型名称（如 deepseek-chat、gpt-4） |
| `temperature` | number | 0.7 | 温度参数，控制随机性（0-1） |
| `system_prompt` | string | - | 系统提示词，可用 VFS 路径 |
| `max_tokens` | integer | - | 最大生成 token 数 |

---

### 6.3 Router（路由）

**作用**：根据条件将数据路由到不同的分支。

**示例**：

```json
{
  "id": "router_1",
  "type": "Router",
  "label": "路由",
  "inputs": [
    {"name": "input", "type": "any"}
  ],
  "outputs": [
    {"name": "output_A", "type": "any"},
    {"name": "output_B", "type": "any"}
  ],
  "config": {
    "conditions": [
      {
        "ref": "input",
        "operator": "contains",
        "value": "quit",
        "output": "B"
      }
    ],
    "default": "A"
  }
}
```

**输入端口**：

| 端口名 | 类型 | 说明 |
|--------|------|------|
| `input` | any | 要判断的输入值 |

**输出端口**：

| 端口名 | 类型 | 说明 |
|--------|------|------|
| `output_A` | any | 条件不满足时的输出 |
| `output_B` | any | 条件满足时的输出 |

**config 配置项**：

| 配置项 | 类型 | 说明 |
|--------|------|------|
| `conditions` | array | 条件数组，按顺序匹配 |
| `default` | string | 默认分支，"A" 或 "B" |

**conditions 条件数组**：

每个条件对象：

```json
{
  "ref": "input",
  "operator": "contains",
  "value": "quit",
  "output": "B"
}
```

| 字段 | 类型 | 说明 |
|------|------|------|
| `ref` | string | 引用的变量名 |
| `operator` | string | 操作符 |
| `value` | any | 比较的值 |
| `output` | string | 满足条件时输出 "A" 或 "B" |
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

---

### 6.4 Loop_Control（循环控制）

**作用**：对数组或集合进行迭代处理。

**示例**：

```json
{
  "id": "loop_1",
  "type": "Loop_Control",
  "label": "处理列表",
  "inputs": [
    {"name": "iterate_on", "type": "array"},
    {"name": "max_iterations", "type": "integer", "default": 100}
  ],
  "outputs": [
    {"name": "iteration_count", "type": "integer"},
    {"name": "current_item", "type": "any"},
    {"name": "accumulator", "type": "any"},
    {"name": "done", "type": "boolean"}
  ]
}
```

**输入端口**：

| 端口名 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `iterate_on` | array | - | 要迭代的数组 |
| `max_iterations` | integer | 100 | 最大迭代次数 |

**输出端口**：

| 端口名 | 类型 | 说明 |
|--------|------|------|
| `iteration_count` | integer | 当前迭代计数 |
| `current_item` | any | 当前迭代项 |
| `accumulator` | any | 累积值 |
| `done` | boolean | 是否完成 |

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

---

### 6.7 Log（日志节点）

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

### 6.8 Context_Set（设置上下文）

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

### 6.9 Context_Get（获取上下文）

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

## 7. 模板语法

在 prompts/*.pt 文件和某些配置项中，可以使用模板变量。

### 7.1 基础变量

| 语法 | 说明 |
|------|------|
| `{{agent_name}}` | Agent 名称 |
| `{{user_context}}` | 用户上下文 |
| `{{current_time}}` | 当前时间 |

### 7.2 上下文变量

| 语法 | 说明 |
|------|------|
| `{{context}}` | 整个上下文对象 |
| `{{context.xxx}}` | 上下文中的特定字段 |
| `{{context.user_input}}` | 用户输入 |
| `{{context.history}}` | 对话历史 |

### 7.3 节点输出变量

| 语法 | 说明 |
|------|------|
| `{{nodes.xxx.outputs.yyy}}` | 获取节点 xxx 的 yyy 输出 |

**示例**：

```jinja2
The LLM said: {{nodes.llm_1.outputs.response}}
Token usage: {{nodes.llm_1.outputs.usage.total_tokens}}
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

---

## 8. VFS 虚拟文件系统

VFS 允许通过 `arc://` 协议安全地访问 bundle 内部的资源，而不需要暴露实际文件系统路径。

### 8.1 VFS 路径映射

| VFS 路径 | 实际路径 |
|----------|----------|
| `arc://prompts/` | `<bundle>/prompts/` |
| `arc://scripts/` | `<bundle>/scripts/` |
| `arc://assets/` | `<bundle>/assets/` |
| `arc://flow.json` | `<bundle>/flow.json` |

### 8.2 在配置中使用 VFS

**LLM_Task 配置示例**：

```json
{
  "id": "llm_1",
  "type": "LLM_Task",
  "config": {
    "system_prompt": "arc://prompts/system.pt"
  }
}
```

**Asset_Reader 配置示例**：

```json
{
  "id": "reader_1",
  "type": "Asset_Reader",
  "config": {
    "path": "arc://scripts/tool.py"
  }
}
```

### 8.3 完整 VFS 路径示例

| 用途 | VFS 路径 |
|------|----------|
| 系统提示词 | `arc://prompts/system.pt` |
| 用户提示词 | `arc://prompts/user.pt` |
| 工具脚本 | `arc://scripts/tool.py` |
| 配置文件 | `arc://assets/config.yaml` |
| 流程定义 | `arc://flow.json` |

---

## 9. 运行和调试

### 9.1 配置 API Key

在项目根目录创建或编辑 `config.yaml`：

```yaml
openai:
  api_key: your-api-key-here
  base_url: https://api.deepseek.com
  default_model: deepseek-chat
  temperature: 0.7
```

**常用 API 端点**：

| 服务商 | base_url | 模型示例 |
|--------|----------|----------|
| DeepSeek | `https://api.deepseek.com` | deepseek-chat |
| OpenAI | `https://api.openai.com/v1` | gpt-4, gpt-3.5-turbo |
| Ollama (本地) | `http://localhost:11434/v1` | llama2, mistral |

### 9.2 运行命令

```bash
PYTHONIOENCODING=utf-8 python -m agenarc.cli run <agent-path> --input '<json>'
```

### 9.3 输入格式

`--input` 参数必须是有效的 JSON：

**简单字符串**：

```bash
--input '{"trigger_payload": "Hello"}'
```

**带上下文的输入**：

```bash
--input '{"trigger_payload": {"user_input": "Hello", "context": {"name": "Alice"}}}'
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

### 9.5 调试技巧

1. **使用 Log 节点**：在关键节点后添加 Log 节点查看输出
2. **简化流程**：先用一个 LLM_Task 测试，再逐步添加其他节点
3. **检查输出**：使用 `-v` 查看完整的节点输出

---

## 10. 完整示例

### 10.1 hello_agent.arc - 最简单的 Agent

**目录结构**：

```
hello_agent.arc/
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
  "metadata": {"name": "hello_agent"},
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
PYTHONIOENCODING=utf-8 python -m agenarc.cli run examples/hello_agent.arc --input '{}'
```

---

### 10.2 chat_agent.arc - 简单对话 Agent

**目录结构**：

```
chat_agent.arc/
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
  "metadata": {"name": "chat_agent"},
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
        "system_prompt": "arc://prompts/system.pt"
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
PYTHONIOENCODING=utf-8 python -m agenarc.cli run examples/chat_agent.arc --input '{"trigger_payload":"Hello!"}'
```

---

### 10.3 router_agent.arc - 带路由的 Agent

**目录结构**：

```
router_agent.arc/
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
PYTHONIOENCODING=utf-8 python -m agenarc.cli run examples/router_agent.arc --input '{"trigger_payload":"Say hello"}'
```

---

### 10.4 full_agent.arc - 完整功能 Agent

**目录结构**：

```text
full_agent.arc/
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
PYTHONIOENCODING=utf-8 python -m agenarc.cli run examples/full_agent.arc --input '{"trigger_payload":"What is AI?"}'
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
A: 当前版本需要在外部维护对话历史，通过 context 传递历史记录。

### Q: 支持哪些编程语言？
A: Script_Node 目前只支持 Python。

---

## 附录：配置文件参考

### config.yaml 完整示例

```yaml
openai:
  api_key: your-api-key
  base_url: https://api.deepseek.com
  default_model: deepseek-chat
  temperature: 0.7
  max_tokens: 2000

agent:
  checkpoint_dir: ~/.agenarc
  enable_checkpoint: true
  max_parallel: 4
```
