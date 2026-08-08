# app/middleware/__init__.py
"""
Middleware package for FastAPI application.

Available middleware:
- AuditMiddleware: Automatic HTTP request/response logging
"""

from .audit import AuditMiddleware

__all__ = ["AuditMiddleware"]
