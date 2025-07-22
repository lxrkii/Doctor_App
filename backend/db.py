from tortoise import Tortoise
from backend.config import DB_URL

async def init_db():
    await Tortoise.init(
        db_url=DB_URL,
        modules={"models": ["backend.models"]}
    )
    await Tortoise.generate_schemas() 