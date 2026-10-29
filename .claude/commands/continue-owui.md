---
description: Continue planned work from GitHub issues roadmap
allowed-tools: Read, Edit, Write, Bash, Grep, Glob, Agent, WebFetch, TodoWrite
---

# /continue-owui - Resume Planned Work

Pick up the next task from the Open Terminal / OWUI improvement roadmap. Reads GitHub issues, checks current state, and starts implementing the next priority item.

## What This Command Does

1. **Read current state**: Check MEMORY.md, git status, and recent commits
2. **Fetch GitHub issues**: List open issues on jsboige/open-webui, sorted by number (priority order)
3. **Identify next task**: Find the first open issue whose dependencies are met
4. **Plan and implement**: Enter plan mode or start implementing based on complexity
5. **Update state**: Mark progress in MEMORY.md and close issues when done

## When to Use

- Starting a new session to continue the Open Terminal roadmap
- After completing a task, to pick up the next one
- When context is fresh and you want to continue incremental improvements

## Issue Priority Order

| # | Issue | Dependencies |
|---|-------|-------------|
| #1 | Data science packages (Dockerfile custom) | None |
| #2 | ACL per-tenant (expose to students) | #1 |
| #3 | sk-agent + Terminal integration | #1 |
| #4 | Per-school environments (custom Dockerfiles) | #1, #2 |
| #5 | Per-tenant isolation (dedicated containers) | #2 |
| #6 | Interactive guided labs (TP) | #1, #2 |
