# AgenArc Examples

This directory contains example `.arc` agent bundles demonstrating various capabilities.

## Agent Bundles

### chat_agent.arc
Simple conversational agent using DeepSeek LLM.
```bash
agenarc run examples/chat_agent.arc --input '{"trigger_payload":"Hello"}'
```

### demo_agent.arc
Demo agent with router and context manipulation.
```bash
agenarc run examples/demo_agent.arc --input '{"trigger_payload":"Help me with math"}'
```

### example_agent.arc
Basic example demonstrating flow structure.

### llm_example.arc
Example using LLM task operator with external prompts.

### my_agent.arc
Full-featured agent with prompts, scripts, and manifest configuration.
```bash
agengenarc run examples/my_agent.arc --input '{"user_input":"What is AI?"}'
```

### simple.arc
Minimal flow example for learning.

## Running Agents

Make sure to configure your API key in `config.yaml`:

```yaml
openai:
  api_key: your-api-key
  base_url: https://api.deepseek.com  # or OpenAI endpoint
  default_model: deepseek-chat
```

Then run:
```bash
PYTHONIOENCODING=utf-8 python -m agenarc.cli run <agent-path> --input '<json>'
```
