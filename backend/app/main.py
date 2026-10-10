"""FastAPI application factory."""
import logging
import time

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.api import accounts, actions, automation, auth, catalog, dashboard, diagnostics, export, jobs, license_access, notifications, webhooks
from app.core.config import get_settings
from app.core.db import get_db
from app.core.deps import new_correlation_id
from app.models import models  # noqa: F401  (register models)
from app.models.models import ErrorLog
from app.schemas.schemas import HealthOut

settings = get_settings()
log = logging.getLogger("app")


def create_app() -> FastAPI:
    app = FastAPI(title=settings.APP_NAME, version="1.0.0")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def correlation_middleware(request: Request, call_next):
        cid = request.headers.get("X-Correlation-ID") or new_correlation_id()
        request.state.correlation_id = cid
        start = time.time()
        try:
            response = await call_next(request)
        except Exception:
            # Last-resort guard; exception handlers below normally catch these.
            log.exception("unhandled error cid=%s path=%s", cid, request.url.path)
            _store_error(request, cid, "unhandled exception")
            return JSONResponse(
                status_code=500,
                content={"detail": "Internal server error", "correlation_id": cid},
            )
        response.headers["X-Correlation-ID"] = cid
        response.headers["X-Process-Time"] = f"{time.time() - start:.3f}s"
        return response

    @app.exception_handler(Exception)
    async def safe_exception_handler(request: Request, exc: Exception):
        cid = getattr(request.state, "correlation_id", new_correlation_id())
        log.exception("request failed cid=%s path=%s", cid, request.url.path)
        _store_error(request, cid, f"{type(exc).__name__}: {exc}")
        return JSONResponse(
            status_code=500,
            content={"detail": "Internal server error", "correlation_id": cid},
        )

    @app.get("/health", response_model=HealthOut, tags=["system"])
    def health():
        return HealthOut()

    app.include_router(auth.router, prefix="/api/v1")
    app.include_router(accounts.router, prefix="/api/v1")
    app.include_router(dashboard.router, prefix="/api/v1")
    app.include_router(catalog.router, prefix="/api/v1")
    app.include_router(actions.router, prefix="/api/v1")
    app.include_router(export.router, prefix="/api/v1")
    app.include_router(automation.router, prefix="/api/v1")
    app.include_router(jobs.router, prefix="/api/v1")
    app.include_router(notifications.router, prefix="/api/v1")
    app.include_router(webhooks.router, prefix="/api/v1")
    app.include_router(diagnostics.router, prefix="/api/v1")
    app.include_router(license_access.router)
    app.include_router(license_access.pages_router)

    # Serve the React web dashboard (web/dist) as a single-page app.
    # API routes above take precedence; unknown non-API paths get index.html
    # so React Router handles them. The SPA talks to {origin}/api/v1, so it
    # survives tunnel URL rotations without a rebuild.
    from pathlib import Path
    from fastapi.responses import FileResponse
    from fastapi.staticfiles import StaticFiles
    WEB_DIST = Path(__file__).resolve().parent.parent.parent / "web" / "dist"
    if WEB_DIST.is_dir():
        assets_dir = WEB_DIST / "assets"
        if assets_dir.is_dir():
            app.mount("/assets", StaticFiles(directory=assets_dir), name="web-assets")
        _SPA_SKIP = ("api/", "docs", "openapi.json", "health",
                     "gumroad-setup", "app-setup", "github-setup", "assets/")

        @app.get("/{full_path:path}", include_in_schema=False)
        def serve_spa(full_path: str):
            if full_path.startswith(_SPA_SKIP):
                from fastapi import HTTPException
                raise HTTPException(status_code=404, detail="Not found")
            index = WEB_DIST / "index.html"
            if index.is_file():
                return FileResponse(index, media_type="text/html")
            from fastapi import HTTPException
            raise HTTPException(status_code=404, detail="Web dashboard not built")

    @app.on_event("startup")
    def _startup():
        # Create tables if migrations haven't run (dev convenience; alembic is canonical).
        from app.core.db import Base, get_engine

        Base.metadata.create_all(bind=get_engine(), checkfirst=True)
        from app.scheduler.scheduler import start_scheduler

        start_scheduler()
        log.info("app started")

    @app.on_event("shutdown")
    def _shutdown():
        from app.scheduler.scheduler import stop_scheduler

        stop_scheduler()
        log.info("app stopped")

    return app


def _store_error(request: Request, cid: str, message: str) -> None:
    try:
        db: Session = next(get_db())
        try:
            db.add(ErrorLog(correlation_id=cid, path=request.url.path,
                            message=message[:2000]))
            db.commit()
        finally:
            db.close()
    except Exception:
        pass


app = create_app()
