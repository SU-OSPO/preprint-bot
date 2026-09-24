from fastapi import APIRouter, HTTPException
from typing import List
from schemas import ProfileCorpusCreate, ProfileCorpusResponse
from database import get_db_pool

router = APIRouter(prefix="/profile-corpora", tags=["profile-corpora"])


@router.post("/", response_model=ProfileCorpusResponse, status_code=201)
async def create_profile_corpus(pc: ProfileCorpusCreate):
    pool = await get_db_pool()
    try:
        async with pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO profile_corpora (profile_id, corpus_id)
                VALUES ($1, $2)
                """,
                pc.profile_id,
                pc.corpus_id,
            )
            return {"profile_id": pc.profile_id, "corpus_id": pc.corpus_id}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/", response_model=List[ProfileCorpusResponse])
async def get_profile_corpora():
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch("SELECT profile_id, corpus_id FROM profile_corpora")
        return [dict(row) for row in rows]


@router.get("/profile/{profile_id}", response_model=List[ProfileCorpusResponse])
async def get_corpora_by_profile(profile_id: int):
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT profile_id, corpus_id FROM profile_corpora WHERE profile_id = $1", profile_id
        )
        return [dict(row) for row in rows]


@router.delete("/", status_code=204)
async def delete_profile_corpus(profile_id: int, corpus_id: int):
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        result = await conn.execute(
            "DELETE FROM profile_corpora WHERE profile_id = $1 AND corpus_id = $2",
            profile_id,
            corpus_id,
        )
        if result == "DELETE 0":
            raise HTTPException(status_code=404, detail="Profile-Corpus association not found")
