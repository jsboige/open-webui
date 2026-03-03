# Community Portal Exploration Report

**Portal:** https://openwebui.com
**Generated:** 2026-03-03
**Method:** Playwright MCP browser automation

## Top Community Functions (by popularity)

| # | Name | Author | Type | Likes | Views | Status |
|---|------|--------|------|-------|-------|--------|
| 1 | (unnamed, 30 likes) | @nokodo | function | 30 | 60K | unknown |
| 2 | AI Infographic Generator (AntV) | @Fu-Jie | function | 25 | 12K | **CANDIDATE** |
| 3 | Generate Image (action button) | @g30 | action | 24 | 15K | low priority |
| 4 | Smart Mind Map | @Fu-Jie | action | 24 | 12K | **INSTALLED** |
| 5 | Markdown Normalizer v1.2.4 | @Fu-Jie | filter | 20 | 7.3K | **INSTALLED** |
| 6 | Image Prompt Enricher | @h4nn1b4l | filter | 17 | 4.3K | low priority |
| 7 | Export to Word Enhanced | @Fu-Jie | action | 16 | 5K | **INSTALLED** |
| 8 | Agent SDK Integration | @Fu-Jie | function | 16 | 4.6K | **CANDIDATE** |
| 9 | Async Context Compression | @Fu-Jie | filter | 16 | 5.9K | **INSTALLED** |
| 10 | OpenRouter Responses API | @rbb-dev | function | 14 | 8.6K | evaluate |
| 11 | Export to Word (Chinese) | @Fu-Jie | action | 14 | 2.7K | skip |
| 12 | Anthropic API Integration | @podden | function | 13 | 4.3K | evaluate |
| 13 | Smart Token Compression | @luskadev | filter | ? | ? | **CANDIDATE** |
| 14 | Translation Assistant | @h4nn1b4l | filter | ? | ? | **CANDIDATE** |

## Top Community Tools (by popularity)

| # | Name | Author | Likes | Views | Status |
|---|------|--------|-------|-------|--------|
| 1 | Sub Agent | @skyzi000 | 39 | 29K | **INSTALLED** (v0.3.3) |
| 2 | LLM Council | @mabntt | 16 | 17K | **CANDIDATE** |
| 3 | Visualization (ASCII + Plotly) | @colton | 14 | 11K | evaluate |
| 4 | Kubernetes Monitor | @oldmoldycake | 13 | 4.1K | skip (not relevant) |
| 5 | (unnamed) | @newnol | 12 | 10K | unknown |
| 6 | Visuals Toolkit v1.0.0 | @colton | 12 | 8.4K | **INSTALLED** |
| 7 | Web Search + Crawl4AI | @alexismadd | 11 | 15K | evaluate (have Better Web Search) |
| 8 | Persistent User Storage + Git | @did100 | 9 | 4.1K | **CANDIDATE** |
| 9 | Cloud Architecture Diagrams | ? | 8 | 4.8K | low priority |
| 10 | AI Computer Use (Docker) | @nikolaiiambrosk | 7 | 5.1K | evaluate (have Open Terminal) |

## Top Community Prompts (by popularity)

| # | Name | Author | Likes | Views | Status |
|---|------|--------|-------|-------|--------|
| 1 | Reddit User Persona | @spark1 | 14 | 5.9K | skip |
| 2 | AI Task Instruction Generator | @Fu-Jie | 9 | 6.1K | **CANDIDATE** |
| 3 | Character Card Architect | @sramelyk | 7 | 3.8K | skip |
| 4 | (Python-related) | @tim | 6 | 3.2K | evaluate |
| 5 | /plan - Task Planning Assistant | @nikolaiiambrosk | 6 | 2K | **CANDIDATE** |
| 6 | Conversation Summary | @spolik123 | 5 | 5.7K | **CANDIDATE** |
| 7 | Song Lyricist | @tuxlux40 | 5 | 2.1K | skip |

---

## Recommendations for Our Educational Deployment

### Functions to Install (HIGH priority)

1. **AI Infographic Generator** (@Fu-Jie, 25 likes)
   - Generates professional infographics from text using AntV
   - SVG/PNG download support
   - **Pertinent for**: students creating visual summaries of course material

2. **Translation Assistant** (@h4nn1b4l)
   - Smart bidirectional translation with context-based summarization
   - **Pertinent for**: multi-language educational content, international students

### Functions to Evaluate (MEDIUM priority)

3. **Agent SDK Integration** (@Fu-Jie, 16 likes)
   - Advanced agent capabilities bridging Copilot SDK with OWUI
   - Intent recognition, web search, context compaction
   - **Risk**: complexity, may conflict with existing MCP/SK-Agent setup

4. **Smart Token Compression** (@luskadev)
   - Alternative to our Async Context Compression
   - Code preservation + semantic analysis
   - **Compare with**: existing async_context_compression filter

### Tools to Install (HIGH priority)

5. **LLM Council** (@mabntt, 16 likes)
   - Multi-model deliberation: individual responses + peer ranking + synthesis
   - **Pertinent for**: educational demos comparing model capabilities, teaching AI evaluation

### Tools to Evaluate (MEDIUM priority)

6. **Persistent User Storage + Git** (@did100, 9 likes)
   - File storage with Git versioning, 140+ whitelisted commands
   - **Pertinent for**: student work persistence, version control learning
   - **Overlap**: may overlap with Open Terminal functionality

### Prompts to Install

7. **AI Task Instruction Generator** (@Fu-Jie)
   - Transforms vague requirements into structured AI instructions
   - **Pertinent for**: teaching prompt engineering

8. **Task Planning Assistant** (@nikolaiiambrosk)
   - Structured implementation planning
   - **Pertinent for**: project planning, structured thinking

9. **Conversation Summary** (@spolik123)
   - Detailed conversation summaries with handoff notes
   - **Pertinent for**: documenting learning sessions

### Functions to Update

- **Markdown Normalizer**: currently v1.2.4, check if newer version exists
- **Smart Mind Map**: verify latest from @Fu-Jie
- **Export to Word Enhanced**: verify latest from @Fu-Jie
- **Async Context Compression**: verify latest from @Fu-Jie
- **Flash Card**: verify latest version
- **Sub Agent**: currently v0.3.3, check for updates

### Items NOT Recommended

- **Kubernetes Monitor**: not relevant for educational deployment
- **Cloud Architecture Diagrams**: too specialized
- **Image generation tools**: already have SD Forge integration
- **OpenRouter Responses API**: complex, may conflict with native OpenRouter config
- **Reddit User Persona**: not educational
- **Character Card Architect**: not educational
- **Song Lyricist**: not educational

---

## Currently Installed Summary

### Already up-to-date (from community)
| Item | Type | Version | Author |
|------|------|---------|--------|
| Smart Mind Map | Action (global) | latest | @Fu-Jie |
| Markdown Normalizer | Filter (global) | v1.2.4 | @Fu-Jie |
| Export to Word Enhanced | Action (global) | latest | @Fu-Jie |
| Async Context Compression | Filter (global) | latest | @Fu-Jie |
| Flash Card | Action (global) | latest | ? |
| Sub Agent | Tool | v0.3.3 | @skyzi000 |
| Visuals Toolkit | Tool | v1.0.0 | @colton |
| YouTube Transcript | Tool | latest | ? |

### Installed but NOT from community
| Item | Type | Notes |
|------|------|-------|
| Better Web Search Tool | Tool | Custom (@TRUC Yoann) |
| Web Scrape | Tool | v0.0.4 (@ekatiyar) |
| SK-Agent MCP | Tool | Custom internal |
| MoEA | Filter (NOT global) | Should be cleaned up or configured |
| Mixture of Agents | Action (NOT global) | Should be cleaned up or configured |

### Cleanup Needed
- **MoEA**: was supposed to be deleted by preflight-cleanup.py — still present
- **Mixture of Agents**: was supposed to be deleted — still present
