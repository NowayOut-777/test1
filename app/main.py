from __future__ import annotations

from datetime import datetime, timezone
from typing import Dict, Any
from uuid import uuid4

from fastapi import FastAPI, Header, HTTPException, UploadFile, File, Form
from pydantic import BaseModel, EmailStr


app = FastAPI(title="HR Copilot API", version="hotfix-1")

API_KEYS = {"hr-dev-key", "admin-dev-key", "interviewer-dev-key"}

candidates: Dict[str, Dict[str, Any]] = {}
resumes: Dict[str, Dict[str, Any]] = {}
question_sets: Dict[str, Dict[str, Any]] = {}


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def require_api_key(x_api_key: str | None):
    if not x_api_key or x_api_key not in API_KEYS:
        raise HTTPException(status_code=401, detail="Invalid API key")


class CandidateCreateRequest(BaseModel):
    full_name: str
    email: EmailStr
    target_role: str


class GenerateQuestionsRequest(BaseModel):
    candidate_id: str
    resume_id: str


@app.get("/healthz")
def healthz():
    return {"status": "ok"}


@app.post("/v1/candidates")
def create_candidate(payload: CandidateCreateRequest, x_api_key: str | None = Header(default=None)):
    require_api_key(x_api_key)
    candidate_id = f"cand_{uuid4().hex[:10]}"
    created_at = now_iso()
    candidates[candidate_id] = {
        "candidate_id": candidate_id,
        "full_name": payload.full_name,
        "email": payload.email,
        "target_role": payload.target_role,
        "created_at": created_at,
    }
    return {"candidate_id": candidate_id, "created_at": created_at}


@app.get("/v1/candidates/{candidate_id}/progress")
def get_progress(candidate_id: str, x_api_key: str | None = Header(default=None)):
    require_api_key(x_api_key)
    if candidate_id not in candidates:
        raise HTTPException(status_code=404, detail="Candidate not found")

    candidate_has_resume = any(r["candidate_id"] == candidate_id for r in resumes.values())
    candidate_has_qset = any(q["candidate_id"] == candidate_id for q in question_sets.values())

    steps = [
        {"step": "candidate_created", "completed": True},
        {"step": "resume_uploaded", "completed": candidate_has_resume},
        {"step": "resume_parsed", "completed": any(r.get("parsed_text") for r in resumes.values() if r["candidate_id"] == candidate_id)},
        {"step": "questions_generated", "completed": candidate_has_qset},
    ]
    completed = sum(1 for s in steps if s["completed"])
    return {
        "candidate_id": candidate_id,
        "completed_steps": completed,
        "total_steps": len(steps),
        "steps": steps,
        "last_event_at": now_iso(),
    }


@app.post("/v1/resumes/upload")
async def upload_resume(
    candidate_id: str = Form(...),
    file: UploadFile = File(...),
    x_api_key: str | None = Header(default=None),
):
    require_api_key(x_api_key)

    if candidate_id not in candidates:
        raise HTTPException(status_code=404, detail="Candidate not found")

    content = await file.read()
    resume_id = f"res_{uuid4().hex[:10]}"
    resumes[resume_id] = {
        "resume_id": resume_id,
        "candidate_id": candidate_id,
        "filename": file.filename,
        "content": content,
        "created_at": now_iso(),
        "parsed_text": None,
    }
    return {"resume_id": resume_id, "candidate_id": candidate_id, "filename": file.filename}


@app.post("/v1/resumes/{resume_id}/parse")
def parse_resume(resume_id: str, x_api_key: str | None = Header(default=None)):
    require_api_key(x_api_key)

    resume = resumes.get(resume_id)
    if not resume:
        raise HTTPException(status_code=404, detail="Resume not found")

    text = resume["content"].decode("utf-8", errors="ignore")
    resume["parsed_text"] = text
    return {
        "resume_id": resume_id,
        "candidate_id": resume["candidate_id"],
        "text_preview": text[:500],
        "text_length": len(text),
    }


@app.post("/v1/questions/generate")
def generate_questions(payload: GenerateQuestionsRequest, x_api_key: str | None = Header(default=None)):
    require_api_key(x_api_key)

    if payload.candidate_id not in candidates:
        raise HTTPException(status_code=404, detail="Candidate not found")

    resume = resumes.get(payload.resume_id)
    if not resume or resume["candidate_id"] != payload.candidate_id:
        raise HTTPException(status_code=404, detail="Resume not found")

    parsed = resume.get("parsed_text") or ""
    role = candidates[payload.candidate_id]["target_role"]

    questions = [
        {
            "type": "STAR",
            "question": f"{role} 역할에서 가장 임팩트 있었던 프로젝트를 STAR 방식으로 설명해 주세요.",
            "intent": "성과/기여도 검증",
            "evidence": parsed[:120],
            "difficulty": "medium",
        },
        {
            "type": "TECH",
            "question": f"{role} 업무에서 장애를 해결했던 경험을 구체적으로 설명해 주세요.",
            "intent": "문제해결 역량 검증",
            "evidence": parsed[:120],
            "difficulty": "medium",
        },
        {
            "type": "DOMAIN",
            "question": f"{role} 직무에서 가장 중요한 지표 2개와 개선 방법을 말해 주세요.",
            "intent": "직무 전문성 검증",
            "evidence": parsed[:120],
            "difficulty": "easy",
        },
    ]

    qset_id = f"qset_{uuid4().hex[:10]}"
    question_sets[qset_id] = {
        "question_set_id": qset_id,
        "candidate_id": payload.candidate_id,
        "resume_id": payload.resume_id,
        "questions": questions,
        "created_at": now_iso(),
    }

    return question_sets[qset_id]
