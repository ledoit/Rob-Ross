"""Run: python -m studio  (from robross-palette-engine root)."""

from __future__ import annotations

import os

import uvicorn

if __name__ == "__main__":
    host = os.environ.get("ROB_ROSS_STUDIO_HOST", "127.0.0.1")
    port = int(os.environ.get("ROB_ROSS_STUDIO_PORT", "8765"))
    uvicorn.run(
        "studio.app:app",
        host=host,
        port=port,
        reload=os.environ.get("ROB_ROSS_STUDIO_RELOAD", "").lower() in ("1", "true", "yes"),
    )
