from fastapi import APIRouter, HTTPException
from typing import List
from schemas import ProfileRecommendationCreate, ProfileRecommendationResponse
from database import get_db_pool

router = APIRouter(prefix="/profile-recommendations", tags=["profile-recommendations"])


@router.post("/", response_model=ProfileRecommendationResponse, status_code=201)
async def create_profile_recommendation(pr: ProfileRecommendationCreate):
    pool = await get_db_pool()
    try:
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                INSERT INTO profile_recommendations (profile_id, recommendation_id)
                VALUES ($1, $2)
                RETURNING id, profile_id, recommendation_id, created_at
                """,
                pr.profile_id,
                pr.recommendation_id,
            )
            return dict(row)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/", response_model=List[ProfileRecommendationResponse])
async def get_profile_recommendations():
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch("SELECT id, profile_id, recommendation_id, created_at FROM profile_recommendations")
        return [dict(row) for row in rows]


@router.get("/{pr_id}", response_model=ProfileRecommendationResponse)
async def get_profile_recommendation(pr_id: int):
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT id, profile_id, recommendation_id, created_at FROM profile_recommendations WHERE id = $1", pr_id
        )
        if not row:
            raise HTTPException(status_code=404, detail="Profile recommendation not found")
        return dict(row)


@router.get("/profile/{profile_id}", response_model=List[ProfileRecommendationResponse])
async def get_profile_recommendations_by_profile(profile_id: int):
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT id, profile_id, recommendation_id, created_at FROM profile_recommendations WHERE profile_id = $1",
            profile_id,
        )
        return [dict(row) for row in rows]


@router.delete("/{pr_id}", status_code=204)
async def delete_profile_recommendation(pr_id: int):
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        result = await conn.execute("DELETE FROM profile_recommendations WHERE id = $1", pr_id)
        if result == "DELETE 0":
            raise HTTPException(status_code=404, detail="Profile recommendation not found")
