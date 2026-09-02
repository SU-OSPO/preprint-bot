from fastapi import APIRouter, HTTPException, Query
from typing import List, Optional
from schemas import PaperCreate, PaperUpdate, PaperResponse
from database import get_db_pool
import json

router = APIRouter(prefix="/papers", tags=["papers"])

@router.get("/needing-processing", response_model=List[PaperResponse])
async def get_papers_needing_processing():
    """User-corpus papers with a PDF on disk but no sections extracted yet."""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT p.id, p.corpus_id, p.source_id, p.title, p.abstract, p.metadata,
                   p.pdf_path, p.processed_text_path, p.submitted_date, p.source, p.created_at
            FROM papers p
            LEFT JOIN sections s ON p.id = s.paper_id
            WHERE p.pdf_path IS NOT NULL
              AND s.id IS NULL
              AND EXISTS (
                  SELECT 1 FROM papers_corpora pc
                  JOIN corpora c ON pc.corpus_id = c.id
                  WHERE pc.paper_id = p.id
                    AND c.name <> 'arxiv_papers'
              )
            ORDER BY p.created_at DESC
            """
        )
        results = []
        for row in rows:
            result = dict(row)
            if result['metadata']:
                result['metadata'] = json.loads(result['metadata'])
            results.append(result)
        return results


@router.get("/needing-embeddings", response_model=List[PaperResponse])
async def get_papers_needing_embeddings():
    """Papers with sections but no abstract embedding yet."""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT DISTINCT p.id, p.corpus_id, p.source_id, p.title, p.abstract, p.metadata,
                   p.pdf_path, p.processed_text_path, p.submitted_date, p.source, p.created_at
            FROM papers p
            JOIN sections s ON p.id = s.paper_id
            LEFT JOIN embeddings e ON p.id = e.paper_id AND e.type = 'abstract'
            WHERE e.id IS NULL
            ORDER BY p.created_at DESC
            """
        )
        results = []
        for row in rows:
            result = dict(row)
            if result['metadata']:
                result['metadata'] = json.loads(result['metadata'])
            results.append(result)
        return results


@router.post("/", response_model=PaperResponse, status_code=201)
async def create_paper(paper: PaperCreate):
    pool = await get_db_pool()
    try:
        # Convert timezone-aware to naive datetime for PostgreSQL TIMESTAMP
        submitted_date_naive = paper.submitted_date.replace(tzinfo=None) if paper.submitted_date else None
        
        async with pool.acquire() as conn:
            # Wrap in a transaction so the paper + junction insert are atomic
            async with conn.transaction():
                row = await conn.fetchrow(
                    """
                    INSERT INTO papers (source_id, title, abstract, metadata, pdf_path, submitted_date, source)
                    VALUES ($1, $2, $3, $4, $5, $6, $7)
                    RETURNING id, corpus_id, source_id, title, abstract, metadata, pdf_path, processed_text_path, submitted_date, source, created_at
                    """,
                    paper.source_id, 
                    paper.title, 
                    paper.abstract,
                    json.dumps(paper.metadata) if paper.metadata else None,
                    paper.pdf_path,
                    submitted_date_naive,
                    paper.source.value
                )
                # Populate the M2M junction table
                if paper.corpus_id is not None:
                    await conn.execute(
                        """
                        INSERT INTO papers_corpora (paper_id, corpus_id)
                        VALUES ($1, $2)
                        ON CONFLICT DO NOTHING
                        """,
                        row['id'], paper.corpus_id
                    )
            result = dict(row)
            if result['metadata']:
                result['metadata'] = json.loads(result['metadata'])
            return result
    except Exception as e:
        print(f"ERROR creating paper: {e}")
        print(f"Paper data: source_id={paper.source_id}, submitted_date={paper.submitted_date}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/{paper_id}/processed-text", response_model=PaperResponse)
async def update_processed_text_path(paper_id: int, path: str = Query(...)):
    """Update the processed text path for a paper"""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            UPDATE papers 
            SET processed_text_path = $1 
            WHERE id = $2
            RETURNING id, corpus_id, source_id, title, abstract, metadata, pdf_path, processed_text_path, submitted_date, source, created_at
            """,
            path, paper_id
        )
        if not row:
            raise HTTPException(status_code=404, detail="Paper not found")
        result = dict(row)
        if result['metadata']:
            result['metadata'] = json.loads(result['metadata'])
        return result

@router.get("/", response_model=List[PaperResponse])
async def get_papers(corpus_id: Optional[int] = Query(None), source_id: Optional[str] = Query(None)):
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        if source_id is not None:
            rows = await conn.fetch(
                """
                SELECT id, corpus_id, source_id, title, abstract, metadata, pdf_path,
                       processed_text_path, submitted_date, source, created_at
                FROM papers WHERE source_id = $1
                """,
                source_id
            )
        elif corpus_id is not None:
            rows = await conn.fetch(
                """
                SELECT DISTINCT p.id, p.corpus_id, p.source_id, p.title, p.abstract, p.metadata, p.pdf_path, 
                       p.processed_text_path, p.submitted_date, p.source, p.created_at 
                FROM papers p
                JOIN papers_corpora pc ON p.id = pc.paper_id
                WHERE pc.corpus_id = $1
                """,
                corpus_id
            )
        else:
            rows = await conn.fetch(
                """
                SELECT id, corpus_id, source_id, title, abstract, metadata, pdf_path, 
                       processed_text_path, submitted_date, source, created_at 
                FROM papers
                """
            )
        results = []
        for row in rows:
            result = dict(row)
            if result['metadata']:
                result['metadata'] = json.loads(result['metadata'])
            results.append(result)
        return results

@router.get("/{paper_id}", response_model=PaperResponse)
async def get_paper(paper_id: int):
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT id, corpus_id, source_id, title, abstract, metadata, pdf_path, 
                   processed_text_path, submitted_date, source, created_at 
            FROM papers WHERE id = $1
            """,
            paper_id
        )
        if not row:
            raise HTTPException(status_code=404, detail="Paper not found")
        result = dict(row)
        if result['metadata']:
            result['metadata'] = json.loads(result['metadata'])
        return result

@router.put("/{paper_id}", response_model=PaperResponse)
async def update_paper(paper_id: int, paper: PaperUpdate):
    pool = await get_db_pool()
    updates = []
    values = []
    idx = 1
    
    if paper.source_id is not None:
        updates.append(f"source_id = ${idx}")
        values.append(paper.source_id)
        idx += 1
    if paper.title is not None:
        updates.append(f"title = ${idx}")
        values.append(paper.title)
        idx += 1
    if paper.abstract is not None:
        updates.append(f"abstract = ${idx}")
        values.append(paper.abstract)
        idx += 1
    if paper.metadata is not None:
        updates.append(f"metadata = ${idx}")
        values.append(json.dumps(paper.metadata))
        idx += 1
    if paper.pdf_path is not None:
        updates.append(f"pdf_path = ${idx}")
        values.append(paper.pdf_path)
        idx += 1
    if paper.source is not None:
        updates.append(f"source = ${idx}")
        values.append(paper.source.value)
        idx += 1
    
    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")
    
    values.append(paper_id)
    query = f"""UPDATE papers SET {', '.join(updates)} 
                WHERE id = ${idx} 
                RETURNING id, corpus_id, source_id, title, abstract, metadata, pdf_path, processed_text_path, submitted_date, source, created_at"""
    
    async with pool.acquire() as conn:
        row = await conn.fetchrow(query, *values)
        if not row:
            raise HTTPException(status_code=404, detail="Paper not found")
        result = dict(row)
        if result['metadata']:
            result['metadata'] = json.loads(result['metadata'])
        return result

@router.delete("/{paper_id}", status_code=204)
async def delete_paper(paper_id: int):
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        result = await conn.execute("DELETE FROM papers WHERE id = $1", paper_id)
        if result == "DELETE 0":
            raise HTTPException(status_code=404, detail="Paper not found")



@router.post("/arxiv-stats")
async def record_arxiv_stats(
    submission_date: str = Query(...),
    category: str = Query(...),
    total_papers: int = Query(...)
):
    """Record daily arXiv statistics"""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO arxiv_daily_stats (submission_date, category, total_papers)
            VALUES ($1, $2, $3)
            ON CONFLICT (submission_date, category) 
            DO UPDATE SET total_papers = EXCLUDED.total_papers
            """,
            submission_date, category, total_papers
        )
    return {"status": "recorded"}

@router.get("/arxiv-stats/date/{date}")
async def get_arxiv_stats_for_date(date: str):
    """Get total papers for a specific date across all categories"""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        total = await conn.fetchval(
            """
            SELECT SUM(total_papers) 
            FROM arxiv_daily_stats 
            WHERE submission_date = $1
            """,
            date
        )
        return {"date": date, "total_papers": total or 0}