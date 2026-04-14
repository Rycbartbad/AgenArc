# AgenArc 插件系统

扩展 AgenArc 功能的自定义算子系统。

## 概述

AgenArc 支持三种类型的插件：

| 类型 | 加载器 | 说明 |
|------|--------|------|
| **Python** | `PythonPluginLoader` | 纯 Python 算子 |
| **C++** | `CppPluginLoader` | 通过 ctypes 加载的编译共享库 |
| **External** | `ExternalPluginLoader` | 子进程/HTTP 服务 |

## 快速开始

### Python 插件

创建插件目录：

```
my_plugin/
├── agenarc.json    # 插件清单
└── plugin.py        # 算子实现
```

**agenarc.json:**
```json
{
  "name": "my_plugin",
  "version": "1.0.0",
  "entry": "plugin.py",
  "operators": ["MyOperator"]
}
```

**plugin.py:**
```python
from typing import Any, Dict, List
from agenarc.operators.operator import IOperator
from agenarc.protocol.schema import Port

class MyOperator(IOperator):
    @property
    def name(self) -> str:
        return "my_plugin.my_operator"

    def get_input_ports(self) -> List[Port]:
        return [
            Port(name="input", type="string", description="输入文本")
        ]

    def get_output_ports(self) -> List[Port]:
        return [
            Port(name="output", type="string", description="处理后的文本")
        ]

    async def execute(self, inputs: Dict[str, Any], context) -> Dict[str, Any]:
        text = inputs.get("input", "")
        return {"output": text.upper()}
```

### C++ 插件

创建插件目录：

```
my_cpp_plugin/
├── agenarc.json    # 插件清单
└── libmy_plugin.so # 编译好的共享库
```

**agenarc.json:**
```json
{
  "name": "my_cpp_plugin",
  "version": "1.0.0",
  "library": "libmy_plugin.so",
  "symbols": ["my_operator"]
}
```

**C++ 实现:**
```cpp
extern "C" {

typedef struct {
    const char* output;
} MyOperatorResult;

void* create_my_operator(void* context) {
    return new int(42);
}

void destroy_my_operator(void* op) {
    delete static_cast<int*>(op);
}

}
```

### External 插件 (HTTP)

创建插件目录：

```
my_http_plugin/
├── agenarc.json    # 插件清单
└── agent.json      # Agent 配置
```

**agenarc.json:**
```json
{
  "name": "my_http_plugin",
  "version": "1.0.0",
  "loader": "external",
  "config": {
    "protocol": "http",
    "url": "http://localhost:8080"
  }
}
```

HTTP 服务需要实现：

| 端点 | 方法 | 说明 |
|----------|--------|-------------|
| `/health` | GET | 健康检查 |
| `/operators` | GET | 获取可用算子列表 |
| `/operators/{name}/{method}` | POST | 调用算子方法 |

## 插件发现

从配置的目录中发现插件：

```python
from agenarc.plugins.manager import PluginManager

manager = PluginManager(plugin_dirs=["~/.agenarc/plugins"])
await manager.initialize()
```

### 嵌入插件（随 Agent 分发）

插件可以内嵌到 `.agrc` 资产包中，随 Agent 一起分发：

```text
my_agent.agrc/
├── manifest.json
├── flow.json
├── plugins/              # Python 嵌入插件（自动发现）
│   └── my_embedded_plugin/
│       ├── agenarc.json
│       └── plugin.py
└── assets/
    └── plugins/          # C++/External 插件（自动安装到全局）
        └── my_cpp_plugin/
            ├── agenarc.json
            └── libmy_plugin.so
```

**加载机制：**

| 位置 | 类型 | 加载方式 |
| :--- | :--- | :--- |
| `<bundle>/plugins/` | Python | 自动发现，直接使用 |
| `<bundle>/assets/plugins/` | C++/External | 首次运行时安装到 `~/.agenarc/plugins/` |

## 热重载

`HotPluginLoader` 在文件变更时自动重载插件：

- **原子替换**：零停机更新
- **防抖**：默认 500ms，避免频繁重载
- **静默期**：等待进行中的操作完成

## 外部插件通信

外部插件使用 JSON-RPC 2.0：

```json
// 请求
{
  "jsonrpc": "2.0",
  "method": "my_operator.execute",
  "params": {"inputs": {"input": "hello"}},
  "id": 1
}

// 响应
{
  "jsonrpc": "2.0",
  "result": {"output": "HELLO"},
  "id": 1
}
```

## 算子接口

所有算子必须实现 `IOperator`：

```python
class IOperator(ABC):
    @property
    def name(self) -> str:
        """格式: 'plugin.operator'"""

    def get_input_ports(self) -> List[Port]:
        """定义输入端口"""

    def get_output_ports(self) -> List[Port]:
        """定义输出端口"""

    async def execute(
        self,
        inputs: Dict[str, Any],
        context: "ExecutionContext"
    ) -> Dict[str, Any]:
        """执行算子"""
```

## 在 Agent 中使用插件算子

在 flow.json 中，使用 `type: "Plugin"` 节点来调用自定义插件算子：

```json
{
  "version": "1.0.0",
  "nodes": [
    {"id": "trigger_1", "type": "Trigger", "label": "开始"},
    {
      "id": "my_op_1",
      "type": "Plugin",
      "label": "自定义算子",
      "inputs": [
        {"name": "input", "type": "string"}
      ],
      "outputs": [
        {"name": "output", "type": "string"}
      ],
      "config": {
        "plugin": "my_plugin",
        "function": "my_operator"
      }
    },
    {"id": "log_1", "type": "Log", "label": "输出"}
  ],
  "edges": [
    {"source": "trigger_1", "sourcePort": "payload", "target": "my_op_1", "targetPort": "input"},
    {"source": "my_op_1", "sourcePort": "output", "target": "log_1", "targetPort": "message"}
  ]
}
```

**节点配置说明：**

| 配置项 | 说明 |
|--------|------|
| `type` | 必须设为 `"Plugin"` |
| `config.plugin` | 插件名称（agenarc.json 中的 name） |
| `config.function` | 算子名称 |

**完整示例：**

```json
{
  "id": "text_processor",
  "type": "Plugin",
  "label": "文本处理",
  "inputs": [
    {"name": "text", "type": "string"},
    {"name": "mode", "type": "string", "default": "upper"}
  ],
  "outputs": [
    {"name": "result", "type": "string"}
  ],
  "config": {
    "plugin": "text_tools",
    "function": "transform"
  }
}
```

这将调用 `text_tools` 插件的 `transform` 算子。
