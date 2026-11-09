---
title: Model Context Protocol Architecture and Primitives
type: reference
created: 2026-11-09
tags:
  - mcp
  - protocol
  - architecture
  - tools
requirements:
  - FR-5
  - NFR-USE-1
  - NFR-USE-2
  - NFR-USE-3
---

# Model Context Protocol Architecture and Primitives

## Summary
The Model Context Protocol (MCP) defines an open standard based on JSON RPC 2.0 enabling language model hosts to access tools, load context resources, and interact with human users.

## Core Protocol Concepts
1. **Host and Client**: The host application (for example Claude Desktop or Gemini) embeds an MCP client that manages a dedicated connection to the MCP server.
2. **Transport**:
   - `stdio`: Standard input and output stream communication between the local process and host. Server logs must strictly write to `stderr` to avoid corrupting protocol packets.
   - `Streamable HTTP`: Localhost HTTP transport with Origin validation to protect against local DNS rebinding.
3. **Primitives**:
   - **Tools**: Executable functions declared with JSON Schema `inputSchema` and annotations (`readOnlyHint`, `destructiveHint`, `idempotentHint`).
   - **Resources**: URI addressed read only documents providing background metrics and state context (for example `youtube://metrics/quota`).
   - **Elicitation**: An MCP interactive primitive where the server prompts the user directly for confirmation through the host interface, avoiding automated model intervention.

## Schema Conventions
- Strict schema validation using `"additionalProperties": false`.
- Descriptive parameter explanations including explicit units and ranges.
- Structured returns alongside clear textual summaries.

## Related Notes
- [[brain/index|Second Brain Index]]
- [[brain/areas/security/prompt-injection-defence|Prompt Injection Defence]]
- [[brain/areas/engineering/provider-interface-pattern|Provider Interface Pattern]]

