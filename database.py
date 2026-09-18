import asyncpg
from config import settings


class Database:
    pool = None


async def get_db_pool():
    if Database.pool is None:
        Database.pool = await asyncpg.create_pool(
            host=settings.DATABASE_HOST,
            port=settings.DATABASE_PORT,
            database=settings.DATABASE_NAME,
            user=settings.DATABASE_USER,
            password=settings.DATABASE_PASSWORD,
        )
    return Database.pool


async def close_db_pool():
    if Database.pool:
        await Database.pool.close()
