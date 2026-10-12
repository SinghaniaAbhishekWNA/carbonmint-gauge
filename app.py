"""Vercel entry point: the WSGI demo app (gauge/web.py). Static pages in public/ are served by Vercel directly."""
from gauge.web import app  # noqa: F401
