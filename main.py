"""Uvicorn entry point."""

import uvicorn
from app.config import PORT
from app.web.app import create_app

app = create_app()

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=PORT, reload=True)
