# AgenArc Agent Examples

## 概述

`.arc` 是 AgenArc 的 Agent 资产包格式，一个自包含的目录包，包含执行 Agent 所需的所有组件。

## 目录结构

```
my_agent.arc/
├── manifest.json      # 资产包元数据
├── flow.json         # 图协议定义
├── prompts/          # Prompt 模板
│   ├── system.pt     # 系统提示词
│   └── user.pt       # 用户提示词
├── scripts/          # 可执行脚本
│   └── tool.py       # 自定义工具
└── assets/           # 静态资源（可选）
    └── config.yaml
```

---

## 1. manifest.json - 资产包配置

```json
{
  "name": "my_agent",
  "version": "1.0.0",
  "entry": "flow.json",
  "permissions": {
    "allow_script_read": true,
    "allow_script_write": true,
    "allow_prompt_read": true,
    "allow_prompt_write": false
  },
  "immutable_nodes": ["trigger_1"],
  "hot_reload": true
}
```

| 字段 | 类型 | 说明 |
|------|------|------|
| `name` | string | Agent 名称 |
| `version` | string | 版本号 |
| `entry` | string | 入口文件（通常是 flow.json） |
| `permissions` | object | 权限配置 |
| `immutable_nodes` | array | 不可变节点列表 |
| `hot_reload` | boolean | 是否启用热重载 |

---

## 2. flow.json - 图协议定义

### 2.1 基本结构

```json
{
  "version": "1.0.0",
  "entryPoint": "trigger_1",
  "metadata": {
    "name": "my_agent",
    "description": "Agent 描述"
  },
  "nodes": [...],
  "edges": [...]
}
```

| 字段 | 说明 |
|------|------|
| `version` | 协议版本，固定为 "1.0.0" |
| `entryPoint` | 入口节点 ID（有且只有一个 Trigger） |
| `metadata` | 元数据信息 |
| `nodes` | 节点列表 |
| `edges` | 边列表（控制流连接） |

### 2.2 Node 节点定义

```json
{
  "id": "unique_node_id",
  "type": "Trigger",
  "label": "显示名称",
  "description": "节点描述",
  "inputs": [],
  "outputs": [],
  "config": {}
}
```

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | string | 唯一标识，节点间不能重复 |
| `type` | string | 节点类型（见下方类型列表） |
| `label` | string | UI 显示名称 |
| `description` | string | 详细描述 |
| `inputs` | array | 输入端口定义 |
| `outputs` | array | 输出端口定义 |
| `config` | object | 节点特定配置 |

#### 节点类型 (NodeType)

| 类型 | 说明 | 用途 |
|------|------|------|
| `Trigger` | 触发器 | 图的入口点，只能有一个 |
| `LLM_Task` | LLM 任务 | 调用语言模型 |
| `Router` | 路由 | 条件分支 |
| `Loop_Control` | 循环控制 | 迭代处理 |
| `Memory_I/O` | 记忆 I/O | 读写持久化存储 |
| `Script_Node` | 脚本节点 | 执行自定义脚本 |
| `Log` | 日志 | 输出调试信息 |
| `Context_Set` | 设置上下文 | 向全局 context 写入 |
| `Context_Get` | 获取上下文 | 从全局 context 读取 |

### 2.3 Port 端口定义

```json
{
  "name": "port_name",
  "type": "string",
  "description": "端口描述",
  "default": "默认值"
}
```

| 字段 | 说明 |
|------|------|
| `name` | 端口名称 |
| `type` | 数据类型（string, any, object, array, boolean, integer） |
| `description` | 描述 |
| `default` | 默认值（可选） |

### 2.4 Edge 边定义

```json
{
  "source": "node_id",
  "sourcePort": "output_port_name",
  "target": "target_node_id",
  "targetPort": "input_port_name"
}
```

| 字段 | 说明 |
|------|------|
| `source` | 源节点 ID |
| `sourcePort` | 源节点输出端口（可选） |
| `target` | 目标节点 ID |
| `targetPort` | 目标节点输入端口（可选） |

---

## 3. 模板语法

在 prompts 和配置中可以使用模板变量：

### 3.1 上下文变量

```jinja2
{{context.user_input}}    # 用户输入
{{context.loop_count}}   # 循环计数
{{context.history}}      # 历史记录
```

### 3.2 节点输出

```jinja2
{{nodes.llm_1.outputs.response}}  # 获取 llm_1 节点的 response 输出
```

### 3.3 特殊变量

```jinja2
{{agent_name}}      # Agent 名称
{{user_context}}    # 用户上下文
{{current_time}}    # 当前时间
```

### 3.4 VFS 路径引用

在节点配置中使用 `arc://` 协议引用 bundle 内部文件：

```yaml
# LLM_Task 配置示例
config:
  system_prompt: "arc://prompts/system.pt"   # 读取 prompts/system.pt
  script_path: "arc://scripts/tool.py"       # 读取 scripts/tool.py
```

**VFS 映射规则：**

| VFS 路径 | 实际路径 |
|----------|----------|
| `arc://prompts/` | `<bundle>/prompts/` |
| `arc://scripts/` | `<bundle>/scripts/` |
| `arc://assets/` | `<bundle>/assets/` |
| `arc://flow.json` | `<bundle>/flow.json` |

---

## 4. 节点详解

### 4.1 Trigger - 触发器

入口节点，生成初始 payload。

```json
{
  "id": "trigger_1",
  "type": "Trigger",
  "label": "Start"
}
```

**输出：**
- `payload`: 初始数据载荷

### 4.2 LLM_Task - LLM 任务

调用语言模型生成响应。

```json
{
  "id": "llm_1",
  "type": "LLM_Task",
  "label": "Chat",
  "inputs": [
    {"name": "prompt", "type": "string"},
    {"name": "context", "type": "object", "default": null}
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

**配置项：**
| 配置 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `model` | string | - | 模型名称 |
| `temperature` | number | 0.7 | 温度参数 |
| `system_prompt` | string | - | 系统提示词 |
| `max_tokens` | integer | - | 最大 token 数 |

### 4.3 Router - 路由

基于条件表达式路由到不同分支。

```json
{
  "id": "router_1",
  "type": "Router",
  "label": "Route",
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
        "ref": "context.user_input",
        "operator": "contains",
        "value": "quit",
        "output": "B"
      }
    ],
    "default": "A"
  }
}
```

**条件操作符 (operator)：**

| 操作符 | 说明 | 示例 |
|--------|------|------|
| `eq` | 等于 | `{"operator": "eq", "value": "yes"}` |
| `ne` | 不等于 | `{"operator": "ne", "value": "no"}` |
| `gt` | 大于 | `{"operator": "gt", "value": 5}` |
| `lt` | 小于 | `{"operator": "lt", "value": 10}` |
| `contains` | 包含 | `{"operator": "contains", "value": "help"}` |
| `startsWith` | 开头是 | `{"operator": "startsWith", "value": "!"}` |
| `endsWith` | 结尾是 | `{"operator": "endsWith", "value": "?"}` |
| `in` | 在列表中 | `{"operator": "in", "value": ["a", "b"]}` |
| `exists` | 存在 | `{"operator": "exists"}` |

### 4.4 Loop_Control - 循环控制

迭代处理数组或集合。

```json
{
  "id": "loop_1",
  "type": "Loop_Control",
  "label": "Process Items",
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

### 4.5 Memory_I/O - 记忆 I/O

读写持久化存储。

```json
{
  "id": "memory_1",
  "type": "Memory_I/O",
  "label": "Memory",
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

### 4.6 Script_Node - 脚本节点

执行自定义 Python 脚本。

```json
{
  "id": "script_1",
  "type": "Script_Node",
  "label": "Process",
  "inputs": [
    {"name": "script", "type": "string", "default": "result = context.get('input', '')"}
  ],
  "outputs": [
    {"name": "result", "type": "any"},
    {"name": "success", "type": "boolean"},
    {"name": "error", "type": "string"}
  ]
}
```

**脚本示例：**

```python
# 获取上下文值
input_text = context.get('input', '')

# 处理数据
result = input_text.upper()

# 返回结果
result = {"processed": result}
```

### 4.7 Log - 日志节点

输出调试信息。

```json
{
  "id": "log_1",
  "type": "Log",
  "label": "Debug",
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

### 4.8 Context_Set / Context_Get

设置和获取全局上下文变量。

```json
{
  "id": "set_ctx",
  "type": "Context_Set",
  "label": "Set Context",
  "inputs": [
    {"name": "key", "type": "string"},
    {"name": "value", "type": "any"}
  ],
  "outputs": [
    {"name": "success", "type": "boolean"}
  ]
}
```

---

## 5. prompts/ 目录

存放 Prompt 模板文件，支持模板变量。

### 示例：system.pt

```jinja2
You are {{agent_name}}, a helpful AI assistant.

Guidelines:
- Be concise and helpful
- Use context: {{context}}
- Think step by step

Current conversation:
{{history}}
```

### 示例：user.pt

```jinja2
{{user_input}}
```

---

## 6. scripts/ 目录

存放可执行的 Python 脚本，供 Script_Node 调用。

### 示例：tool.py

```python
"""自定义工具函数"""

def process_text(text: str) -> dict:
    """处理文本"""
    return {
        "upper": text.upper(),
        "lower": text.lower(),
        "length": len(text)
    }

def calculate(expression: str) -> dict:
    """安全计算数学表达式"""
    allowed = set("0123456789+-*/.() ")
    if not all(c in allowed for c in expression):
        return {"error": "Invalid characters"}

    try:
        result = eval(expression)
        return {"result": result}
    except ZeroDivisionError:
        return {"error": "Division by zero"}
    except Exception as e:
        return {"error": str(e)}
```

---

## 7. 运行 Agent

### 配置 API Key

在项目根目录的 `config.yaml` 中配置：

```yaml
openai:
  api_key: your-api-key
  base_url: https://api.deepseek.com
  default_model: deepseek-chat
  temperature: 0.7
```

### 运行命令

```bash
PYTHONIOENCODING=utf-8 python -m agenarc.cli run examples/chat_agent.arc \
  --input '{"trigger_payload":"Hello"}'
```

### 输入格式

`--input` 参数需要是有效的 JSON：

```json
{"trigger_payload": "用户输入内容"}
{"user_input": "问题"}
{"input": "命令"}
```

---

## 8. 完整示例

### chat_agent.arc - 对话 Agent

```
chat_agent.arc/
├── manifest.json
├── flow.json
└── prompts/
    ├── system.pt
    └── user.pt
```

**flow.json 核心结构：**

```json
{
  "nodes": [
    {"id": "trigger_1", "type": "Trigger"},
    {"id": "llm_1", "type": "LLM_Task"},
    {"id": "log_response", "type": "Log"}
  ],
  "edges": [
    {"source": "trigger_1", "sourcePort": "payload", "target": "llm_1", "targetPort": "prompt"},
    {"source": "llm_1", "sourcePort": "response", "target": "log_response", "targetPort": "message"}
  ]
}
```

**运行：**

```bash
PYTHONIOENCODING=utf-8 python -m agenarc.cli run examples/chat_agent.arc \
  --input '{"trigger_payload":"What is AI?"}'
```

---

## 9. 最佳实践

1. **节点 ID 命名**：使用有意义的名称，如 `llm_chat`、`router_main`
2. **错误处理**：为关键节点配置 `errorHandling`
3. **模块化**：将复杂逻辑放入 scripts/ 目录
4. **Prompt 模板**：使用 `{{variable}}` 语法提高复用性
5. **VFS 引用**：优先使用 `arc://` 协议而非绝对路径
6. **不可变节点**：将核心 Trigger 等节点加入 `immutable_nodes`
