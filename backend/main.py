"""FastAPI application entrypoint."""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend import __version__
from backend.config import get_settings
from backend.core.audit import register_audit_hooks, request_id_middleware
from backend.core.routes import router as core_router
from backend.modules.accounting.routes import router as accounting_router
from backend.modules.hr.routes import router as hr_router
from backend.modules.inventory.routes import router as inventory_router
from backend.modules.inventory.routes_advanced import router as inventory_advanced_router
from backend.modules.inventory.routes_count import router as inventory_counts_router
from backend.modules.mfg.routes import router as mfg_router
from backend.modules.mfg.routes_advanced import router as mfg_advanced_router
from backend.modules.group.routes import router as group_router
from backend.modules.ops.routes import router as ops_router
from backend.modules.outbound.routes import router as outbound_router
from backend.modules.purchase.routes import router as purchase_router
from backend.modules.purchase.routes_advanced import router as purchase_advanced_router
from backend.modules.quality.routes import router as quality_router
from backend.modules.sales.routes import router as sales_router
from backend.modules.sales.routes_advanced import router as sales_advanced_router
from backend.modules.wms.routes import router as wms_router

_log = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    register_audit_hooks()
    _log.info("KOB-ERP backend starting (version=%s)", __version__)
    yield
    _log.info("KOB-ERP backend shutting down")


def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(
        title="KOB-ERP",
        version=__version__,
        debug=settings.debug,
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["X-Request-ID"],
    )

    @app.middleware("http")
    async def _request_id(request, call_next):  # type: ignore[no-untyped-def]
        # Use the pure-ASGI request_id_middleware via Starlette's BaseHTTPMiddleware-style
        # adapter — but BaseHTTPMiddleware does not give us direct ASGI scope, so we set
        # the audit context here and let the route handlers stamp the response header.
        import uuid

        from backend.core.audit import set_audit_context

        request_id = uuid.uuid4().hex[:16]
        set_audit_context(request_id, None)
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response

    @app.get("/health", tags=["meta"])
    async def health() -> dict[str, str]:
        return {"status": "ok", "version": __version__}

    app.include_router(core_router)
    app.include_router(wms_router, prefix="/api/v1")
    app.include_router(inventory_router, prefix="/api/v1")
    app.include_router(inventory_advanced_router, prefix="/api/v1")
    app.include_router(inventory_counts_router, prefix="/api/v1")
    app.include_router(outbound_router, prefix="/api/v1")
    app.include_router(quality_router, prefix="/api/v1")
    app.include_router(ops_router, prefix="/api/v1")
    app.include_router(purchase_router, prefix="/api/v1")
    app.include_router(purchase_advanced_router, prefix="/api/v1")
    app.include_router(mfg_router, prefix="/api/v1")
    app.include_router(mfg_advanced_router, prefix="/api/v1")
    app.include_router(sales_router, prefix="/api/v1")
    app.include_router(sales_advanced_router, prefix="/api/v1")
    app.include_router(group_router, prefix="/api/v1")
    app.include_router(accounting_router, prefix="/api/v1")
    app.include_router(hr_router, prefix="/api/v1")

    return app


app = create_app()
