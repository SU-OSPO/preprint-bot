from fastapi import APIRouter, HTTPException, Query
from typing import List, Optional
from schemas import EmbeddingCreate, EmbeddingUpdate, EmbeddingResponse, VectorSearchRequest
from database import get_db_pool

router = APIRouter(prefix="/embeddings", tags=["embeddings"])


@router.post("/", response_model=EmbeddingResponse, status_code=201)
async def create_embedding(embedding: EmbeddingCreate):
    """Store a single embedding"""
    pool = await get_db_pool()
    try:
        embedding_str = f"[{','.join(map(str, embedding.embedding))}]"
        
        async with pool.acquire() as conn:
            if embedding.section_id is None:
                row = await conn.fetchrow(
                    """
                    INSERT INTO embeddings (paper_id, section_id, embedding, type, model_name)
                    VALUES ($1, $2, $3::vector, $4, $5)
                    ON CONFLICT (paper_id, type, model_name) WHERE section_id IS NULL
                    DO UPDATE SET embedding = EXCLUDED.embedding
                    RETURNING id, paper_id, section_id, embedding, type, model_name, created_at
                    """,
                    embedding.paper_id,
                    embedding.section_id,
                    embedding_str,
                    embedding.type.value,
                    embedding.model_name
                )
            else:
                row = await conn.fetchrow(
                    """
                    INSERT INTO embeddings (paper_id, section_id, embedding, type, model_name)
                    VALUES ($1, $2, $3::vector, $4, $5)
                    ON CONFLICT (paper_id, section_id, type, model_name) WHERE section_id IS NOT NULL
                    DO UPDATE SET embedding = EXCLUDED.embedding
                    RETURNING id, paper_id, section_id, embedding, type, model_name, created_at
                    """,
                    embedding.paper_id,
                    embedding.section_id,
                    embedding_str,
                    embedding.type.value,
                    embedding.model_name
                )
            result = dict(row)
            result['embedding'] = embedding.embedding
            return result
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/batch", response_model=List[EmbeddingResponse], status_code=201)
async def batch_create_embeddings(embeddings: List[EmbeddingCreate]):
    """Batch insert embeddings for efficiency"""
    pool = await get_db_pool()
    results = []
    
    async with pool.acquire() as conn:
        async with conn.transaction():
            for emb in embeddings:
                try:
                    embedding_str = f"[{','.join(map(str, emb.embedding))}]"
                    row = await conn.fetchrow(
                        """
                        INSERT INTO embeddings (paper_id, section_id, embedding, type, model_name)
                        VALUES ($1, $2, $3::vector, $4, $5)
                        RETURNING id, paper_id, section_id, type, model_name, created_at
                        """,
                        emb.paper_id,
                        emb.section_id,
                        embedding_str,
                        emb.type.value,
                        emb.model_name
                    )
                    result = dict(row)
                    result['embedding'] = emb.embedding
                    results.append(result)
                except Exception as e:
                    print(f"Failed to insert embedding: {e}")
    
    return results


@router.get("/", response_model=List[EmbeddingResponse])
async def get_embeddings(
    paper_id: Optional[int] = Query(None),
    corpus_id: Optional[int] = Query(None),
    type: Optional[str] = Query(None),
    paper_ids: Optional[List[int]] = Query(None)
):
    """Get embeddings with optional filters"""
    if paper_id is not None and paper_ids is not None:
        raise HTTPException(
            status_code=400,
            detail="Specify either paper_id or paper_ids, not both.",
        )
    pool = await get_db_pool()
    
    conditions = []
    params = []
    idx = 1
    
    if paper_id is not None:
        conditions.append(f"e.paper_id = ${idx}")
        params.append(paper_id)
        idx += 1
    
    if corpus_id is not None:
        conditions.append(f"pc.corpus_id = ${idx}")
        params.append(corpus_id)
        idx += 1
    
    if type is not None:
        conditions.append(f"e.type = ${idx}")
        params.append(type)
        idx += 1
    
    if paper_ids is not None:
        conditions.append(f"e.paper_id = ANY(${idx})")
        params.append(paper_ids)
        idx += 1
    
    where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    
    query = f"""
        SELECT DISTINCT e.id, e.paper_id, e.section_id, e.type, e.model_name, e.created_at,
               e.embedding::text as embedding_text
        FROM embeddings e
        JOIN papers p ON e.paper_id = p.id
        LEFT JOIN papers_corpora pc ON p.id = pc.paper_id
        {where_clause}
        ORDER BY e.created_at DESC
    """
    
    async with pool.acquire() as conn:
        rows = await conn.fetch(query, *params)
        
        results = []
        for row in rows:
            result = dict(row)
            # Parse embedding vector back to list
            emb_text = result.pop('embedding_text', '[]')
            result['embedding'] = parse_vector(emb_text)
            results.append(result)
        
        return results


@router.get("/{embedding_id}", response_model=EmbeddingResponse)
async def get_embedding(embedding_id: int):
    """Get a specific embedding by ID"""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT id, paper_id, section_id, type, model_name, created_at,
                   embedding::text as embedding_text
            FROM embeddings 
            WHERE id = $1
            """,
            embedding_id
        )
        if not row:
            raise HTTPException(status_code=404, detail="Embedding not found")
        
        result = dict(row)
        emb_text = result.pop('embedding_text', '[]')
        result['embedding'] = parse_vector(emb_text)
        return result


@router.post("/search/similar")
async def search_similar_embeddings(request: VectorSearchRequest):
    """Search for similar papers using vector similarity"""
    pool = await get_db_pool()
    
    # Convert embedding to pgvector format
    embedding_str = f"[{','.join(map(str, request.embedding))}]"
    
    # Build query with optional corpus filter
    # NOTE: ORDER BY must use the raw distance operator (<=>) for pgvector
    # to use its HNSW/IVFFlat index.  Ordering by a derived alias like
    # ``similarity DESC`` forces a sequential scan + sort.
    if request.corpus_id is not None:
        query = """
            SELECT DISTINCT
                p.id, p.source_id, p.title, p.abstract,
                1 - (e.embedding <=> $1::vector) as similarity
            FROM embeddings e
            JOIN papers p ON e.paper_id = p.id
            JOIN papers_corpora pc ON p.id = pc.paper_id
            WHERE e.type = 'abstract'
            AND pc.corpus_id = $2
            AND 1 - (e.embedding <=> $1::vector) >= $3
            ORDER BY e.embedding <=> $1::vector
            LIMIT $4
        """
        params = [embedding_str, request.corpus_id, request.threshold, request.limit]
    else:
        query = """
            SELECT DISTINCT
                p.id, p.source_id, p.title, p.abstract,
                1 - (e.embedding <=> $1::vector) as similarity
            FROM embeddings e
            JOIN papers p ON e.paper_id = p.id
            WHERE e.type = 'abstract'
            AND 1 - (e.embedding <=> $1::vector) >= $2
            ORDER BY e.embedding <=> $1::vector
            LIMIT $3
        """
        params = [embedding_str, request.threshold, request.limit]
    
    async with pool.acquire() as conn:
        rows = await conn.fetch(query, *params)
        return [dict(row) for row in rows]

@router.delete("/{embedding_id}", status_code=204)
async def delete_embedding(embedding_id: int):
    """Delete an embedding"""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        result = await conn.execute(
            "DELETE FROM embeddings WHERE id = $1",
            embedding_id
        )
        if result == "DELETE 0":
            raise HTTPException(status_code=404, detail="Embedding not found")


def parse_vector(vector_str: str) -> List[float]:
    """Parse pgvector string format to Python list"""
    # Remove brackets and parse
    if not vector_str or vector_str == '[]':
        return []
    
    cleaned = vector_str.strip('[]')
    if not cleaned:
        return []
    
    try:
        return [float(x.strip()) for x in cleaned.split(',')]
    except:
        return []