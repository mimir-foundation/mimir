import logging
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware

from src.config import Settings, get_settings
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

    # Initialize AI harness
    from src.harness.router import HarnessRouter, load_harness_config
    config = load_harness_config(settings)
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

app.include_router(capture_router)
app.include_router(search_router)
app.include_router(browse_router)
app.include_router(settings_router)
app.include_router(agent_router)
app.include_router(export_router)

try:
    from src.bridge.router import webhook_router, management_router
    app.include_router(webhook_router)
    app.include_router(management_router)
except Exception as e:
    logger.warning(f"Bridge routers failed to load: {e}")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("src.main:app", host="0.0.0.0", port=8000, reload=True)
