from contextlib import asynccontextmanager
from pathlib import Path
import sys

sys.path.append(str(Path(__file__).resolve().parents[2]))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.dashboard import router as dashboard_router
from app.api.lecturer import router as lecturer_router
from app.api.taxonomy import router as taxonomy_router

from Gradex_AI_Server.app.session_auth import setup_auth, initialize_auth, close_auth, allowed_origins


@asynccontextmanager
async def lifespan(app):
    await initialize_auth()
    yield
    close_auth()


app = FastAPI(title="DBMS Analytics API", version="1.0.0", lifespan=lifespan)
setup_auth(app)

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(dashboard_router, prefix="/api")
app.include_router(lecturer_router, prefix="/api")
app.include_router(taxonomy_router)
