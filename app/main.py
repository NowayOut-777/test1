import os
import sqlite3
from datetime import datetime, timezone
from uuid import uuid4

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, EmailStr, Field

app = FastAPI(title="HR-Centric AI Interview Copilot", version="0.1.0-minimal")


class CandidateCreateRequest(BaseModel):
    full_name: str = Field(min_length=1, max_length=100)
    email: EmailStr
    target_role: str = Field(min_length=1, max_length=100)


def db_path() -> str:
    return os.getenv("APP_DB_PATH", "./data/app.db")


def init_db() -> None:
    os.makedirs(os.path.dirname(db_path()), exist_ok=True)
    with sqlite3.connect(db_path()) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS candidates (
                candidate_id TEXT PRIMARY KEY,
                full_name TEXT NOT NULL,
                email TEXT NOT NULL,
                target_role TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )


@app.on_event("startup")
def startup() -> None:
    init_db()


@app.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/v1/candidates")
def create_candidate(payload: CandidateCreateRequest) -> dict[str, str]:
    candidate_id = f"cand_{uuid4().hex[:12]}"
    created_at = datetime.now(timezone.utc).isoformat()

    with sqlite3.connect(db_path()) as conn:
        conn.execute(
            "INSERT INTO candidates(candidate_id, full_name, email, target_role, created_at) VALUES (?, ?, ?, ?, ?)",
            (candidate_id, payload.full_name, payload.email, payload.target_role, created_at),
        )

    return {"candidate_id": candidate_id, "created_at": created_at}


@app.get("/v1/candidates/{candidate_id}/progress")
def get_progress(candidate_id: str) -> dict:
    with sqlite3.connect(db_path()) as conn:
        row = conn.execute(
            "SELECT candidate_id, created_at FROM candidates WHERE candidate_id = ?",
            (candidate_id,),
        ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Candidate not found")

    return {
        "candidate_id": row[0],
        "completed_steps": 1,
        "total_steps": 7,
        "steps": [{"step": "candidate_created", "completed": True}],
        "last_event_at": row[1],
    }


@app.get("/v1/ops/metrics")
def metrics() -> dict:
    return {"metrics": {"service.up": 1}}
