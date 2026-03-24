---
name: new-mcp-tool
description: Add a new MCP tool to the Convene MCP server. TRIGGER on: new MCP tool, add MCP tool, new tool for agents, expose feature via MCP, new convene tool.
---

# New MCP Tool

Checklist for adding a new tool to the Convene MCP server.

## Checklist

- [ ] Add tool handler in `services/mcp-server/src/mcp_server/tools/<name>.py`
  - Define input schema (Pydantic model)
  - Implement handler function
  - Register in `tools/__init__.py`
- [ ] Add unit tests in `services/mcp-server/tests/tools/test_<name>.py`
- [ ] Add tool documentation page in `docs/technical/mcp-tools/<name>.md`
  - Tool name, description, parameters, example usage
- [ ] Update OpenClaw plugin if the tool should be exposed to OpenClaw clients
  - See `integrations/openclaw-plugin/` and `docs/integrations/OPENCLAW.md`
- [ ] Create or update the relevant skill SKILL.md in `.claude/skills/` if this tool powers a new agent behavior
- [ ] Test with the Claude Code skill (`/convene-meeting`) and verify the tool appears

## Reference

See `claude_docs/MCP_Server_Architecture.md` for server patterns and tool registration.
