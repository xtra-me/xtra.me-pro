import os
import uuid
from datetime import date, datetime
from typing import Optional, List

from fastapi import FastAPI, HTTPException, Depends, Header
from pydantic import BaseModel
from supabase import create_client, Client
from groq import Groq

app = FastAPI(title="Team Project App API")

from fastapi.middleware.cors import CORSMiddleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Supports live Cloudflare Worker, localhost, etc.
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_SERVICE_KEY = os.environ["SUPABASE_SERVICE_KEY"]
sb: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)

API_KEY = os.environ.get("BACKEND_API_KEY", "change-me")


def check_key(x_api_key: str = Header(...)):
    if x_api_key != API_KEY:
        raise HTTPException(401, "Invalid API key")


def get_user_info(authorization: str = Header(...)) -> dict:
    # Expects: "Bearer <supabase_jwt>"
    token = authorization.replace("Bearer ", "")
    user = sb.auth.get_user(token)
    if not user or not user.user:
        raise HTTPException(401, "Invalid session")
    return {"id": user.user.id, "email": user.user.email}


def get_user_id(authorization: str = Header(...)) -> str:
    return get_user_info(authorization)["id"]


# ---------- ORGS & MEMBERS ----------

class CreateOrg(BaseModel):
    name: str


@app.post("/orgs", dependencies=[Depends(check_key)])
def create_org(body: CreateOrg, user_info: dict = Depends(get_user_info)):
    user_id = user_info["id"]
    user_email = user_info["email"]
    org = sb.table("orgs").insert({"name": body.name, "owner_id": user_id}).execute()
    org_id = org.data[0]["id"]
    sb.table("org_members").insert({
        "org_id": org_id, "user_id": user_id, "role": "owner", "user_email": user_email
    }).execute()
    return org.data[0]


@app.get("/orgs/{org_id}/members", dependencies=[Depends(check_key)])
def list_members(org_id: str, user_id: str = Depends(get_user_id)):
    res = sb.table("org_members").select("*").eq("org_id", org_id).execute()
    return res.data


class CreateInvite(BaseModel):
    role: str = "member"
    project_id: Optional[str] = None
    type: str = "org"  # "org" or "project"


@app.post("/orgs/{org_id}/invites", dependencies=[Depends(check_key)])
def create_invite(org_id: str, body: CreateInvite, user_id: str = Depends(get_user_id)):
    code = uuid.uuid4().hex[:8]
    res = sb.table("invites").insert({
        "code": code,
        "org_id": org_id,
        "project_id": body.project_id,
        "role": body.role,
        "type": body.type,
        "created_by": user_id,
        "is_active": True
    }).execute()
    return res.data[0]


@app.get("/orgs/{org_id}/invites", dependencies=[Depends(check_key)])
def list_invites(org_id: str, user_id: str = Depends(get_user_id)):
    return sb.table("invites").select("*").eq("org_id", org_id).eq("is_active", True).execute().data


@app.get("/invites/{code}")
def get_invite_info(code: str):
    inv = sb.table("invites").select("*, orgs(name), projects(title)").eq("code", code).eq("is_active", True).single().execute().data
    if not inv:
        raise HTTPException(404, "Invite code not found or expired")
    return inv


@app.post("/invites/{code}/accept", dependencies=[Depends(check_key)])
def accept_invite(code: str, user_info: dict = Depends(get_user_info)):
    inv = sb.table("invites").select("*").eq("code", code).eq("is_active", True).single().execute().data
    if not inv:
        raise HTTPException(404, "Invite code not found or expired")

    user_id = user_info["id"]
    user_email = user_info["email"]
    org_id = inv["org_id"]

    # Check if already in org_members
    existing = sb.table("org_members").select("*").eq("org_id", org_id).eq("user_id", user_id).execute().data
    if not existing:
        member = sb.table("org_members").insert({
            "org_id": org_id,
            "user_id": user_id,
            "role": inv["role"],
            "user_email": user_email
        }).execute().data[0]
    else:
        member = existing[0]

    # If project consultant invite:
    if inv.get("project_id"):
        try:
            sb.table("project_collaborators").insert({
                "project_id": inv["project_id"],
                "user_id": user_id,
                "user_email": user_email,
                "role": inv.get("role", "consultant")
            }).execute()
        except Exception:
            pass

    return {
        "status": "joined",
        "org_id": org_id,
        "member": member,
        "role": inv["role"],
        "project_id": inv.get("project_id")
    }


class AddMemberByEmail(BaseModel):
    email: str
    role: str = "member"
    project_id: Optional[str] = None


@app.post("/orgs/{org_id}/members/add-by-email", dependencies=[Depends(check_key)])
def add_member_by_email(org_id: str, body: AddMemberByEmail, user_id: str = Depends(get_user_id)):
    code = uuid.uuid4().hex[:8]
    inv = sb.table("invites").insert({
        "code": code,
        "org_id": org_id,
        "project_id": body.project_id,
        "role": body.role,
        "type": "project" if body.project_id else "org",
        "created_by": user_id,
        "is_active": True
    }).execute().data[0]
    return {"message": "Invite created for email", "code": code, "role": body.role, "invite": inv}


@app.patch("/orgs/{org_id}/members/{member_id}", dependencies=[Depends(check_key)])
def update_member_role(org_id: str, member_id: str, body: dict, user_id: str = Depends(get_user_id)):
    role = body.get("role")
    if not role:
        raise HTTPException(400, "Role is required")
    res = sb.table("org_members").update({"role": role}).eq("id", member_id).eq("org_id", org_id).execute()
    return res.data[0] if res.data else {"status": "updated"}


@app.delete("/orgs/{org_id}/members/{member_id}", dependencies=[Depends(check_key)])
def remove_member(org_id: str, member_id: str, user_id: str = Depends(get_user_id)):
    sb.table("org_members").delete().eq("id", member_id).eq("org_id", org_id).execute()
    return {"status": "removed"}


# ---------- IDEA PITCHES ----------

class CreatePitch(BaseModel):
    org_id: str
    title: str
    description: Optional[str] = None
    video_type: Optional[str] = None
    target_audience: Optional[str] = None
    requirements: Optional[str] = None
    target_start_date: Optional[date] = None
    target_end_date: Optional[date] = None


@app.post("/pitches", dependencies=[Depends(check_key)])
def create_pitch(body: CreatePitch, user_id: str = Depends(get_user_id)):
    res = sb.table("idea_pitches").insert({
        "org_id": body.org_id,
        "title": body.title,
        "description": body.description,
        "video_type": body.video_type,
        "target_audience": body.target_audience,
        "requirements": body.requirements,
        "target_start_date": str(body.target_start_date) if body.target_start_date else None,
        "target_end_date": str(body.target_end_date) if body.target_end_date else None,
        "created_by": user_id
    }).execute()
    return res.data[0]


class PitchMessage(BaseModel):
    content: str


@app.post("/pitches/{pitch_id}/messages", dependencies=[Depends(check_key)])
def post_pitch_message(pitch_id: str, body: PitchMessage, user_id: str = Depends(get_user_id)):
    res = sb.table("pitch_messages").insert({
        "pitch_id": pitch_id, "author_id": user_id, "content": body.content
    }).execute()
    return res.data[0]


class ConvertPitch(BaseModel):
    title: str
    description: Optional[str] = None
    extra_details: dict = {}
    color: str
    start_date: date
    due_date: date
    steps: List[dict] = []  # [{title, due_date, priority, substeps:[str,...]}]
    current_phase: int = 1
    video_type: Optional[str] = None
    target_audience: Optional[str] = None
    requirements: Optional[str] = None


@app.post("/pitches/{pitch_id}/convert", dependencies=[Depends(check_key)])
def convert_pitch(pitch_id: str, body: ConvertPitch, user_id: str = Depends(get_user_id)):
    pitch = sb.table("idea_pitches").select("*").eq("id", pitch_id).single().execute().data
    if not pitch:
        raise HTTPException(404, "Pitch not found")

    project = sb.table("projects").insert({
        "org_id": pitch["org_id"], "source_pitch_id": pitch_id,
        "title": body.title, "description": body.description,
        "extra_details": body.extra_details, "color": body.color,
        "start_date": str(body.start_date), "due_date": str(body.due_date),
        "created_by": user_id,
        "current_phase": body.current_phase,
        "video_type": body.video_type,
        "target_audience": body.target_audience,
        "requirements": body.requirements,
    }).execute().data[0]

    for i, step in enumerate(body.steps):
        step_row = sb.table("project_steps").insert({
            "project_id": project["id"], "title": step["title"],
            "order_index": i, "priority": step.get("priority", 0),
            "due_date": step.get("due_date"),
        }).execute().data[0]
        for j, sub in enumerate(step.get("substeps", [])):
            sb.table("project_substeps").insert({
                "step_id": step_row["id"], "title": sub, "order_index": j
            }).execute()

    sb.table("idea_pitches").update({
        "status": "archived", "archived_at": datetime.utcnow().isoformat()
    }).eq("id", pitch_id).execute()

    return project


# ---------- ASSIGNMENTS (STEPS & SUBSTEPS) ----------

class AssignMember(BaseModel):
    project_id: str
    org_member_id: str
    step_id: Optional[str] = None  # null = whole-project assignee
    substep_id: Optional[str] = None


@app.post("/assignments", dependencies=[Depends(check_key)])
def assign_member(body: AssignMember, user_id: str = Depends(get_user_id)):
    # Check if duplicate assignment exists
    query = sb.table("project_assignees").select("*").eq("project_id", body.project_id).eq("org_member_id", body.org_member_id)
    if body.step_id:
        query = query.eq("step_id", body.step_id)
    if body.substep_id:
        query = query.eq("substep_id", body.substep_id)
    existing = query.execute().data
    if existing:
        return existing[0]

    payload = {
        "project_id": body.project_id,
        "org_member_id": body.org_member_id,
        "step_id": body.step_id,
    }
    if body.substep_id:
        payload["substep_id"] = body.substep_id

    res = sb.table("project_assignees").insert(payload).execute()
    return res.data[0]


@app.delete("/assignments/{assignment_id}", dependencies=[Depends(check_key)])
def delete_assignment(assignment_id: str, user_id: str = Depends(get_user_id)):
    sb.table("project_assignees").delete().eq("id", assignment_id).execute()
    return {"status": "deleted"}


@app.get("/projects/{project_id}/assignees", dependencies=[Depends(check_key)])
def list_assignees(project_id: str, user_id: str = Depends(get_user_id)):
    return sb.table("project_assignees").select("*, org_members(id, user_id, user_email, role, display_name)").eq("project_id", project_id).execute().data


# ---------- PROJECTS / STEPS / SUBSTEPS ----------

@app.get("/orgs/{org_id}/projects", dependencies=[Depends(check_key)])
def list_projects(org_id: str, user_id: str = Depends(get_user_id)):
    return sb.table("projects").select("*, current_phase, project_steps(*, project_substeps(*)), project_assignees(*, org_members(id, user_email, role, display_name))").eq("org_id", org_id).execute().data


@app.get("/projects/{project_id}", dependencies=[Depends(check_key)])
def get_project(project_id: str, user_id: str = Depends(get_user_id)):
    return sb.table("projects").select("*, project_steps(*, project_substeps(*)), project_assignees(*, org_members(id, user_email, role, display_name))").eq("id", project_id).single().execute().data


class AdvancePhase(BaseModel):
    pass


@app.post("/projects/{project_id}/advance-phase", dependencies=[Depends(check_key)])
def advance_phase(project_id: str, user_id: str = Depends(get_user_id)):
    project = sb.table("projects").select("current_phase").eq("id", project_id).single().execute().data
    if not project:
        raise HTTPException(404, "Project not found")
    new_phase = min((project.get("current_phase") or 1) + 1, 5)
    res = sb.table("projects").update({"current_phase": new_phase}).eq("id", project_id).execute()
    return res.data[0]


class CreateStep(BaseModel):
    title: str
    priority: int = 0
    due_date: Optional[date] = None
    order_index: Optional[int] = 0


@app.post("/projects/{project_id}/steps", dependencies=[Depends(check_key)])
def add_step(project_id: str, body: CreateStep, user_id: str = Depends(get_user_id)):
    payload = {
        "project_id": project_id,
        "title": body.title,
        "priority": body.priority,
        "order_index": body.order_index or 0,
        "due_date": str(body.due_date) if body.due_date else None,
        "status": "pending"
    }
    res = sb.table("project_steps").insert(payload).execute()
    return res.data[0]


class UpdateStep(BaseModel):
    priority: Optional[int] = None
    status: Optional[str] = None
    due_date: Optional[date] = None


@app.patch("/steps/{step_id}", dependencies=[Depends(check_key)])
def update_step(step_id: str, body: UpdateStep, user_id: str = Depends(get_user_id)):
    updates = {k: v for k, v in body.dict().items() if v is not None}
    if "due_date" in updates:
        updates["due_date"] = str(updates["due_date"])
    res = sb.table("project_steps").update(updates).eq("id", step_id).execute()
    return res.data[0]


@app.delete("/steps/{step_id}", dependencies=[Depends(check_key)])
def delete_step(step_id: str, user_id: str = Depends(get_user_id)):
    sb.table("project_steps").delete().eq("id", step_id).execute()
    return {"status": "deleted"}


class CreateSubstep(BaseModel):
    title: str
    order_index: Optional[int] = 0


@app.post("/steps/{step_id}/substeps", dependencies=[Depends(check_key)])
def add_substep(step_id: str, body: CreateSubstep, user_id: str = Depends(get_user_id)):
    payload = {
        "step_id": step_id,
        "title": body.title,
        "order_index": body.order_index or 0,
        "is_checked": False
    }
    res = sb.table("project_substeps").insert(payload).execute()
    return res.data[0]


class ToggleSubstep(BaseModel):
    is_checked: bool


@app.patch("/substeps/{substep_id}", dependencies=[Depends(check_key)])
def toggle_substep(substep_id: str, body: ToggleSubstep, user_id: str = Depends(get_user_id)):
    res = sb.table("project_substeps").update({"is_checked": body.is_checked}).eq("id", substep_id).execute()
    return res.data[0]


@app.delete("/substeps/{substep_id}", dependencies=[Depends(check_key)])
def delete_substep(substep_id: str, user_id: str = Depends(get_user_id)):
    sb.table("project_substeps").delete().eq("id", substep_id).execute()
    return {"status": "deleted"}


# ---------- DELAY / REASSIGN ----------

class DelayReport(BaseModel):
    step_id: str
    reason: Optional[str] = None
    action_taken: str = "none"  # none | notified_members | reassigned
    reassigned_to: Optional[str] = None


@app.post("/delays", dependencies=[Depends(check_key)])
def report_delay(body: DelayReport, user_id: str = Depends(get_user_id)):
    res = sb.table("delay_reports").insert({
        "step_id": body.step_id, "reported_by": user_id,
        "reason": body.reason, "action_taken": body.action_taken,
        "reassigned_to": body.reassigned_to,
    }).execute()
    return res.data[0]


# ---------- AI CHAT + DAILY BRIEF ----------

class ChatMessage(BaseModel):
    org_member_id: str
    content: str
    groq_api_key: str


def get_member_context(org_member_id: str) -> str:
    member = sb.table("org_members").select("*").eq("id", org_member_id).single().execute().data
    org_id = member["org_id"]

    assignments = sb.table("project_assignees").select(
        "*, project_steps(title, due_date, priority, status), projects(title, color)"
    ).eq("org_member_id", org_member_id).execute().data
    overrides = sb.table("availability_overrides").select("*").eq(
        "org_member_id", org_member_id
    ).gte("end_date", str(date.today())).execute().data
    all_projects = sb.table("projects").select(
        "title, start_date, due_date, project_steps(title, due_date, priority, status)"
    ).eq("org_id", org_id).execute().data

    lines = [f"Work schedule: {member.get('work_schedule')}", f"Timezone: {member.get('timezone')}"]
    if overrides:
        lines.append("Unavailable periods: " + "; ".join(
            f"{o['start_date']} to {o['end_date']} ({o.get('reason','no reason given')})" for o in overrides
        ))

    lines.append("\nSteps assigned to this specific user (their priority focus):")
    if assignments:
        for a in assignments:
            step = a.get("project_steps")
            proj = a.get("projects")
            if step:
                lines.append(f"- [{proj['title']}] {step['title']} — due {step['due_date']}, "
                             f"priority {step['priority']}, status {step['status']}")
    else:
        lines.append("- None assigned yet.")

    lines.append("\nAll projects in the organization (for context/awareness, not necessarily this user's work):")
    for p in all_projects:
        lines.append(f"- {p['title']} ({p['start_date']} to {p['due_date']})")
        for s in p.get("project_steps", []):
            lines.append(f"    · {s['title']} — due {s['due_date']}, priority {s['priority']}, status {s['status']}")

    return "\n".join(lines)


SYSTEM_PROMPT = (
    "You are AXEL, a warm but efficient personal work assistant embedded in a team "
    "project planning app. You can see all projects in the user's organization for "
    "awareness, but you should prioritize planning around the steps specifically "
    "assigned to this individual user. Respect their stated free time and any "
    "temporary unavailability. Prioritize by due date and user-set priority. If the "
    "user says they can't finish something on time, ask whether they want you to "
    "notify other members or suggest reassignment — never do either without their "
    "confirmation. Keep responses concise and actionable."
)


@app.post("/chat", dependencies=[Depends(check_key)])
def chat(body: ChatMessage, user_id: str = Depends(get_user_id)):
    context = get_member_context(body.org_member_id)
    client = Groq(api_key=body.groq_api_key)

    sb.table("ai_messages").insert({
        "org_member_id": body.org_member_id, "role": "user",
        "content": body.content, "origin": "chat"
    }).execute()

    completion = client.chat.completions.create(
        model="openai/gpt-oss-20b",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT + "\n\nUser context:\n" + context},
            {"role": "user", "content": body.content},
        ],
    )
    reply = completion.choices[0].message.content

    sb.table("ai_messages").insert({
        "org_member_id": body.org_member_id, "role": "assistant",
        "content": reply, "origin": "chat"
    }).execute()

    return {"reply": reply}


class DailyBriefRequest(BaseModel):
    org_member_id: str
    groq_api_key: str


@app.post("/daily-brief", dependencies=[Depends(check_key)])
def daily_brief(body: DailyBriefRequest, user_id: str = Depends(get_user_id)):
    context = get_member_context(body.org_member_id)
    client = Groq(api_key=body.groq_api_key)

    completion = client.chat.completions.create(
        model="openai/gpt-oss-20b",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"Here is my context:\n{context}\n\n"
                                         f"Give me today's plan, prioritized by deadline and priority."},
        ],
    )
    brief = completion.choices[0].message.content

    sb.table("ai_messages").insert({
        "org_member_id": body.org_member_id, "role": "assistant",
        "content": brief, "origin": "system"
    }).execute()

    return {"brief": brief}


@app.get("/health")
def health():
    return {"status": "ok"}


# ---------- SCHEDULED JOB ENDPOINTS (call these from cron-job.org) ----------

@app.post("/jobs/morning-email", dependencies=[Depends(check_key)])
def job_morning_email():
    import email_job
    email_job.run("morning")
    return {"status": "sent"}


@app.post("/jobs/daytime-email", dependencies=[Depends(check_key)])
def job_daytime_email():
    import email_job
    email_job.run("daytime")
    return {"status": "sent"}