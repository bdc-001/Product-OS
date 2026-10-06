import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.gzip import GZipMiddleware

from app import models as _models  # noqa: F401
from app.api.routers import public_router, router
from app.bootstrap import bootstrap
from app.config import settings, validate_startup

log = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    validate_startup()
    bootstrap()
    from app.pipelines import scheduler, worker

    if (settings.env_value("run_worker") or "").strip().lower() == "inline":
        worker.start()
    if settings.env_value("run_scheduler"):
        scheduler.start()
    try:
        yield
    finally:
        scheduler.stop()
        worker.stop()


_docs = not settings.is_production
app = FastAPI(
    title=settings.app_name,
    lifespan=lifespan,
    docs_url="/docs" if _docs else None,
    redoc_url=None,
    openapi_url="/openapi.json" if _docs else None,
)
app.add_middleware(GZipMiddleware, minimum_size=500)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(public_router, prefix="/api")
app.include_router(router, prefix="/api")


@app.get("/")
def root():
    return {"name": settings.app_name}
