from fastapi import APIRouter, HTTPException, Query
from typing import List, Optional
from schemas import RecommendationCreate, RecommendationResponse
from database import get_db_pool
import json

recommendations_router = APIRouter(prefix="/recommendations", tags=["recommendations"])


@recommendations_router.post("/", response_model=RecommendationResponse, status_code=201)
async def create_recommendation(rec: RecommendationCreate):
    pool = await get_db_pool()
    try:
        async with pool.acquire() as conn:
            async with conn.transaction():
                row = await conn.fetchrow(
                    """
                    WITH ins AS (
                        INSERT INTO recommendations (run_id, paper_id, score, rank, summary)
                        VALUES ($1, $2, $3, $4, $5)
                        ON CONFLICT (run_id, paper_id) DO UPDATE
                            SET score = EXCLUDED.score,
                                rank = EXCLUDED.rank,
                                summary = EXCLUDED.summary
                        RETURNING id, run_id, paper_id, score, rank, summary, created_at
                    )
                    INSERT INTO profile_recommendations (profile_id, recommendation_id)
                    SELECT rr.profile_id, ins.id
                    FROM recommendation_runs rr, ins
                    WHERE rr.id = $1
                    ON CONFLICT DO NOTHING
                    RETURNING (SELECT id FROM ins), (SELECT run_id FROM ins),
                              (SELECT paper_id FROM ins), (SELECT score FROM ins),
                              (SELECT rank FROM ins), (SELECT summary FROM ins),
                              (SELECT created_at FROM ins)
                    """,
                    rec.run_id, rec.paper_id, rec.score, rec.rank, rec.summary
                )
                if not row:
                    # profile_recommendations already existed (ON CONFLICT DO NOTHING
                    # returned nothing) — fetch the upserted recommendation directly
                    row = await conn.fetchrow(
                        """SELECT id, run_id, paper_id, score, rank, summary, created_at
                           FROM recommendations WHERE run_id = $1 AND paper_id = $2""",
                        rec.run_id, rec.paper_id
                    )
                if not row:
                    raise HTTPException(status_code=400, detail="Insert failed — profile_id may be missing on run")
                return dict(row)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@recommendations_router.get("/", response_model=List[RecommendationResponse])
async def get_recommendations(run_id: Optional[int] = Query(None)):
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        if run_id is not None:
            rows = await conn.fetch(
                "SELECT id, run_id, paper_id, score, rank, summary, created_at FROM recommendations WHERE run_id = $1 ORDER BY rank",
                run_id
            )
        else:
            rows = await conn.fetch(
                "SELECT id, run_id, paper_id, score, rank, summary, created_at FROM recommendations ORDER BY created_at DESC"
            )
        return [dict(row) for row in rows]


@recommendations_router.get("/run/{run_id}/with-papers")
async def get_recommendations_with_papers(run_id: int, limit: int = Query(50, ge=1, le=100)):
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT 
                r.id, r.run_id, r.paper_id, r.score, r.rank, r.summary, r.created_at,
                p.arxiv_id, p.title, p.abstract, p.metadata, p.source, p.submitted_date,
                s.summary_text
            FROM recommendations r
            JOIN papers p ON r.paper_id = p.id
            LEFT JOIN summaries s ON s.paper_id = p.id
            WHERE r.run_id = $1
            ORDER BY r.rank
            LIMIT $2
            """,
            run_id, limit
        )
        results = []
        for row in rows:
            result = dict(row)
            if result.get('metadata'):
                try:
                    result['metadata'] = json.loads(result['metadata'])
                except:
                    pass
            results.append(result)
        return results


@recommendations_router.get("/profile/{profile_id}")
async def get_recommendations_by_profile(profile_id: int, limit: int = Query(5000)):
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        profile = await conn.fetchrow(
            "SELECT user_id, top_x FROM profiles WHERE id = $1",
            profile_id
        )
        if not profile:
            return []

        user_id = profile['user_id']
        corpus_name = f"user_{user_id}_profile_{profile_id}"
        corpus = await conn.fetchrow(
            "SELECT id FROM corpora WHERE user_id = $1 AND name = $2",
            user_id, corpus_name
        )
        if not corpus:
            return []

        user_corpus_id = corpus['id']
        rows = await conn.fetch(
            """
            SELECT DISTINCT ON (p.arxiv_id)
                r.id, r.run_id, r.paper_id, r.score, r.rank, r.created_at,
                p.arxiv_id, p.title, p.abstract, p.metadata, p.submitted_date,
                s.summary_text,
                rr.total_papers_fetched
            FROM recommendations r
            JOIN recommendation_runs rr ON r.run_id = rr.id
            JOIN papers p ON r.paper_id = p.id
            LEFT JOIN summaries s ON s.paper_id = p.id AND s.mode = 'abstract'
            WHERE rr.user_corpus_id = $1
            ORDER BY p.arxiv_id, r.score DESC, p.submitted_date DESC
            LIMIT $2
            """,
            user_corpus_id, limit
        )
        results = []
        for row in rows:
            result = dict(row)
            if result.get('metadata'):
                try:
                    result['metadata'] = json.loads(result['metadata'])
                except:
                    pass
            results.append(result)
        return results


@recommendations_router.get("/{rec_id}", response_model=RecommendationResponse)
async def get_recommendation(rec_id: int):
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT id, run_id, paper_id, score, rank, summary, created_at FROM recommendations WHERE id = $1",
            rec_id
        )
        if not row:
            raise HTTPException(status_code=404, detail="Recommendation not found")
        return dict(row)


@recommendations_router.delete("/{rec_id}", status_code=204)
async def delete_recommendation(rec_id: int):
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        result = await conn.execute("DELETE FROM recommendations WHERE id = $1", rec_id)
        if result == "DELETE 0":
            raise HTTPException(status_code=404, detail="Recommendation not found")