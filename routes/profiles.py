from fastapi import APIRouter, HTTPException
from typing import List
from schemas import ProfileCreate, ProfileUpdate, ProfileResponse
from database import get_db_pool
from datetime import datetime

router = APIRouter(prefix="/profiles", tags=["profiles"])


@router.post("/", response_model=ProfileResponse, status_code=201)
async def create_profile(profile: ProfileCreate):
    pool = await get_db_pool()
    try:
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                INSERT INTO profiles (user_id, name, keywords, categories, email_notify, frequency, threshold, top_x)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                RETURNING id, user_id, name, keywords, categories, email_notify, frequency, threshold, top_x, created_at, updated_at
                """,
                profile.user_id,
                profile.name,
                profile.keywords,
                profile.categories,
                profile.email_notify,
                profile.frequency.value,
                profile.threshold,
                profile.top_x,
            )
            return dict(row)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/", response_model=List[ProfileResponse])
async def get_profiles():
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT id, user_id, name, keywords, categories, email_notify, frequency, threshold, top_x, created_at, updated_at FROM profiles"
        )
        return [dict(row) for row in rows]


@router.get("/{profile_id}", response_model=ProfileResponse)
async def get_profile(profile_id: int):
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT id, user_id, name, keywords, categories, email_notify, frequency, threshold, top_x, created_at, updated_at FROM profiles WHERE id = $1",
            profile_id,
        )
        if not row:
            raise HTTPException(status_code=404, detail="Profile not found")
        return dict(row)


@router.put("/{profile_id}", response_model=ProfileResponse)
async def update_profile(profile_id: int, profile: ProfileUpdate):
    pool = await get_db_pool()
    updates = []
    values = []
    idx = 1

    if profile.name is not None:
        updates.append(f"name = ${idx}")
        values.append(profile.name)
        idx += 1
    if profile.keywords is not None:
        updates.append(f"keywords = ${idx}")
        values.append(profile.keywords)
        idx += 1
    if profile.categories is not None:  # ADD THIS BLOCK
        updates.append(f"categories = ${idx}")
        values.append(profile.categories)
        idx += 1
    if profile.email_notify is not None:
        updates.append(f"email_notify = ${idx}")
        values.append(profile.email_notify)
        idx += 1
    if profile.frequency is not None:
        updates.append(f"frequency = ${idx}")
        values.append(profile.frequency.value)
        idx += 1
    if profile.threshold is not None:
        updates.append(f"threshold = ${idx}")
        values.append(profile.threshold)
        idx += 1
    if profile.top_x is not None:
        updates.append(f"top_x = ${idx}")
        values.append(profile.top_x)
        idx += 1

    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")

    updates.append(f"updated_at = ${idx}")
    values.append(datetime.now())
    idx += 1

    values.append(profile_id)
    query = f"""UPDATE profiles SET {', '.join(updates)}
                WHERE id = ${idx}
                RETURNING id, user_id, name, keywords, categories, email_notify, frequency, threshold, top_x, created_at, updated_at"""

    async with pool.acquire() as conn:
        row = await conn.fetchrow(query, *values)
        if not row:
            raise HTTPException(status_code=404, detail="Profile not found")
        return dict(row)


@router.delete("/{profile_id}", status_code=204)
async def delete_profile(profile_id: int):
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        result = await conn.execute("DELETE FROM profiles WHERE id = $1", profile_id)
        if result == "DELETE 0":
            raise HTTPException(status_code=404, detail="Profile not found")
