from fastapi import APIRouter, HTTPException
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel
from typing import Optional
from datetime import date, datetime
from database import get_db_pool
from services.email_service import send_recommendations_digest, send_email

router = APIRouter(prefix="/emails", tags=["emails"])


class DigestRequest(BaseModel):
    user_id: int
    profile_id: int
    run_date: Optional[str] = None


@router.post("/send-digest")
async def send_digest(req: DigestRequest):
    pool = await get_db_pool()
    run_date = req.run_date or str(date.today())

    async with pool.acquire() as conn:
        user = await conn.fetchrow(
            "SELECT id, email, name FROM users WHERE id = $1", req.user_id
        )
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        profile = await conn.fetchrow(
            "SELECT id, name, email_notify, top_x, frequency FROM profiles WHERE id = $1 AND user_id = $2",
            req.profile_id, req.user_id
        )
        if not profile:
            raise HTTPException(status_code=404, detail="Profile not found")

        if not profile["email_notify"]:
            return {"status": "skipped", "reason": "email_notify is disabled for this profile"}

        top_x = profile["top_x"] or 10

        # Fetch all unsent recommendations for this profile
        rows = await conn.fetch(
            """
            SELECT r.id AS recommendation_id,
                   p.arxiv_id, p.title, p.abstract,
                   r.score, r.summary, s.summary_text
            FROM recommendations r
            JOIN recommendation_runs rr ON rr.id = r.run_id
            JOIN papers p ON p.id = r.paper_id
            LEFT JOIN summaries s ON s.paper_id = p.id AND s.mode = 'abstract'
            WHERE rr.profile_id = $1
              AND r.sent_in_email = false
            ORDER BY r.score DESC
            LIMIT $2
            """,
            req.profile_id, top_x
        )

        if not rows:
            return {"status": "skipped", "reason": "no unsent recommendations found"}

        # Collect recommendation IDs for marking as sent
        rec_ids = [row["recommendation_id"] for row in rows]
        papers = [dict(r) for r in rows]

    frequency = profile["frequency"] or "daily"

    success, subject, html_body = await run_in_threadpool(
        send_recommendations_digest,
        to_address=user["email"],
        profile_name=profile["name"],
        papers=papers,
        run_date=run_date,
        frequency=frequency,
    )

    status = "sent" if success else "failed"

    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO email_logs (user_id, profile_id, subject, body, status)
            VALUES ($1, $2, $3, $4, $5)
            """,
            req.user_id, req.profile_id, subject, html_body, status
        )

        # Only mark recommendations as sent if the email actually succeeded
        if success:
            await conn.execute(
                "UPDATE recommendations SET sent_in_email = true WHERE id = ANY($1)",
                rec_ids,
            )

    if not success:
        raise HTTPException(status_code=500, detail="Email sending failed")

    return {"status": "sent", "to": user["email"], "papers_count": len(papers)}


@router.post("/test-email")
async def test_email(to_email: str):
    success = await run_in_threadpool(
        send_email,
        to_address=to_email,
        subject="Preprint Bot — Test Email",
        html_body="<p>If you received this, your SMTP relay is configured correctly.</p>"
    )
    if not success:
        raise HTTPException(status_code=500, detail="Test email failed")
    return {"status": "sent", "to": to_email}
