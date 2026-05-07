# AgenArc Examples

可运行的 Agent 示例，按复杂度递增排列：

| Agent | 说明 | 关键特性 |
|-------|------|----------|
| **hello_agent** | Hello World | Trigger + Log |
| **chat_agent** | 简单对话 | Trigger + LLM_Task + Log |
| **router_agent** | 条件路由 | Trigger + LLM_Task + Router + Log |
| **full_agent** | 完整功能 | manifest + permissions + immutable_anchors |
| **euchea** | PDF→代码生成服务 | Script_Node(dev) + LLM_Task + 热键监听 |

## 运行示例

```bash
# Hello Agent（无需 LLM）
PYTHONIOENCODING=utf-8 python -m agenarc.cli run examples/hello_agent.agrc --input '{}'

# Chat Agent（需要 LLM）
PYTHONIOENCODING=utf-8 python -m agenarc.cli run examples/chat_agent.agrc --input '{"payload":"Hello!"}'

# Router Agent
PYTHONIOENCODING=utf-8 python -m agenarc.cli run examples/router_agent.agrc --input '{"payload":"Say hello"}'

# Full Agent
PYTHONIOENCODING=utf-8 python -m agenarc.cli run examples/full_agent.agrc --input '{"payload":"What is AI?"}'
```

## euchea - PDF→代码生成热键服务

euchea 是一个后台服务，全局监听 Alt+A 热键，将指定目录中的 PDF（转 Markdown）和 C++ 源文件注入 AI 提示词，由 LLM 生成/完善代码并保存到输出目录。

### 安装依赖

```bash
uv pip install keyboard              # 全局热键（必需）
uv pip install markitdown            # PDF→MD（推荐，微软出品）
uv pip install pdfplumber PyMuPDF    # PDF→MD 备选方案
uv pip install openai                # LLM 调用
```

### 服务模式运行（推荐）

```bash
PYTHONIOENCODING=utf-8 python examples/euchea_serve.py
```

按 Alt+A 触发处理，Ctrl+C 停止服务。

### 单次运行（开发调试）

```bash
PYTHONIOENCODING=utf-8 python -m agenarc.cli run examples/euchea.agrc --input '{}'
```

### 工作流

```
Alt+A 按下
  → 扫描 C:\Users\Admin\Downloads\AA\
  → PDF 转 Markdown
  → 读取 .cpp/.h 等源文件
  → 构建提示词 → AI 生成代码
  → 保存到 C:\Users\Admin\Downloads\AA\project\
```

## 详细文档

完整的 Agent 开发指南请参阅：[docs/agents.md](docs/agents.md)
