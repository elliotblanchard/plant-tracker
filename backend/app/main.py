"""FastAPI application entry point."""

import asyncio
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.auth import router as auth_router, verify_token
from app.config import settings
from app.database import SessionLocal, get_db, init_db
from app.routers import analysis, images, plants

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Create database tables on startup; optionally start Drive sync scheduler."""
    init_db()

    sync_task = None
    if settings.drive_enabled:
        from app.scheduler import run_sync_loop

        sync_task = asyncio.create_task(run_sync_loop())
        logger.info("Background Drive sync scheduler started")

    yield

    if sync_task is not None:
        sync_task.cancel()
        try:
            await sync_task
        except asyncio.CancelledError:
            pass


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
app.include_router(auth_router)
app.include_router(plants.router)
app.include_router(images.router)
app.include_router(analysis.router)


@app.get("/api/health")
def health_check() -> dict[str, str]:
    """Simple liveness probe."""
    return {"status": "ok"}


@app.post("/api/sync", dependencies=[Depends(verify_token)])
def manual_sync() -> dict:
    """Manually trigger a Google Drive sync + analysis cycle."""
    from app.drive_sync import sync_and_analyze

    db = SessionLocal()
    try:
        return sync_and_analyze(db)
    finally:
        db.close()


@app.post("/api/set-drive-credentials", dependencies=[Depends(verify_token)])
async def set_drive_credentials(request: Request) -> dict:
    """Store Drive service account JSON to the persistent volume.

    Send the raw JSON key file contents as the request body.
    This only needs to be done once — the file persists across deploys.
    """
    body = await request.body()
    if not body:
        raise HTTPException(status_code=400, detail="Empty request body")

    import json
    try:
        json.loads(body)
    except json.JSONDecodeError as e:
        raise HTTPException(status_code=400, detail=f"Invalid JSON: {e}")

    creds_path = Path("/data/drive-creds.json")
    creds_path.parent.mkdir(parents=True, exist_ok=True)
    creds_path.write_bytes(body)

    return {"status": "ok", "path": str(creds_path), "size": len(body)}


# Serve frontend static files if the build output exists (production / Docker)
_static_dir = Path(__file__).resolve().parent.parent / "static"
if _static_dir.is_dir():
    app.mount("/", StaticFiles(directory=str(_static_dir), html=True), name="static")
    logger.info("Serving frontend static files from %s", _static_dir)
