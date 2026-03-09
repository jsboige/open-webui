# Skill: Continue OWUI - Resume Planned Work from Roadmap

**Version:** 1.0.0
**Usage:** `/continue-owui`

---

## Objective

Automatically identify and start working on the next priority task from the Open Terminal / OWUI improvement roadmap (GitHub issues on jsboige/open-webui).

---

## Workflow

### Phase 1: State Assessment

**Actions:**
1. Read auto-memory (`MEMORY.md`) for current deployment state
2. Check git status and recent commits for in-progress work
3. Fetch open GitHub issues from the roadmap

**Commands:**
```bash
# Current state
git log --oneline -5
git status

# Open issues (roadmap)
gh issue list --repo jsboige/open-webui --state open --json number,title,labels,body --limit 20
```

### Phase 2: Dependency Resolution

**Issue dependency graph:**
```
#1 (packages DS) ──┬── #2 (ACL) ──┬── #4 (per-school images)
                   │               ├── #5 (per-tenant isolation)
                   │               └── #6 (TP guidés)
                   └── #3 (sk-agent + terminal)
```

**Rules:**
- An issue is "ready" if all its dependencies are closed
- Pick the lowest-numbered ready issue
- If multiple are ready, prefer the one with highest impact (P1 > P2 > P3)

**Dependency map (issue# → depends on):**
```
1 → []
2 → [1]
3 → [1]
4 → [1, 2]
5 → [2]
6 → [1, 2]
```

### Phase 3: Task Planning

**For each issue, before implementing:**

1. Read the full issue body (`gh issue view <N> --repo jsboige/open-webui`)
2. Check if any preparatory work was already done (grep MEMORY.md, check files)
3. If the task is complex (multi-file, architectural decision needed): **enter plan mode**
4. If the task is straightforward: proceed directly

**Always create a TodoWrite list** tracking sub-steps of the current issue.

### Phase 4: Implementation

**General patterns by issue type:**

**#1 - Dockerfile custom (data science packages):**
- Create `dockerfiles/open-terminal-ds/Dockerfile`
- Build locally, test imports
- Update docker-compose-myia.yaml
- Redeploy and verify

**#2 - ACL configuration:**
- Study `access_grants` format in OWUI source
- List existing groups per tenant
- Configure via API
- Update configure-tenant.py if needed

**#3 - sk-agent + Terminal:**
- Test terminal_id + tool_ids simultaneously
- Document findings
- Implement integration if needed

**#4-#6 - Larger features:**
- Enter plan mode
- Design architecture
- Implement incrementally
- Test on myia first, then deploy to tenants

### Phase 5: Completion

After implementing:

1. **Test** the change (API, UI if applicable)
2. **Commit** with conventional commit message referencing the issue: `feat(terminal): ... (closes #N)`
3. **Push** to origin/dev
4. **Close the issue** via `gh issue close <N> --repo jsboige/open-webui --comment "Implemented in <commit>"`
5. **Update MEMORY.md** with new state
6. **Report** to user: what was done, what's next

---

## Tools Used

- **Read/Edit**: Memory files, Dockerfiles, docker-compose, scripts
- **Bash**: Docker build/deploy, git, gh CLI, API calls (curl)
- **Grep/Glob**: Code exploration for OWUI internals
- **Agent**: Complex research (OWUI source code, access_control patterns)
- **Write**: New Dockerfiles, configs
- **TodoWrite**: Track sub-tasks

---

## Context Requirements

- Must be in the `d:\Open-WebUI\myia-open-webui` workspace
- GitHub CLI (`gh`) authenticated with access to jsboige/open-webui
- Docker available for building/deploying
- `.env` file with tenant credentials at repo root

---

## Notes

- **Duration**: Varies (15 min for config tasks, 1h+ for Dockerfiles)
- **Incremental**: Each invocation handles ONE issue, not the full roadmap
- **Safe**: Always tests on myia tenant first before deploying to others
- **Resumable**: If interrupted, the next invocation picks up from the same point
