# AgenArc Examples

可运行的 Agent 示例：

| Agent | 说明 | 关键特性 |
|-------|------|----------|
| **my_first_agent** | 多轮对话 | Trigger + Prompt_Builder + LLM_Task |
| **qq_bot_agent** | QQ 机器人 | Trigger + LLM_Task + 事件插件（serve 模式） |
| **euchea** | PDF→代码生成 | Script_Node + LLM_Task + 热键插件（serve 模式） |

## 运行示例

```bash
# 多轮对话（需要 LLM）
uv run agenarc run examples/my_first_agent.agrc --input '{"payload":"Hello"}'

# 交互式对话
uv run agenarc shell examples/my_first_agent.agrc
```

## 服务模式示例

需要事件插件的 agent 通过 `agenarc serve` 启动：

```bash
# QQ 机器人（需 NapCat WebSocket）
uv run agenarc serve examples/qq_bot_agent.agrc

# euchea — PDF→代码生成（需 keyboard 库）
uv run agenarc serve examples/euchea.agrc
```

## euchea — PDF→代码生成热键服务

全局监听 **Alt+A** 热键，扫描 `C:\Users\Admin\Downloads\AA\` 目录中的 PDF 和 C++ 源文件，由 LLM 生成/完善代码并保存到 `project/` 子目录。

### 安装依赖

```bash
uv pip install keyboard              # 全局热键（必需）
uv pip install markitdown            # PDF→MD（推荐，微软出品）
uv pip install pdfplumber PyMuPDF    # PDF→MD 备选方案
uv pip install openai                # LLM 调用
```

### 使用方法

```bash
# 后台服务模式（推荐）
uv run agenarc serve examples/euchea.agrc

# 单次执行（开发调试）
uv run agenarc run examples/euchea.agrc --input '{}'
```

按 **Alt+A** 触发，**Ctrl+C** 停止服务。

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
