"""Entry point. On Vercel: the WSGI `app` (static pages in public/ are served by Vercel directly).
Locally / under PM2: python app.py [port]  -> serves the site and the app on 127.0.0.1."""
import os, sys
from gauge.web import app, main  # noqa: F401

if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else os.environ.get("PORT", 6900))
