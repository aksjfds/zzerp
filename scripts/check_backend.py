"""Import the backend application and report its registered API routes."""

from __future__ import annotations

import os
from pathlib import Path
import sys


ROOT_DIR = Path(__file__).resolve().parents[1]
BACKEND_SRC = ROOT_DIR / "backend" / "src"

if sys.version_info < (3, 10):
    raise RuntimeError("zzerp backend requires Python 3.10 or newer")

os.environ.setdefault("APP_ENV", "development")
sys.path.insert(0, str(BACKEND_SRC))
sys.path.insert(0, str(ROOT_DIR))

from main import app  # noqa: E402


routes = sorted(
    (
        route.path,
        ",".join(sorted(route.methods or [])),
    )
    for route in app.routes
    if hasattr(route, "methods")
)

print(f"Imported {app.title!r} with {len(routes)} routes")
for path, methods in routes:
    print(f"{methods:16} {path}")
