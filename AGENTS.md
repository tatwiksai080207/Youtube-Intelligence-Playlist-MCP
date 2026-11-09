# AI Agent Guidelines: YouTube Video Intelligence MCP Server

## 1. Project Overview
This repository contains an MCP (Model Context Protocol) server that enables conversational AI clients to discover, analyze, and curate educational YouTube videos using official YouTube Data API v3 metadata.

## 2. Mandatory Architectural Boundaries
- All YouTube network calls must pass through the YouTubeProvider interface. No direct external HTTP requests from domain modules.
- The server must remain deterministic and must not make upstream LLM calls.
- Write operations (playlist creation) must always require explicit confirmation from the human user via confirmation tokens or elicitation dialogs.
- Never exceed the daily quota allocation of 10,000 units. Every tool must check remaining quota before dispatching API calls.

## 3. Second Brain Architecture
- Engineering decisions, research notes, and run logs are maintained in `brain/` following the PARA structure (inbox, projects, areas, resources, archive).
- All notes must use wikilinks and cite requirement IDs where applicable.

## 4. Security Rules
- Never commit secrets, OAuth client secrets, refresh tokens, or personal identifiers into git.
- Test suites must use fixture cassettes or in memory fakes. Outbound network calls to googleapis are strictly forbidden in CI workflows.