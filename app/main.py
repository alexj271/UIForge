from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.api.routes import router
from app.config import settings
from app.services.ocr import init_ocr_reader

Path("static").mkdir(exist_ok=True)
Path("uploads").mkdir(exist_ok=True)
Path("output").mkdir(exist_ok=True)


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_ocr_reader(["en"])
    if settings.detector == "florence2":
        from app.services.florence_client import init_florence
        import asyncio
        await asyncio.get_event_loop().run_in_executor(
            None, init_florence, settings.florence_model_id
        )
    elif settings.detector == "groundingdino":
        from app.services.grounding_dino_client import init_grounding_dino
        import asyncio
        await asyncio.get_event_loop().run_in_executor(
            None, init_grounding_dino, settings.grounding_dino_model_id
        )
    yield


app = FastAPI(title="UIForge", lifespan=lifespan)

app.mount("/static", StaticFiles(directory="static"), name="static")
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")
app.mount("/output", StaticFiles(directory="output"), name="output")

app.include_router(router)
