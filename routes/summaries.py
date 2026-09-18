from fastapi import APIRouter, HTTPException
from typing import List
from schemas import SummaryCreate, SummaryUpdate, SummaryResponse
from database import get_db_pool

router = APIRouter(prefix="/summaries", tags=["summaries"])


@router.post("/", response_model=SummaryResponse, status_code=201)
async def create_summary(summary: SummaryCreate):
    pool = await get_db_pool()
    try:
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                INSERT INTO summaries (paper_id, mode, summary_text, summarizer)
                VALUES ($1, $2, $3, $4)
                ON CONFLICT (paper_id, mode) DO UPDATE 
                SET summary_text = EXCLUDED.summary_text, summarizer = EXCLUDED.summarizer
                RETURNING id, paper_id, mode, summary_text, summarizer, created_at
                """,
                summary.paper_id,
                summary.mode.value,
                summary.summary_text,
                summary.summarizer,
            )
            return dict(row)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/", response_model=List[SummaryResponse])
async def get_summaries():
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch("SELECT id, paper_id, mode, summary_text, summarizer, created_at FROM summaries")
        return [dict(row) for row in rows]


@router.get("/{summary_id}", response_model=SummaryResponse)
async def get_summary(summary_id: int):
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT id, paper_id, mode, summary_text, summarizer, created_at FROM summaries WHERE id = $1", summary_id
        )
        if not row:
            raise HTTPException(status_code=404, detail="Summary not found")
        return dict(row)


@router.get("/paper/{paper_id}", response_model=List[SummaryResponse])
async def get_summaries_by_paper(paper_id: int):
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT id, paper_id, mode, summary_text, summarizer, created_at FROM summaries WHERE paper_id = $1",
            paper_id,
        )
        return [dict(row) for row in rows]


@router.put("/{summary_id}", response_model=SummaryResponse)
async def update_summary(summary_id: int, summary: SummaryUpdate):
    pool = await get_db_pool()
    updates = []
    values = []
    idx = 1

    if summary.summary_text is not None:
        updates.append(f"summary_text = ${idx}")
        values.append(summary.summary_text)
        idx += 1
    if summary.summarizer is not None:
        updates.append(f"summarizer = ${idx}")
        values.append(summary.summarizer)
        idx += 1

    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")

    values.append(summary_id)
    query = f"UPDATE summaries SET {', '.join(updates)} WHERE id = ${idx} RETURNING id, paper_id, mode, summary_text, summarizer, created_at"

    async with pool.acquire() as conn:
        row = await conn.fetchrow(query, *values)
        if not row:
            raise HTTPException(status_code=404, detail="Summary not found")
        return dict(row)


@router.delete("/{summary_id}", status_code=204)
async def delete_summary(summary_id: int):
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        result = await conn.execute("DELETE FROM summaries WHERE id = $1", summary_id)
        if result == "DELETE 0":
            raise HTTPException(status_code=404, detail="Summary not found")
