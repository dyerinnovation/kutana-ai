# External Documentation Rules

External docs (`external-docs/`) are written for **end users and third-party developers** — not internal contributors.

- **Assume the reader has no access to the source code.** Never reference internal file paths, module names, or implementation details.
- **Include clone/install steps.** Every guide that requires running code locally must start with cloning the repo and installing dependencies.
- **Use generic paths.** Write `/path/to/kutana-ai` instead of absolute paths. Let the reader substitute their own.
- **Explain prerequisites explicitly.** List required tools (Node.js, Python, etc.) with minimum versions. Don't assume the reader has anything pre-installed beyond a standard dev environment.
- **Keep examples copy-pasteable.** Commands should work if the reader follows the steps in order. Include placeholder values (e.g. `cvn_your_key_here`) and tell the reader what to replace.
- **No internal jargon.** Use "Kutana API" not "api-server". Use "agent gateway" not "agent-gateway service". Explain concepts before using them.
- **Link to related docs.** Cross-reference other external docs pages, not internal docs.
- **MCP server registration.** Always instruct users to register MCP servers via `claude mcp add-json` CLI command. Manual JSON config editing does not work. Always include `--scope user` for servers that should persist across projects.
