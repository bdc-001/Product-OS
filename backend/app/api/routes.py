"""Compatibility shim — domain routers live in app.api.routers."""

from app.api.routers import router

__all__ = ["router"]
