import os
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

load_dotenv(Path(__file__).parent / ".env")

from database import Base, engine, DATABASE_URL, SessionLocal
from routers import results, scrape, admin, stats

Base.metadata.create_all(bind=engine)

app = FastAPI(title="Triathlon Club Results")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(scrape.router, prefix="/api")
app.include_router(results.router, prefix="/api")
app.include_router(admin.router, prefix="/api")
app.include_router(stats.router, prefix="/api")


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.delete("/api/test/reset")
def test_reset():
    """Truncate all results — only allowed when using SQLite (test environment)."""
    if not DATABASE_URL.startswith("sqlite"):
        from fastapi import HTTPException
        raise HTTPException(status_code=403, detail="Reset only allowed in SQLite test mode.")
    from models import Result, PendingProvider
    db = SessionLocal()
    try:
        db.query(Result).delete()
        db.query(PendingProvider).delete()
        db.commit()
        return {"reset": True}
    finally:
        db.close()
