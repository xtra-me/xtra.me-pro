# Supabase DB Schema (Inferred from main.py + email_job.py)
> Update this file whenever you add/remove/rename columns or tables.

---

## Tables

### `orgs`
| Column | Type | Notes |
|---|---|---|
| id | uuid | PK |
| name | text | |
| owner_id | uuid | FK → auth.users |

### `org_members`
| Column | Type | Notes |
|---|---|---|
| id | uuid | PK |
| org_id | uuid | FK → orgs |
| user_id | uuid | FK → auth.users |
| role | text | e.g. "owner", "member" |
| work_schedule | text/json | Member's schedule |
| timezone | text | |
| groq_api_key | text | User's own Groq key (used for AI calls) |
| last_seen | timestamp | Updated by frontend on activity — used to skip email |

### `idea_pitches`
| Column | Type | Notes |
|---|---|---|
| id | uuid | PK |
| org_id | uuid | FK → orgs |
| title | text | |
| description | text | nullable |
| created_by | uuid | FK → auth.users |
| status | text | "open" → "archived" after conversion |
| archived_at | timestamp | Set on conversion |

### `pitch_messages`
| Column | Type | Notes |
|---|---|---|
| id | uuid | PK |
| pitch_id | uuid | FK → idea_pitches |
| author_id | uuid | FK → auth.users |
| content | text | |

### `projects`
| Column | Type | Notes |
|---|---|---|
| id | uuid | PK |
| org_id | uuid | FK → orgs |
| source_pitch_id | uuid | FK → idea_pitches |
| title | text | |
| description | text | |
| extra_details | jsonb | Flexible metadata |
| color | text | UI color tag |
| start_date | date | |
| due_date | date | |
| created_by | uuid | FK → auth.users |

### `project_steps`
| Column | Type | Notes |
|---|---|---|
| id | uuid | PK |
| project_id | uuid | FK → projects |
| title | text | |
| order_index | int | Display order |
| priority | int | 0 = normal, higher = more urgent |
| due_date | date | |
| status | text | e.g. "pending", "in_progress", "done" |

### `project_substeps`
| Column | Type | Notes |
|---|---|---|
| id | uuid | PK |
| step_id | uuid | FK → project_steps |
| title | text | |
| order_index | int | |
| is_checked | bool | Checkbox state |

### `project_assignees`
| Column | Type | Notes |
|---|---|---|
| id | uuid | PK |
| project_id | uuid | FK → projects |
| step_id | uuid | FK → project_steps (nullable = whole-project assignee) |
| org_member_id | uuid | FK → org_members |

### `delay_reports`
| Column | Type | Notes |
|---|---|---|
| id | uuid | PK |
| step_id | uuid | FK → project_steps |
| reported_by | uuid | FK → auth.users |
| reason | text | |
| action_taken | text | "none" \| "notified_members" \| "reassigned" |
| reassigned_to | uuid | nullable, FK → org_members |

### `availability_overrides`
| Column | Type | Notes |
|---|---|---|
| id | uuid | PK |
| org_member_id | uuid | FK → org_members |
| start_date | date | |
| end_date | date | |
| reason | text | |

### `ai_messages`
| Column | Type | Notes |
|---|---|---|
| id | uuid | PK |
| org_member_id | uuid | FK → org_members |
| role | text | "user" \| "assistant" |
| content | text | |
| origin | text | "chat" \| "system" \| "email" |
