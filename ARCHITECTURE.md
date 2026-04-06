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
- 资产边界：`arc://` 虚拟协议隔离，"数字生命"在边界内自由进化

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

控制循环的进入、退出和迭代。

```yaml
Loop_Control:
  inputs:
    - name: "iterate_on"
      type: "array"
    - name: "max_iterations"
      type: "integer"
      default: 100
  outputs:
    - name: "iteration_count"
      type: "integer"
    - name: "current_item"
      type: "any"
    - name: "accumulator"
      type: "any"
  config:
    - name: "checkpoint"
      type: "boolean"
      default: false
    - name: "termination_conditions"
      type: "array[Condition]"
```

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

## 第二层：自包含资产包（.arc Bundle）

### Bundle 目录结构

```
my_agent.arc/
├── manifest.json           # 资产包元数据
├── flow.json              # 图协议（等价于旧 protocol.json）
├── prompts/                # Prompt 模板目录
│   ├── system.pt           # 系统提示词模板
│   └── user.pt            # 用户提示词模板
├── scripts/                # 可执行脚本目录
│   ├── validator.py        # 自定义校验脚本
│   └── tool.py            # Agent 动态创建的脚本
└── assets/                 # 静态资源（可选）
    └── config.yaml
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
    "script_mode": "blacklist"
  },
  "immutable_nodes": ["trigger_1", "security_audit"],
  "hot_reload": true,
  "environment_requirements": {
    "keys": ["OPENAI_API_KEY", "DEEPSEEK_API_KEY"],
    "min_memory": "512MB"
  }
}
```

**字段说明：**

| 字段 | 类型 | 描述 |
|------|------|------|
| `permissions.script_mode` | `blacklist \| whitelist` | 脚本安全模式 |
| `environment_requirements.keys` | `string[]` | 必需的 API Key 环境变量 |
| `environment_requirements.min_memory` | `string` | 最小内存要求 |

> **Loader 预检机制**：在执行前检查宿主机是否注入了 `environment_requirements.keys` 中的所有环境变量，未满足则拒绝运行并提示缺失的 Key。

### VFS（虚拟文件系统）

所有节点对 `prompts/` 和 `scripts/` 的访问必须通过 `arc://` 虚拟协议：

```yaml
# 在节点配置中使用 VFS 路径
LLM_Task:
  config:
    system_prompt: "arc://prompts/system.pt"
    params:
      script_path: "arc://scripts/tool.py"
```

**VFS 映射规则：**

| VFS 路径 | 实际路径 |
|----------|----------|
| `arc://prompts/` | `<bundle>/prompts/` |
| `arc://scripts/` | `<bundle>/scripts/` |
| `arc://assets/` | `<bundle>/assets/` |
| `arc://flow.json` | `<bundle>/flow.json` |

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
      type: "string"          # arc:// 相对路径
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
    path: "arc://prompts/system.pt"
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

### AST 扫描（脚本净化）

**危险系统调用黑名单：**

```python
DANGEROUS_CALLS = {
    "os": ["system", "popen", "exec", "spawn"],
    "subprocess": ["Popen", "call", "run", "exec"],
    "builtins": ["eval", "exec", "open", "__import__"],
    "urllib": ["urlopen"],
    "requests": ["get", "post", "put", "delete"],
    "socket": ["socket"],
}
```

**拦截规则：**

- 任何新生成的脚本必须通过 AST 扫描
- 扫描不通过者将被拒绝执行，并返回 `SecurityError`
- `manifest.json` 中 `permissions.allowed_modules` 白名单优先于黑名单

**白名单模式（高安全场景）：**

```json
{
  "permissions": {
    "script_mode": "whitelist",
    "allowed_modules": ["math", "json", "re", "datetime"]
  }
}
```

> 白名单模式下，只有 `allowed_modules` 中的模块可导入，完全禁止 `__import__`、`eval`、`exec` 等危险调用。适用于高风险自进化 Agent。

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

### 不可变节点保护

`manifest.json` 中的 `immutable_nodes` 数组：

```json
{
  "immutable_nodes": ["trigger_1", "security_audit"]
}
```

**保护规则：**
- `Asset_Writer` 拒绝修改 `immutable_nodes` 内的节点
- 尝试修改将返回 `ImmutableNodeError`
- 唯一解除方式是手动编辑 `manifest.json`

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
├── VFS (arc:// 协议映射)
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
│   └── bundle.py             # .arc Bundle 加载器
│
├── plugins/                   # 插件系统
│   ├── manager.py            # 插件管理器
│   ├── operator.py           # 算子接口
│   ├── hot_loader.py         # 热重载加载器（新增）
│   └── loaders/
│       ├── python.py
│       ├── cpp.py
│       └── external.py
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
- CLI 支持 `.arc` 代理包

### 阶段 3: 自进化资产系统 (4-6 周) 🚧 进行中

- .arc Bundle 格式定义
- VFS（arc:// 协议映射）
- Asset_Reader / Asset_Writer 算子
- Runtime_Reload 热重载机制
- 双重校验链（Schema + AST Sanitizer）
- immutable_nodes 保护

### 阶段 4: 插件系统 (4-6 周) 📋 待开始

- PluginManager 核心
- Hot_Plugin_Loader（文件监听 + 原子替换）
- PythonPluginLoader / CppPluginLoader / ExternalPluginLoader
- 插件开发文档

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
| P1 | `agenarc/vfs/filesystem.py` | VFS arc:// 协议实现 | 📋 |
| P1 | `agenarc/operators/evolution.py` | 自进化算子 | 📋 |
| P1 | `agenarc/plugins/hot_loader.py` | 热重载加载器 | 📋 |
| P2 | `agenarc/engine/scheduler.py` | 调度策略 | 📋 |

---

## 测试状态

| 指标 | 值 |
|------|-----|
| 测试数量 | 317 |
| 覆盖率 | 81% |
| 目标覆盖率 | 80% ✅ |

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
| v0.3 | 2026-04-05 | 新增自进化架构：.arc Bundle、VFS、自进化算子、双重校验链 |
| v0.4 | 2026-04-06 | 阶段2完成：Router、Loop_Control、CheckpointManager、AST Evaluator |
| v0.5 | 2026-04-06 | 新增：Quiescence 热重载机制、白名单脚本模式、自愈 Error Port、environment_requirements 预检 |
