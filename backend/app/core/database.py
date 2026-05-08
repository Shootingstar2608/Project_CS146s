from sqlalchemy import create_engine, false, Base
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
import os
from dotenv import load_dotenv
import logging

logger = logging.getLogger(__name__)

db_url = os.getenv("POSTGRES_URL")

# pool connection
engine = create_engine(db_url, pool=10)
# session production class
SessionLocal = async_sessionmaker(engine, expire_on_commit=false)


# helper get_db function
async def get_db() -> AsyncSession:
    async with SessionLocal() as session:
        yield session


# connect and dispost db
async def init_db():
    try:
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
            logger.info("Database initiated")
    except Exception as e:
        logger.error(f"connection failed: {e}")
        raise e


async def close_db():
    await engine.dispose()
