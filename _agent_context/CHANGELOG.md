# Changelog
> Agents: append a new entry here after EVERY completed change. Newest first.

---

## Format
```
### [YYYY-MM-DD] Short title
- **Files changed:** list them
- **What changed:** 1-2 lines
- **Why:** reason / user request
- **Proposal ref:** (link to approved CHANGE_PROPOSAL or "user verbal approval")
```

---

<!-- ENTRIES GO BELOW THIS LINE -->

### [2026-10-13] Phase 3 — Team Management, Magic Join Links & Substep Assignments
- **Files changed:** `main.py`, `c:\Users\ACER\Downloads\index.html`, `migration_phase3_team.sql`, `_agent_context/` docs
- **What changed:**
  - **Backend:** Added endpoints for generating and listing org/project invites (`POST /orgs/{id}/invites`, `GET /invites/{code}`), accepting magic join links (`POST /invites/{code}/accept`), direct adding by email (`POST /orgs/{id}/members/add-by-email`), updating member roles, removing members, dynamic step & substep creation/deletion, and substep assignment.
  - **Database:** Added `migration_phase3_team.sql` with `invites`, `project_collaborators`, `substep_id` on `project_assignees`, and member identification fields.
  - **Frontend:** Added "Team & Invites" view with shareable invite link generator, direct email adder, member role controls, and active workload counts. Added "Manage Tasks & Assignments" modal on project cards with granular step and sub-step assignment dropdowns, plus a "🎯 My Tasks Only" project filter.
- **Why:** User requested real member / consultant invite links, in-app identification, and fine-grained task assignment down to sub-steps.
- **Proposal ref:** Approved by user (2026-10-13 session)


### [2026-10-13] Full rebuild — YouTube phase workflow + UI overhaul
- **Files changed:** `c:\Users\ACER\Downloads\index.html` (full rewrite ~700 lines), `main.py` (5 additions), `migration_phase2.sql` (new), `_agent_context/` docs updated
- **What changed:**
  - **Frontend:** Complete rewrite of index.html. New dark UI (Inter + Fraunces, #0F1117 bg). 5-phase project board with progress bar per card. YouTube-specific pitch form (video type, audience, requirements, start/end dates). Toast notifications replace all alert(). Projects cached in `window._projectsCache`. Calendar with prev/next navigation. AXEL chat with typing indicator. Settings with timezone/schedule fields.
  - **Backend:** Added `current_phase`, `video_type`, `target_audience`, `requirements` fields to `ConvertPitch` model and project insert. New `POST /projects/{id}/advance-phase` endpoint (increments phase 1→5). New `GET /projects/{id}` endpoint with full step+substep detail. `list_projects` now returns `current_phase`.
  - **DB Migration:** `migration_phase2.sql` — adds new columns to `projects`, `idea_pitches`, `org_members`.
- **Why:** User requested YouTube team workflow with 5 phases, UI overhaul, performance improvements
- **Proposal ref:** User explicit request (2026-10-13 session)

### [2026-10-13] Created _agent_context/ documentation folder
- **Files changed:** `_agent_context/OVERVIEW.md`, `_agent_context/DB_SCHEMA.md`, `_agent_context/CHANGELOG.md`, `_agent_context/CHANGE_PROPOSAL.md`
- **What changed:** Added agent context folder for efficient AI-assisted development
- **Why:** User requested an AI-readable project reference to minimize token usage and require change proposals before editing workflow/functionality
- **Proposal ref:** User explicit request
