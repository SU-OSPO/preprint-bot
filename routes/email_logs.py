from fastapi import APIRouter, HTTPException
from typing import List
from schemas import EmailLogCreate, EmailLogResponse
from database import get_db_pool

router = APIRouter(prefix="/email-logs", tags=["email-logs"])


@router.post("/", response_model=EmailLogResponse, status_code=201)
async def create_email_log(log: EmailLogCreate):
    pool = await get_db_pool()
    try:
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                INSERT INTO email_logs (user_id, profile_id, subject, body, status)
                VALUES ($1, $2, $3, $4, $5)
                RETURNING id, user_id, profile_id, subject, body, sent_at, status
                """,
                log.user_id,
                log.profile_id,
                log.subject,
                log.body,
                log.status.value,
            )
            return dict(row)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/", response_model=List[EmailLogResponse])
async def get_email_logs():
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch("SELECT id, user_id, profile_id, subject, body, sent_at, status FROM email_logs")
        return [dict(row) for row in rows]


@router.get("/{log_id}", response_model=EmailLogResponse)
async def get_email_log(log_id: int):
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT id, user_id, profile_id, subject, body, sent_at, status FROM email_logs WHERE id = $1", log_id
        )
        if not row:
            raise HTTPException(status_code=404, detail="Email log not found")
        return dict(row)


@router.get("/user/{user_id}", response_model=List[EmailLogResponse])
async def get_email_logs_by_user(user_id: int):
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT id, user_id, profile_id, subject, body, sent_at, status FROM email_logs WHERE user_id = $1 ORDER BY sent_at DESC",
            user_id,
        )
        return [dict(row) for row in rows]


@router.delete("/{log_id}", status_code=204)
async def delete_email_log(log_id: int):
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        result = await conn.execute("DELETE FROM email_logs WHERE id = $1", log_id)
        if result == "DELETE 0":
            raise HTTPException(status_code=404, detail="Email log not found")
