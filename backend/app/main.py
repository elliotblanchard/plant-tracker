"""FastAPI application entry point."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.database import init_db
from app.routers import analysis, images, plants


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Create database tables on startup."""
    init_db()
    yield


app = FastAPI(
    title="Plant Tracker API",
    description="Automated monitoring of Marchantia polymorpha growth and health.",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS — allow the Vite dev server and common local origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers
app.include_router(plants.router)
app.include_router(images.router)
app.include_router(analysis.router)


@app.get("/api/health")
def health_check() -> dict[str, str]:
    """Simple liveness probe."""
    return {"status": "ok"}
