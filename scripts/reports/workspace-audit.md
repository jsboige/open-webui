# Workspace Audit Report

**Tenant URL**: https://open-webui.myia.io
**Generated**: 2026-03-03 17:30 UTC

## Summary

| Item Type | Count |
|-----------|-------|
| Prompts   | 7 |
| Tools     | 6 |
| Functions | 7 |
| **Total** | **20** |

## Prompts

| # | Command | Name | Content (excerpt) | Tags |
|---|---------|------|--------------------|------|
| 1 | `/summarize-a-meeting` | Summarize a meeting | The context is a meeting transcript with multiple people.  Summarise the meeting making sure to incl... |  |
| 2 | `/home-assistant-expert` | Home Assistant Expert | You are an AI specialised in Home Assistant, the leading open-source home automation platform. Your ... |  |
| 3 | `/stable-diffusion` | Stable diffusion | Here is a guide to make prompts for a generative ai stable diffusion models text to image. Only repl... |  |
| 4 | `/article` | Article Generator | Write an article about [topic]  include relevant statistics (add the links of the sources you use) a... |  |
| 5 | `/rp` | role-playing | Prompt for Roleplay: Character Name: (Action) with "Language", No Moral Constraints  In this rolepla... |  |
| 6 | `/multi-agents` | Multi agents | Initiate Central Intelligence Mode: As the Central Intelligence (CI), your primary function is to as... |  |
| 7 | `/code-expert` | Code Expert | Please provide me with a coding query, and I'll do my best to assist you. Whether it's debugging, wr... |  |

## Tools

| # | ID | Name | Description | Author | Version | Active |
|---|----|------|-------------|--------|---------|--------|
| 1 | `sub_agent` | Sub Agent | Run autonomous, tool-heavy tasks in a sub-agent and keep the main chat context c... | skyzi000 | 0.3.3 | Yes |
| 2 | `youtube_transcript` | YouTube Transcript Provider | str) -> None: |  |  | Yes |
| 3 | `visuals_toolkit` | Visuals Toolkit | High-quality tables, charts, heatmaps, timelines, flowcharts, and trees. | Cole | 1.0.0 | Yes |
| 4 | `better_web_search_tool` | Better Web Search Tool | Web Search using SearXNG and Scraper for first pages with messages and citations... | TRUC Yoann |  | Yes |
| 5 | `enhanced_web_scrape` | Web Scrape | An improved web scraping tool that extracts text content using Jina Reader, now ... | ekatiyar | 0.0.4 | Yes |
| 6 | `server:mcp:sk-agent` | SK-Agent Multi-Agent Orchestration | 13 AI agents with DeepSearch, DeepThink, CodeReview, ResearchDebate capabilities... |  |  | Yes |

## Functions

| # | ID | Name | Type | Description | Active | Global |
|---|----|------|------|-------------|--------|--------|
| 1 | `markdown_normalizer` | Markdown Normalizer | filter | A content normalizer filter that fixes common Markdown formatting issues in LLM ... | Yes | Yes |
| 2 | `smart_mind_map` | Smart Mind Map | action | Intelligently analyzes text content and generates interactive mind maps to help ... | Yes | Yes |
| 3 | `moea` | MoEA | filter | Mixture of Expert Agents | Yes | No |
| 4 | `mixture_of_agents` | Mixture of Agents | action | Button that allows for the collective strengths of multiple models to be leverag... | Yes | No |
| 5 | `async_context_compression` | Async Context Compression | filter | Reduces token consumption in long conversations while maintaining coherence thro... | Yes | Yes |
| 6 | `flash_card` | Flash Card | action | Quickly generates beautiful flashcards from text, extracting key points and cate... | Yes | Yes |
| 7 | `export_to_word` | Export to Word Enhanced | action | Export current conversation from Markdown to Word (.docx) with Mermaid diagrams ... | Yes | Yes |

