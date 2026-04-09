# AgenArc Examples

可运行的 Agent 示例，按复杂度递增排列：

| Agent | 说明 | 关键特性 |
|-------|------|----------|
| **hello_agent** | Hello World | Trigger + Log |
| **chat_agent** | 简单对话 | Trigger + LLM_Task + Log |
| **router_agent** | 条件路由 | Trigger + LLM_Task + Router + Log |
| **full_agent** | 完整功能 | manifest + permissions + immutable_anchors |

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

## 详细文档

完整的 Agent 开发指南请参阅：[docs/agents.md](docs/agents.md)
