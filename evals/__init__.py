"""Kutana AI agent evaluation framework.

Two modes:
- **Mock evals** (`-m mock`): Agent system prompt + synthetic transcript
  -> Anthropic Messages API with tool definitions -> capture tool_use blocks
  -> LLM-as-Judge scores -> Langfuse.
- **E2E evals** (`-m e2e`): Create real meeting on dev cluster -> activate
  managed agent -> inject transcript -> observe actual MCP tool calls
  -> score via LLM-as-Judge -> Langfuse traces.
"""
