# AgenArc 架构规划

> Directed-graph Agent Orchestration Engine
> 协议-执行-可视化 三层解耦

---

## 架构定性

```
声明式协议 + 模板语法 + 黑板架构 + 自进化资产
```

**核心哲学："机制与策略分离"**
- 内核：极致稳定，仅负责安全调度与资源校验
- 自修复/逻辑进化：由用户在图流程内自行构建
- 资产边界：`agrc://` 虚拟协议隔离，"数字生命"在边界内自由进化

---

## 第一层：Agent 流程协议（DSL）

### 设计决策

| 问题 | 决策 |
|------|------|
| 节点粒度 | 函数级（Functional Atoms）+ Script_Node |
| 边语义 | 控制流为显式连线，数据流为隐式 Context |
| 状态边界 | 协议声明 checkpoint 语义，引擎负责持久化 |
| Router output | conditions 内直接指定 output_A/B |
| Edge guard | 移除（逻辑必须通过 Router/Script_Node） |
| onFailure | 移至 Node config + Error Port |

---

### 节点类型定义

#### ① Trigger

图的入口节点，任何图有且仅有一个 Trigger。

```yaml
Trigger:
  outputs:
    - name: "payload"
      type: "any"
  config:
    - name: "source"
      type: "enum[manual|webhook|schedule|event]"
```

#### ② LLM_Task

执行 LLM 推理任务。

```yaml
LLM_Task:
  inputs:
    - name: "prompt"
      type: "string"
    - name: "context"
      type: "object"
  outputs:
    - name: "response"
      type: "string"
    - name: "usage"
      type: "object"
  config:
    - name: "model"
      type: "string"
      default: "gpt-4"
    - name: "temperature"
      type: "number"
      default: 0.7
    - name: "system_prompt"
      type: "string"
    - name: "plugin"
      type: "string"
    - name: "function"
      type: "string"
    - name: "params"
      type: "object"
```

#### ③ Router

基于条件表达式路由到不同分支（If-Else / Switch-Case）。

```yaml
Router:
  inputs:
    - name: "input"
      type: "any"
  outputs:
    - name: "output_A"
      type: "any"
    - name: "output_B"
      type: "any"
  config:
    - name: "conditions"
      type: "array[Condition]"
    - name: "default"
      type: "enum[A|B]"
```

#### ④ Loop_Control

基于反馈循环的迭代控制。支持 `done=False` 继续循环，`done=True` 退出。

**反馈循环工作流程**：

```
Loop_Control (done=False)
    ↓
Body 节点 (处理 current_item)
    ↓
Body 输出回传给 Loop_Control (accumulator_input)
    ↓
Loop_Control 读取 accumulator，进入下一次迭代
    ↓
直到 done=True，退出循环
```

```yaml
Loop_Control:
  inputs:
    - name: "iterate_on"
      type: "array"
    - name: "max_iterations"
      type: "integer"
      default: 100
    - name: "accumulator_input"        # 新增：接收 body 回传值
      type: "any"
  outputs:
    - name: "iteration_count"
      type: "integer"
    - name: "current_item"
      type: "any"
    - name: "accumulator"
      type: "any"
    - name: "done"
      type: "boolean"                 # false=继续循环，true=退出
  config:
    - name: "checkpoint"
      type: "boolean"
      default: false
    - name: "termination_conditions"
      type: "array[Condition]"
```

**两种典型场景**：

| 场景 | 用法 |
|------|------|
| 列表遍历 | iterate_on 传入数组，accumulator 自动收集结果 |
| 自我修正 | max_iterations 控制重试次数，accumulator 保存错误信息 |

**避坑指南**：

1. 必须设置 max_iterations 限制，防止无限循环
2. 必须有闭环边从 body 连回 Loop_Control 的 accumulator_input
3. done=true 时，通过 sourceValue 条件边跳过后续节点

#### ⑤ Memory_I/O

与持久化存储交互。

```yaml
Memory_I/O:
  inputs:
    - name: "key"
      type: "string"
    - name: "value"
      type: "any"
  outputs:
    - name: "value"
      type: "any"
  config:
    - name: "mode"
      type: "enum[read|write|delete]"
    - name: "idempotent"
      type: "boolean"
      default: true
    - name: "checkpoint"
      type: "boolean"
```

#### [扩展] Script_Node

执行自定义脚本逻辑。

```yaml
Script_Node:
  inputs: "dynamic"
  outputs: "dynamic"
  config:
    - name: "language"
      type: "enum[python|lua|cpp]"
    - name: "script"
      type: "string"
    - name: "timeout"
      type: "integer"
      default: 30
```

#### [扩展] Subgraph

引用外部子图。

```yaml
Subgraph:
  inputs: "mapped"
  outputs: "mapped"
  config:
    - name: "graph_ref"
      type: "string"
    - name: "input_mapping"
      type: "object"
    - name: "output_mapping"
      type: "object"
```

#### [扩展] Plugin

调用自定义插件算子。

**插件来源：**
- 全局插件目录：`~/.agenarc/plugins/`（需单独安装，所有类型）
- 嵌入插件目录：`<bundle>/plugins/`（**Python**，自动发现）
- 资产包插件目录：`<bundle>/assets/plugins/`（**C++/External**，自动安装到全局）

```yaml
Plugin:
  inputs: "dynamic"
  outputs: "dynamic"
  config:
    - name: "plugin"
      type: "string"              # 插件名称
    - name: "function"
      type: "string"              # 算子名称
```

**使用示例：**

```yaml
- id: "my_operator"
  type: "Plugin"
  config:
    plugin: "text_tools"
    function: "transform"
```

---

### Node 通用结构

```yaml
Node:
  id: "string"
  type: "NodeType 枚举"
  label: "string"
  description: "string"

  errorHandling:
    strategy: "enum[retry|fallback|skip|abort]"
    maxRetries: "integer"
    errorPort: "string"
    fallbackNode: "string"

  checkpoint: "boolean"
  idempotent: "boolean"
```

---

### Edge 结构

```yaml
Edge:
  source: "string"
  sourcePort: "string"
  target: "string"
  targetPort: "string"

  label: "string"
  style: "enum[solid|dashed]"
```

**边只承载控制流语义（顺序）。数据通过全局 Context 隐式传递。**

---

### Condition（条件表达式）

```yaml
Condition:
  ref: "string"
  operator: "enum[eq|ne|gt|gte|lt|lte|contains|startsWith|endsWith|in|notIn|exists|notExists]"
  value: "any"
  output: "string"

  and: "array[Condition]"
  or: "array[Condition]"
  not: "Condition"
```

---

### 模板语法

```yaml
{{nodes.<node_id>.outputs.<port_name>}}
{{context.<key>}}
{{loop.current_item}}
{{loop.iteration_count}}
{{env.<ENV_VAR_NAME>}}
```

---

## 第二层：自包含资产包（.agrc Bundle）

### Bundle 目录结构

```
my_agent.agrc/
├── manifest.json           # 资产包元数据
├── flow.json              # 图协议（等价于旧 protocol.json）
├── prompts/                # Prompt 模板目录
│   ├── system.pt           # 系统提示词模板
│   └── user.pt            # 用户提示词模板
├── scripts/                # 可执行脚本目录
│   ├── validator.py        # 自定义校验脚本
│   └── tool.py            # Agent 动态创建的脚本
├── plugins/                 # 嵌入式 Python 插件（自动发现）
│   └── my_python_plugin/
│       ├── agenarc.json
│       └── plugin.py
└── assets/                 # 静态资源 + C++/External 插件
    ├── config.yaml
    └── plugins/             # C++/External 插件（自动安装到全局）
        └── my_cpp_plugin/
            ├── agenarc.json
            └── libmy_plugin.so
```

### manifest.json 结构

```json
{
  "name": "my_agent",
  "version": "1.0.0",
  "entry": "flow.json",
  "permissions": {
    "allow_script_read": true,
    "allow_script_write": true,
    "allow_prompt_read": true,
    "allow_prompt_write": false,
    "allowed_modules": ["os", "json", "re"],
    "autonomy_level": "level_2"
  },
  "immutable_anchors": [
    {"node_id": "trigger_1", "reason": "Entry point cannot be modified"},
    {"node_id": "audit_1", "reason": "Security audit node - kernel enforced lock"}
  ],
  "hot_reload": true,
  "gas_budget": 1000,
  "max_memory_mb": 128,
  "environment_requirements": {
    "keys": ["OPENAI_API_KEY", "DEEPSEEK_API_KEY"],
    "min_memory": "512MB"
  }
}
```

**字段说明：**

| 字段 | 类型 | 描述 |
|------|------|------|
| `permissions.autonomy_level` | `level_0 \| level_1 \| level_2 \| level_3` | 信任式自主等级 |
| `immutable_anchors` | `ImmutableAnchor[]` | 内核强制锁定的节点 |
| `gas_budget` | `integer` | 表达式求值的 Gas 上限 |
| `max_memory_mb` | `integer` | SafeContext 内存限制 |

> **Loader 预检机制**：在执行前检查宿主机是否注入了 `environment_requirements.keys` 中的所有环境变量，未满足则拒绝运行并提示缺失的 Key。

### VFS（虚拟文件系统）

所有节点对 `prompts/` 和 `scripts/` 的访问必须通过 `agrc://` 虚拟协议：

```yaml
# 在节点配置中使用 VFS 路径
LLM_Task:
  config:
    system_prompt: "agrc://prompts/system.pt"
    params:
      script_path: "agrc://scripts/tool.py"
```

**VFS 映射规则：**

| VFS 路径 | 实际路径 |
|----------|----------|
| `agrc://prompts/` | `<bundle>/prompts/` |
| `agrc://scripts/` | `<bundle>/scripts/` |
| `agrc://assets/` | `<bundle>/assets/` |
| `agrc://flow.json` | `<bundle>/flow.json` |

**禁止事项：**
- 严禁直接使用宿主机绝对路径（如 `/home/user/...` 或 `C:\...`）
- 严禁使用 `../` 遍历父目录
- 违反者将触发安全异常

---

## 第三层：自进化算子（Evolutionary Operators）

### ⑥ Asset_Reader

读取 Bundle 内的资产文件。

```yaml
Asset_Reader:
  inputs:
    - name: "path"
      type: "string"          # agrc:// 相对路径
  outputs:
    - name: "content"
      type: "string"          # 文件原文
    - name: "metadata"
      type: "object"          # 文件元信息
  config:
    - name: "encoding"
      type: "string"
      default: "utf-8"
    - name: "required"
      type: "boolean"
      default: true
```

**使用示例：**

```yaml
- id: "load_prompt"
  type: "Asset_Reader"
  config:
    path: "agrc://prompts/system.pt"
```

### ⑦ Asset_Writer

向 Bundle 内写入/创建资产文件。

```yaml
Asset_Writer:
  inputs:
    - name: "path"
      type: "string"
    - name: "content"
      type: "string"
    - name: "operation"
      type: "enum[create|update|delete]"
  outputs:
    - name: "success"
      type: "boolean"
    - name: "path"
      type: "string"
  config:
    - name: "atomic"
      type: "boolean"
      default: true          # 失败立即回滚
    - name: "allow_create"
      type: "boolean"
      default: true          # 允许 CREATE 语义
```

**原子性保证：**
- 写入前先创建 `.tmp` 文件
- 写入成功后 rename
- 失败则删除 `.tmp`，原文件保持不变

### ⑧ Runtime_Reload

触发引擎热重载，刷新插件注册表。

```yaml
Runtime_Reload:
  inputs: []
  outputs:
    - name: "reloaded_scripts"
      type: "array[string]"
    - name: "success"
      type: "boolean"
  config:
    - name: "target"
      type: "enum[plugins|scripts|both]"
      default: "both"
```

**执行流程：**

1. **Quiescence（静默期）**：暂停接收新任务，等待当前原子节点执行完毕
2. **Snapshot 保存**：保存当前 Global Context 完整状态
3. 扫描 `scripts/` 目录
4. 对新增/修改的 `.py` 文件执行 AST 扫描
5. 刷新 PluginManager 注册表
6. 恢复 Context（保持不丢失）
7. 返回重载结果

> **Quiescence 机制**：确保 Loop_Control 等中间状态节点在重载前完成当前原子操作，避免状态不一致。

---

## 第四层：内核级强校验（Guardrail & Validation）

### 双重校验链

```
┌─────────────────────────────────────────────────────────┐
│                   校验流程                                │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  1. Schema 校验                                          │
│     └── flow.json 修改 → 节点存在？端口匹配？无孤立边？    │
│                                                         │
│  2. 脚本净化 (Sanitizer)                                 │
│     └── 新生成的 .py → AST 扫描 → 危险调用拦截            │
│                                                         │
│  3. Error Port 反馈                                      │
│     └── 校验失败 → 结构化错误堆栈 → Agent 自我修正        │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

### AST 扫描（信任式自治）

**核心哲学转变：从"防御型沙箱"到"信任 AI"**

```
防御型沙箱：拦截一切，只允许白名单
信任式自治：允许一切，除了明确危险的内核属性
```

**危险属性黑名单（仅拦截这些）：**

```python
DANGEROUS_ATTRIBUTES = {
    # Interpreter internals
    "__globals__", "__builtins__", "__code__", "__func__",
    "__closure__", "__class__", "__bases__", "__mro__",
    "__subclasses__", "__dicto__",
    # Frame/traceback
    "f_back", "f_builtins", "f_code", "f_globals", "f_locals",
    "tb_frame", "tb_lasti", "tb_next",
    # System escape
    "system", "popen", "spawn", "fork", "exec", "eval",
    "exec_file", "run_code",
    # File operations
    "remove", "unlink", "rmdir", "rename",
    # Import machinery
    "__import__", "import_module",
}
```

**信任式自治原则：**

| 特性 | level_0 (Zero Knowledge) | level_1 (Supervised) | level_2 (Autonomous) | level_3 (Self-Evolving) |
|------|----------------------|---------------------|---------------------|------------------------|
| agrc:// 访问 | 禁用 | 启用 | 启用 | 启用 |
| Script_Node trust_level | locked | locked | trusted | developer |
| 属性访问 | 仅安全方法 | 仅安全方法 | 全部允许 | 全部允许 |
| 推导式 | 禁用 | 禁用 | 启用 | 启用 |
| open/compile | 禁用 | 禁用 | 启用 | 启用 |
| flow.json 修改 | 禁用 | 禁用 | 启用 | 启用 |
| manifest.json 修改 | 禁用 | 禁用 | 禁用 | 启用 |
| Gas 计费 | 500 ops | 1000 ops | 1000 ops | 无限制 |
| SafeContext 内存 | 64MB | 128MB | 128MB | 256MB |

**Script_Node 信任级别：**

Script_Node 由开发者编写，默认使用 `developer` 模式（完全信任），不受 autonomy_level 限制。

可通过 node config 显式设置：
```json
{
  "id": "my_script",
  "type": "Script_Node",
  "config": {
    "script_trust_level": "locked"  // 可选：locked | trusted | developer
  }
}
```

| trust_level | 表达式 | 语句 | 适用场景 |
|-------------|--------|------|----------|
| `locked` | ASTEvaluator | 拒绝 | 最安全，仅表达式 |
| `trusted` | ASTEvaluator | safe exec | 平衡模式 |
| `developer` | ASTEvaluator | full exec | **默认**，完全信任 |

**level_0 (Zero Knowledge) 设计意义：**

```
level_0: Agent 是"纯函数"——输入 → 推理 → 输出
         Agent 不知道自己在 Agent 框架中运行
         不知道 agrc://、prompts/、scripts/ 的存在
         只能通过 prompt/input 接收信息，通过 output 返回结果

适用场景：
• 第三方 LLM API 调用（Claude/GPT）
• 极度敏感的数据处理（不允许任何文件系统访问）
• 简单的请求-响应模式
```

**Gas 计费机制：**

每次 AST 节点访问消耗 1 Gas。超出 `gas_budget` 限制时抛出 `GasExceededError`，防止无限循环。

**SafeContext 包装器：**

使用 `tracemalloc` 追踪表达式求值过程中的内存分配，确保不会溢出宿主机内存。

**黑名单 vs 白名单：**

```
旧：黑名单模式（拦截 DANGEROUS_CALLS 中列出的所有调用）
新：信任模式（仅拦截 DANGEROUS_ATTRIBUTES 中的内核属性）
```

> 信任式自治让 Agent 能够使用标准库方法（split, append, regex, json 等），同时保持内核安全。

### Error Port 机制

校验失败时，错误堆栈通过 Error Port 返回：

```yaml
Error_Stack:
  code: "SCHEMA_VALIDATION_FAILED"
  message: "Node 'xxx' references non-existent port 'yyy'"
  node_id: "router_1"
  path: "flow.json#/nodes/0"
  suggestion: "Available ports: output_A, output_B"
```

**自愈提示逻辑：**

引擎在检测到 Schema 错误时，直接将正确的信息填充到 `suggestion` 字段：

| 错误类型 | suggestion 示例 |
|----------|-----------------|
| 端口引用错误 | `Available ports: output_A, output_B` |
| 缺失必填字段 | `Required fields: model, system_prompt` |
| 循环引用检测 | `Cycle detected at: trigger_1 → llm_1 → router_1` |
| AST 安全拦截 | `Blocked call: os.exec. Allowed: math, json, re` |

**Agent 自修复闭环：**

```
校验失败 → Error Port → Agent 反思 → Asset_Writer 修改 → Runtime_Reload → 重试
```

---

## 第五层：安全性与不可变性

### 不可变锚点（Immutable Anchors）

`manifest.json` 中的 `immutable_anchors` 数组：

```json
{
  "immutable_anchors": [
    {"node_id": "trigger_1", "reason": "Entry point cannot be modified"},
    {"node_id": "audit_1", "reason": "Security audit node - kernel enforced lock"}
  ]
}
```

**保护规则：**

- `Asset_Writer` 拒绝修改 `immutable_anchors` 内的节点
- 即使在 `level_3`（Self-Evolving）模式下，某些核心节点也由**内核强制锁定**
- 尝试修改将返回 `ImmutableAnchorError`
- 唯一解除方式是手动编辑 `manifest.json`（需要重启引擎）

**不可变锚点的设计意义：**

```
┌──────────────────────────────────────────────────────────────┐
│                    Agent 自我进化闭环                          │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│   Asset_Reader          LLM              Asset_Writer         │
│   (读取flow.json)  →  (优化逻辑)  →    (回写flow.json)         │
│         ↑                                      │             │
│         │                                      ↓             │
│         │                              Runtime_Reload         │
│         │                                      │             │
│         └──────────────────────────────────────┘             │
│                          闭环                                 │
│                                                              │
│   ┌──────────────────────────────────────────────────────┐   │
│   │  Immutable Anchors (内核锁定)                         │   │
│   │  • trigger_1: 入口点不可修改                          │   │
│   │  • audit_1: 安全审计节点不可删除                       │   │
│   │  • error_handler: 错误处理节点不可删除                  │   │
│   └──────────────────────────────────────────────────────┘   │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

**内核锁定的节点类型：**

| 节点类型 | 原因 | 是否可配置 |
|----------|------|------------|
| `Trigger` | 图的唯一起点 | 是（可通过 immutable_anchors） |
| 安全审计节点 | 合规要求 | 是（可通过 immutable_anchors） |
| 错误处理节点 | 系统完整性 | 是（可通过 immutable_anchors） |
| 其他节点 | 业务需求 | 由 autonomy_level 决定 |

### 上下文保持

`Runtime_Reload` 必须保证全局 Context 不丢失：

```python
class Runtime_Reload_Operator:
    async def execute(self, inputs, context):
        # 1. 保存当前 Context
        snapshot = context.snapshot()

        # 2. 执行重载
        self.plugin_manager.reload()

        # 3. 恢复 Context
        context.restore(snapshot)

        return {"reloaded": True, "context_preserved": True}
```

---

## 第六层：执行引擎

### 核心组件

```
ExecutionEngine
├── Loader (Graph + Bundle 解析)
├── VFS (agrc:// 协议映射)
├── Scheduler (控制流调度)
├── Executor (节点执行)
├── PluginManager (Hot_Plugin_Loader)
├── StateManager (Context + Checkpoint)
└── Guardrail (Schema 校验 + AST 扫描)
```

### StateManager 分层架构

```
Global Context (全局上下文)
├── execution_id, graph_id
├── 跨节点共享变量
└── checkpoint 历史

Local State (局部状态)
├── node-specific 变量
├── 输入/输出值
└── 重试计数器

Checkpoint (检查点)
├── 全状态快照
└── 用于中断恢复
```

### 上下文隔离与 Copy-on-Write

Context 默认**引用传递**，在 PARALLEL 模式下会导致数据竞争。需配合声明式隔离：

```json
{
  "context": {
    "mode": "copy_on_write",
    "large_object_keys": ["crawled_data", "base64_images"],
    "strict_mode": true
  }
}
```

**实现机制**：

| 机制 | 描述 |
|------|------|
| `large_object_keys` | 声明后，走延迟深拷贝（CoW） |
| `strict_mode` | 启用 in-place 篡改检测 |
| `_origin_ids` | 内部追踪对象 ID，检测直接修改 |

### 并发控制：乐观锁与 CAS

高并发 Join 场景下，使用乐观锁避免 Context 级锁的性能瓶颈：

```json
{
  "concurrent_mode": {
    "strategy": "optimistic",
    "max_retries": 3,
    "backoff": "exponential",
    "backoff_base": 2
  }
}
```

**CAS 冲突重试流程**：

```
1. 读取当前值 expected
2. 执行 compare_and_set(key, expected, new_value)
3. 若 ConflictError，指数退避重试（最多 max_retries 次）
4. 超限后进入 ERROR_FATAL
```

### 事务性 Memory_I/O 与补偿节点

Memory_I/O 支持事务模式，但外部 I/O（HTTP/邮件/支付）本质不可回滚，需通过**补偿节点**实现：

```json
{
  "id": "send_email",
  "type": "Script_Node",
  "side_effects": ["irreversible"],
  "compensation": "send_retry_email"
}
```

**副作用类型**：

| 类型 | 可回滚？ | 处理方式 |
|------|----------|----------|
| `memory_write` | 是 | Context 快照 |
| `file_write` | 是 | WAL 回滚 |
| `http_post` | 否 | 补偿节点 |
| `payment` | 否 | 补偿 + 告警 |
| `email` | 否 | 补偿 |

**补偿不嵌套原则**：补偿节点本身失败时，不递归寻找其补偿，直接进入 `ERROR_FATAL`，记录 WAL 日志等待人工介入。

---

## 第七层：插件系统

### Hot_Plugin_Loader 实现步骤

```
1. 初始化
   └── 扫描 plugins/ 目录
   └── 读取各插件的 agenarc.json 清单
   └── 注册到 PluginRegistry

2. 动态加载
   └── 按需导入（lazy load）
   └── importlib.import_module()

3. 热重载
   └── 文件监听（watchdog）
   └── AST 扫描新脚本
   └── 原子替换注册表条目
   └── Zero-downtime 切换

4. 隔离执行（可选）
   └── multiprocessing.Process
   └── 插件崩溃不影响主进程
```

### IOperator 接口

```python
class IOperator(ABC):
    @property
    def name(self) -> str: ...
    @property
    def version(self) -> str: ...
    def get_input_ports(self) -> List[Port]: ...
    def get_output_ports(self) -> List[Port]: ...
    async def execute(
        self,
        inputs: Dict[str, Any],
        context: ExecutionContext
    ) -> Dict[str, Any]: ...
    async def validate(self, inputs: Dict[str, Any]) -> bool: ...
```

---

## 项目结构

```
agenarc/
├── protocol/                 # 协议层
│   ├── schema.py            # JSON Schema 定义
│   ├── loader.py             # 协议加载器
│   └── validator.py          # 验证器
│
├── engine/                   # 执行层
│   ├── executor.py           # 核心引擎
│   ├── scheduler.py          # 调度策略
│   ├── state.py              # 状态管理
│   ├── recovery.py           # 断点恢复
│   └── guardrail.py           # 校验链（新增）
│
├── vfs/                       # 虚拟文件系统
│   ├── __init__.py
│   ├── filesystem.py         # VFS 核心
│   └── bundle.py             # .agrc Bundle 加载器
│
├── plugins/                   # 插件系统
│   ├── manager.py            # 插件管理器
│   ├── hot_loader.py         # 热重载加载器
│   ├── operator.py           # 算子接口
│   └── loaders/              # 多语言加载器
│       ├── python.py         # Python 插件加载器
│       ├── cpp.py            # C++ 插件加载器 (ctypes)
│       └── external.py       # 外部插件 (stdio/HTTP)
│
├── operators/                 # 内置算子库（新增）
│   ├── __init__.py
│   ├── builtin.py            # Trigger, Memory_I/O
│   ├── llm.py                # LLM_Task
│   ├── router.py             # Router
│   ├── loop.py               # Loop_Control
│   └── evolution.py          # Asset_Reader, Asset_Writer, Runtime_Reload
│
├── graph/                     # 图数据结构
│   ├── node.py
│   ├── edge.py
│   └── traversal.py
│
└── cli/                       # CLI
```

---

## 三阶段里程碑

### 阶段 1: MVP 引擎 (4-6 周) ✅ 完成

- JSON Schema 协议定义
- ExecutionEngine 核心（线性流）
- 线性调度器
- 内置 Trigger / LLM_Task / Memory_I/O 算子
- CLI: `agenarc run <protocol.json>`

### 阶段 2: 完整执行引擎 (6-8 周) ✅ 完成

- Router 节点（条件分支）
- Loop_Control 节点（循环 + 回溯）
- Script_Node（自定义脚本 + AST安全求值）
- CheckpointManager + 文件持久化
- AST 安全表达式求值器
- CLI 支持 `.agrc` 代理包

### 阶段 3: 自进化资产系统 (4-6 周) ✅ 完成

- .agrc Bundle 格式定义
- VFS（arc:// 协议映射）
- Asset_Reader / Asset_Writer 算子
- Runtime_Reload 热重载机制
- 双重校验链（Schema + AST Sanitizer）
- immutable_nodes 保护

### 阶段 4: 插件系统 (4-6 周) ✅ 完成

- PluginManager 核心 - 完整的插件注册和发现机制
- Hot_Plugin_Loader - 文件监听 + 原子替换 + 零停机重载
- PythonPluginLoader - 动态导入 Python 插件
- CppPluginLoader - ctypes 加载编译的共享库
- ExternalPluginLoader - stdio/HTTP IPC 外部插件
- 插件开发文档

### 阶段 4.5: 交互式 Shell (1 周) ✅ 完成

- InteractiveREPL - 交互式终端命令执行
- 支持纯文本输入自动转换为 `{"input": "text"}` 格式
- 支持直接输入 JSON 对象作为完整 payload
- 实时反馈执行结果

### 阶段 5: 可视化平台 (8-12 周) 📋 待开始

- React + TypeScript Canvas
- 节点拖拽与连接
- 属性编辑面板
- 执行预览与调试

---

## 关键文件

| 优先级 | 文件路径 | 作用 | 状态 |
|--------|----------|------|------|
| P0 | `agenarc/protocol/schema.py` | 协议根基 | ✅ |
| P0 | `agenarc/engine/executor.py` | 执行引擎核心 | ✅ |
| P0 | `agenarc/engine/evaluator.py` | AST安全表达式求值器 | ✅ |
| P0 | `agenarc/operators/router.py` | Router算子 | ✅ |
| P0 | `agenarc/operators/loop.py` | Loop_Control算子 | ✅ |
| P0 | `agenarc/engine/state.py` | CheckpointManager | ✅ |
| P1 | `agenarc/engine/guardrail.py` | 校验链（Schema + AST） | 📋 |
| P1 | `agenarc/vfs/filesystem.py` | VFS agrc:// 协议实现 | ✅ |
| P1 | `agenarc/operators/evolution.py` | 自进化算子 | ✅ |
| P1 | `agenarc/plugins/hot_loader.py` | 热重载加载器 | ✅ |
| P1 | `agenarc/plugins/loaders/*.py` | 多语言插件加载器 | ✅ |
| P2 | `agenarc/engine/scheduler.py` | 调度策略 | 📋 |

---

## 测试状态

| 指标 | 值 |
|------|-----|
| 测试数量 | 619 |
| 覆盖率 | 79% |
| 目标覆盖率 | 90% |

---

## 参考借鉴

| 领域 | 参考项目 |
|------|----------|
| 协议设计 | AWS Step Functions 状态机、LCEL (LangChain) |
| 资产打包 | Docker Image、LLVM Bitcode |
| 虚拟文件系统 | FUSE、Virtuozzo |
| 插件热重载 | Python importlib、Elixir code reloading |
| 沙箱安全 | AST 白名单求值器、Electron sandbox |
| 不可变性设计 | Git immutable history、Capsicum |

---

## 变更日志

| 版本 | 日期 | 变更 |
|------|------|------|
| v0.1 | 2026-04-05 | 初始草案 |
| v0.2 | 2026-04-05 | DSL 修订：移除 Edge guard，onFailure 移至 Node + Error Port |
| v0.3 | 2026-04-05 | 新增自进化架构：.agrc Bundle、VFS、自进化算子、双重校验链 |
| v0.4 | 2026-04-06 | 阶段2完成：Router、Loop_Control、CheckpointManager、AST Evaluator |
| v0.5 | 2026-04-06 | 新增：Quiescence 热重载机制、白名单脚本模式、自愈 Error Port、environment_requirements 预检 |
| v0.6 | 2026-04-06 | 测试覆盖：411 passed, 85% |
| v0.7 | 2026-04-06 | 阶段3完成：VFS + Asset_Reader/Writer + Runtime_Reload |
| v0.8 | 2026-04-06 | 新增：三档信任模式、CoW隔离、乐观锁CAS、补偿节点不嵌套原则 |
| v0.9 | 2026-04-07 | 阶段4完成：插件系统 + 交互式 Shell |
