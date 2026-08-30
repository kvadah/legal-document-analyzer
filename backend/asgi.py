"""ASGI entry point for the application."""
from app.main import app

if __name__ == "__main__":
    import uvicorn

    uvicorn.run("asgi:app", host="0.0.0.0", port=8000, reload=True)
