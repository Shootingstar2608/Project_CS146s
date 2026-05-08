from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from backend.app.config import settings
from backend.app.models.db_models import Base
import logging

logger = logging.getLogger(__name__)

# use async engine for postgres
engine = create_async_engine(settings.POSTGRES_URL, pool_size=10, max_overflow=20)

# session production class
SessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

# helper get_db function
async def get_db():
    async with SessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()

# connect and initiate db
async def init_db():
    try:
        async with engine.begin() as conn:
            # Note: In production, use Alembic. 
            # This is for dev/scaffolding.
            await conn.run_sync(Base.metadata.create_all)
            logger.info("Database initiated")
    except Exception as e:
        logger.error(f"connection failed: {e}")
        raise e

async def close_db():
    await engine.dispose()
