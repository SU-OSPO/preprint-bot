from fastapi import APIRouter, HTTPException
from typing import List
from schemas import ProcessingRunCreate, ProcessingRunUpdate, ProcessingRunResponse
from database import get_db_pool

router = APIRouter(prefix="/processing-runs", tags=["processing-runs"])

# started_at is Django auto_now_add (no DB default), so it is set explicitly.
_COLS = ("id, run_type, category, status, papers_processed, "
         "error_message, started_at, completed_at")


@router.post("/", response_model=ProcessingRunResponse, status_code=201)
async def create_processing_run(run: ProcessingRunCreate):
    pool = await get_db_pool()
    try:
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                f"""
                INSERT INTO processing_runs
                    (run_type, category, status, papers_processed, started_at)
                VALUES ($1, $2, $3, $4, NOW())
                RETURNING {_COLS}
                """,
                run.run_type, run.category, run.status, run.papers_processed,
            )
            return dict(row)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.patch("/{run_id}", response_model=ProcessingRunResponse)
async def update_processing_run(run_id: int, update: ProcessingRunUpdate):
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            f"""
            UPDATE processing_runs
            SET status = COALESCE($2, status),
                papers_processed = COALESCE($3, papers_processed),
                error_message = COALESCE($4, error_message),
                completed_at = CASE
                    WHEN $2 IN ('completed', 'failed') THEN NOW()
                    ELSE completed_at
                END
            WHERE id = $1
            RETURNING {_COLS}
            """,
            run_id, update.status, update.papers_processed, update.error_message,
        )
        if not row:
            raise HTTPException(status_code=404, detail="Processing run not found")
        return dict(row)


@router.get("/", response_model=List[ProcessingRunResponse])
async def get_processing_runs():
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            f"SELECT {_COLS} FROM processing_runs ORDER BY started_at DESC"
        )
        return [dict(row) for row in rows]
