import logging
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware

from src.config import Settings, get_settings
from src.knowledge import database as db
from src.knowledge.database import close_db, init_db, get_db
from src.knowledge.vector_store import VectorStore

logger = logging.getLogger("mimir")


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    logging.basicConfig(level=getattr(logging, settings.log_level.upper()))
    logger.info("Starting Mimir...")

    # Initialize database
    await init_db(settings.database_path)
    logger.info("Database initialized")

    # Initialize vector store
    app.state.vector_store = VectorStore(settings.chroma_path)
    logger.info("Vector store initialized")

    # Initialize AI harness (overlay DB-stored API keys + persisted preset)
    from src.harness.router import HarnessRouter, load_harness_config_with_db_keys
    import json as _json
    db_keys = {}
    try:
        _row = await db.fetch_one("SELECT value FROM settings WHERE key = 'api_keys'")
        if _row:
            db_keys = _json.loads(_row["value"])
    except Exception:
        pass
    # Load persisted preset, fall back to env var
    preset = settings.harness_preset
    try:
        _preset_row = await db.fetch_one("SELECT value FROM settings WHERE key = 'active_preset'")
        if _preset_row:
            preset = _json.loads(_preset_row["value"])
    except Exception:
        pass
    config = load_harness_config_with_db_keys(settings, preset, db_keys)
    app.state.harness = HarnessRouter(config)
    logger.info("AI harness initialized")

    # Start background scheduler
    from src.processing.pipeline import start_scheduler
    app.state.scheduler = await start_scheduler(app)
    logger.info("Background scheduler started")

    # Start file watcher on inbox
    from src.capture.file_watcher import FileWatcherService
    app.state.file_watcher = FileWatcherService()
    try:
        app.state.file_watcher.start(settings.inbox_path, settings.documents_path)
        logger.info("File watcher started")
    except Exception as e:
        logger.warning(f"File watcher failed to start: {e}")

    # Register email polling job
    from src.capture.email_watcher import poll_email
    app.state.scheduler.add_job(
        poll_email, "interval", seconds=settings.imap_poll_interval,
        args=[app], id="poll_email", max_instances=1, coalesce=True,
    )

    # Initialize messaging bridge
    try:
        from src.bridge.router import init_bridge
        app.state.bridge = await init_bridge(app)
        logger.info("Messaging bridge initialized")
    except Exception as e:
        logger.warning(f"Messaging bridge failed to start: {e}")
        app.state.bridge = None

    yield

    # Shutdown
    if hasattr(app.state, "bridge") and app.state.bridge:
        await app.state.bridge.shutdown()
    if hasattr(app.state, "file_watcher"):
        app.state.file_watcher.stop()
    if hasattr(app.state, "scheduler"):
        app.state.scheduler.shutdown(wait=False)
    await close_db()
    logger.info("Mimir stopped")


app = FastAPI(
    title="Mimir API",
    version="0.1.0",
    description="Self-hosted AI second brain agent",
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# API key auth middleware
@app.middleware("http")
async def api_key_auth(request: Request, call_next):
    settings = get_settings()
    if settings.api_key:
        # Skip auth for docs and health
        if request.url.path in ("/api/health", "/docs", "/openapi.json", "/redoc") or request.url.path.startswith("/bridge/"):
            return await call_next(request)
        auth = request.headers.get("Authorization", "")
        if auth != f"Bearer {settings.api_key}":
            return Response(status_code=401, content="Unauthorized")
    return await call_next(request)


# Health check
@app.get("/api/health")
async def health():
    return {"status": "ok", "version": "0.1.0"}


# Mount routers
from src.capture.router import router as capture_router
from src.api.search_router import router as search_router
from src.api.browse_router import router as browse_router
from src.api.settings_router import router as settings_router
from src.api.agent_router import router as agent_router
from src.api.export_router import router as export_router
from src.api.import_router import router as import_router

app.include_router(capture_router)
app.include_router(search_router)
app.include_router(browse_router)
app.include_router(settings_router)
app.include_router(agent_router)
app.include_router(export_router)
app.include_router(import_router)

try:
    from src.bridge.router import webhook_router, management_router
    app.include_router(webhook_router)
    app.include_router(management_router)
except Exception as e:
    logger.warning(f"Bridge routers failed to load: {e}")

# Mount MCP server (graceful degradation if mcp not installed)
try:
    from src.mcp_server import create_mcp_app
    app.mount("/mcp", create_mcp_app())
    logger.info("MCP server mounted at /mcp")
except ImportError:
    logger.info("MCP not installed — skipping MCP server mount")
except Exception as e:
    logger.warning(f"MCP server failed to mount: {e}")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("src.main:app", host="0.0.0.0", port=8000, reload=True)
