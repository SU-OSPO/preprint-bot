from fastapi import APIRouter, HTTPException
from typing import List
from schemas import CorpusCreate, CorpusUpdate, CorpusResponse
from database import get_db_pool

router = APIRouter(prefix="/corpora", tags=["corpora"])


@router.post("/", response_model=CorpusResponse, status_code=201)
async def create_corpus(corpus: CorpusCreate):
    pool = await get_db_pool()
    try:
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                INSERT INTO corpora (user_id, name, description)
                VALUES ($1, $2, $3)
                RETURNING id, user_id, name, description, created_at
                """,
                corpus.user_id,
                corpus.name,
                corpus.description,
            )
            return dict(row)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/", response_model=List[CorpusResponse])
async def get_corpora():
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch("SELECT id, user_id, name, description, created_at FROM corpora")
        return [dict(row) for row in rows]


@router.get("/{corpus_id}", response_model=CorpusResponse)
async def get_corpus(corpus_id: int):
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT id, user_id, name, description, created_at FROM corpora WHERE id = $1",
            corpus_id,
        )
        if not row:
            raise HTTPException(status_code=404, detail="Corpus not found")
        return dict(row)


@router.put("/{corpus_id}", response_model=CorpusResponse)
async def update_corpus(corpus_id: int, corpus: CorpusUpdate):
    pool = await get_db_pool()
    updates = []
    values = []
    idx = 1

    if corpus.name is not None:
        updates.append(f"name = ${idx}")
        values.append(corpus.name)
        idx += 1
    if corpus.description is not None:
        updates.append(f"description = ${idx}")
        values.append(corpus.description)
        idx += 1

    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")

    values.append(corpus_id)
    query = f"UPDATE corpora SET {', '.join(updates)} WHERE id = ${idx} RETURNING id, user_id, name, description, created_at"

    async with pool.acquire() as conn:
        row = await conn.fetchrow(query, *values)
        if not row:
            raise HTTPException(status_code=404, detail="Corpus not found")
        return dict(row)


@router.delete("/{corpus_id}", status_code=204)
async def delete_corpus(corpus_id: int):
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        result = await conn.execute("DELETE FROM corpora WHERE id = $1", corpus_id)
        if result == "DELETE 0":
            raise HTTPException(status_code=404, detail="Corpus not found")
