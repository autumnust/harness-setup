**Instance-specific setup — NVIDIA laptop:** This machine is the local entry point for SSH-based development machines. Use the connection methods already defined in `~/.ssh/config`, keep laptop-only credentials and device settings local, and do not copy them into repositories or remote machines.

## MCP

Found out codex mcp from `codex mcp --list`. This is a tool that allows you to use the codex api in a local environment.
- For JIRA issue related inquiries, use jira mcp for both read and write operations.

When MCP is not responding, try the followings: 
- Use nvinfo cli to see if there're known maintenance or issues.
- For JIRA issues: check #cdd-jirasw using Slack MCP and see if there are active discussion regarding jira issues. 