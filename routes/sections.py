from fastapi import APIRouter, HTTPException, Query
from typing import List, Optional
from database import get_db_pool
from schemas import SectionCreate, SectionUpdate, SectionResponse

router = APIRouter(prefix="/sections", tags=["sections"])


@router.post("/", response_model=SectionResponse, status_code=201)
async def create_section(section: SectionCreate):
    """Create a new section"""
    pool = await get_db_pool()

    try:
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                INSERT INTO sections (paper_id, section_header, section_text, section_order)
                VALUES ($1, $2, $3, $4)
                RETURNING id, paper_id, section_header, section_text, section_order, created_at
                """,
                section.paper_id,
                section.header,
                section.text,
                0,
            )
            result = dict(row)
            # Map database fields to response fields
            return {
                "id": result["id"],
                "paper_id": result["paper_id"],
                "header": result["section_header"],
                "text": result["section_text"],
                "created_at": result["created_at"],
            }
    except Exception as e:
        if "foreign key" in str(e).lower():
            raise HTTPException(status_code=400, detail="Invalid paper_id")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/", response_model=List[SectionResponse])
async def list_sections(paper_id: Optional[int] = Query(None)):
    """List sections, optionally filtered by paper"""
    pool = await get_db_pool()

    if paper_id is not None:
        query = """
            SELECT id, paper_id, section_header, section_text, section_order, created_at 
            FROM sections 
            WHERE paper_id = $1 
            ORDER BY section_order, id
        """
        params = [paper_id]
    else:
        query = """
            SELECT id, paper_id, section_header, section_text, section_order, created_at 
            FROM sections 
            ORDER BY paper_id, section_order, id
        """
        params = []

    async with pool.acquire() as conn:
        rows = await conn.fetch(query, *params)
        results = []
        for row in rows:
            result = dict(row)
            results.append(
                {
                    "id": result["id"],
                    "paper_id": result["paper_id"],
                    "header": result["section_header"],
                    "text": result["section_text"],
                    "created_at": result["created_at"],
                }
            )
        return results


@router.get("/{section_id}", response_model=SectionResponse)
async def get_section(section_id: int):
    """Get a specific section"""
    pool = await get_db_pool()

    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT id, paper_id, section_header, section_text, section_order, created_at FROM sections WHERE id = $1",
            section_id,
        )
        if not row:
            raise HTTPException(status_code=404, detail="Section not found")
        result = dict(row)
        return {
            "id": result["id"],
            "paper_id": result["paper_id"],
            "header": result["section_header"],
            "text": result["section_text"],
            "created_at": result["created_at"],
        }


@router.patch("/{section_id}", response_model=SectionResponse)
async def update_section(section_id: int, section: SectionUpdate):
    """Update a section"""
    pool = await get_db_pool()

    update_fields = []
    values = []
    param_num = 1

    if section.header is not None:
        update_fields.append(f"section_header = ${param_num}")
        values.append(section.header)
        param_num += 1

    if section.text is not None:
        update_fields.append(f"section_text = ${param_num}")
        values.append(section.text)
        param_num += 1

    if not update_fields:
        raise HTTPException(status_code=400, detail="No fields to update")

    values.append(section_id)

    query = f"""
        UPDATE sections
        SET {', '.join(update_fields)}
        WHERE id = ${param_num}
        RETURNING id, paper_id, section_header, section_text, section_order, created_at
    """

    async with pool.acquire() as conn:
        row = await conn.fetchrow(query, *values)
        if not row:
            raise HTTPException(status_code=404, detail="Section not found")
        result = dict(row)
        return {
            "id": result["id"],
            "paper_id": result["paper_id"],
            "header": result["section_header"],
            "text": result["section_text"],
            "created_at": result["created_at"],
        }


@router.delete("/{section_id}", status_code=204)
async def delete_section(section_id: int):
    """Delete a section"""
    pool = await get_db_pool()

    async with pool.acquire() as conn:
        result = await conn.execute("DELETE FROM sections WHERE id = $1", section_id)
        if result == "DELETE 0":
            raise HTTPException(status_code=404, detail="Section not found")
