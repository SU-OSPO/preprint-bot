from fastapi import APIRouter, HTTPException
from typing import List
from database import get_db_pool
from schemas import UserCreate, UserUpdate, UserResponse

router = APIRouter(prefix="/users", tags=["users"])


@router.post("/", response_model=UserResponse)
async def create_user(user: UserCreate):
    """Create a new user"""
    pool = await get_db_pool()

    try:
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                INSERT INTO users (email, name)
                VALUES ($1, $2)
                RETURNING id, email, name, created_at
                """,
                user.email,
                user.name,
            )
            return dict(row)
    except Exception as e:
        if "unique" in str(e).lower():
            raise HTTPException(status_code=400, detail="Email already exists")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/", response_model=List[UserResponse])
async def list_users():
    """List all users"""
    pool = await get_db_pool()

    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT id, email, name, created_at FROM users ORDER BY created_at DESC"
        )
        return [dict(row) for row in rows]


@router.get("/{user_id}", response_model=UserResponse)
async def get_user(user_id: int):
    """Get a specific user"""
    pool = await get_db_pool()

    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT id, email, name, created_at FROM users WHERE id = $1", user_id
        )
        if not row:
            raise HTTPException(status_code=404, detail="User not found")
        return dict(row)


@router.patch("/{user_id}", response_model=UserResponse)
async def update_user(user_id: int, user: UserUpdate):
    """Update a user"""
    pool = await get_db_pool()

    update_fields = []
    values = []
    param_num = 1

    if user.email is not None:
        update_fields.append(f"email = ${param_num}")
        values.append(user.email)
        param_num += 1

    if user.name is not None:
        update_fields.append(f"name = ${param_num}")
        values.append(user.name)
        param_num += 1

    if not update_fields:
        raise HTTPException(status_code=400, detail="No fields to update")

    values.append(user_id)

    query = f"""
        UPDATE users
        SET {', '.join(update_fields)}
        WHERE id = ${param_num}
        RETURNING id, email, name, created_at
    """

    async with pool.acquire() as conn:
        row = await conn.fetchrow(query, *values)
        if not row:
            raise HTTPException(status_code=404, detail="User not found")
        return dict(row)


@router.delete("/{user_id}")
async def delete_user(user_id: int):
    """Delete a user"""
    pool = await get_db_pool()

    async with pool.acquire() as conn:
        result = await conn.execute("DELETE FROM users WHERE id = $1", user_id)
        if result == "DELETE 0":
            raise HTTPException(status_code=404, detail="User not found")
        return {"message": "User deleted successfully"}
