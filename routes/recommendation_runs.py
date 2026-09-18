from fastapi import APIRouter, HTTPException
from typing import List
from schemas import RecommendationRunCreate, RecommendationRunResponse
from database import get_db_pool

router = APIRouter(prefix="/recommendation-runs", tags=["recommendation-runs"])


@router.post("/", response_model=RecommendationRunResponse, status_code=201)
async def create_recommendation_run(run: RecommendationRunCreate):
    pool = await get_db_pool()
    try:
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                INSERT INTO recommendation_runs (profile_id, user_id, user_corpus_id, ref_corpus_id, threshold, method, total_papers_fetched, target_date)
                VALUES ($1, $2, $3, $4, $5::float, $6, $7, $8)
                RETURNING id, profile_id, user_id, user_corpus_id, ref_corpus_id, threshold, method, total_papers_fetched, target_date, created_at
                """,
                run.profile_id,
                run.user_id,
                run.user_corpus_id,
                run.ref_corpus_id,
                run.threshold,
                run.method,
                run.total_papers_fetched,
                run.target_date,
            )
            return dict(row)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/", response_model=List[RecommendationRunResponse])
async def get_recommendation_runs():
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT id, profile_id, user_id, user_corpus_id, ref_corpus_id, threshold, method, total_papers_fetched, target_date, created_at FROM recommendation_runs"
        )
        return [dict(row) for row in rows]


@router.get("/{run_id}", response_model=RecommendationRunResponse)
async def get_recommendation_run(run_id: int):
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT id, profile_id, user_id, user_corpus_id, ref_corpus_id, threshold, method, total_papers_fetched, target_date, created_at FROM recommendation_runs WHERE id = $1",
            run_id,
        )
        if not row:
            raise HTTPException(status_code=404, detail="Recommendation run not found")
        return dict(row)


@router.delete("/{run_id}", status_code=204)
async def delete_recommendation_run(run_id: int):
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        result = await conn.execute("DELETE FROM recommendation_runs WHERE id = $1", run_id)
        if result == "DELETE 0":
            raise HTTPException(status_code=404, detail="Recommendation run not found")
