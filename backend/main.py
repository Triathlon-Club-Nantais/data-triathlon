from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

load_dotenv(Path(__file__).parent / ".env")

from database import Base, engine
from routers import results, scrape

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


@app.get("/api/health")
def health():
    return {"status": "ok"}
