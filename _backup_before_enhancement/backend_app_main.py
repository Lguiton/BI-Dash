from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routers import analytics
from app.services.db import init_bi_schema

app = FastAPI(title="BI Analytics Engine", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:3001",
        "http://localhost:3012",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
def startup_event():
    init_bi_schema()

app.include_router(analytics.router)

@app.get("/health")
def health():
    return {"status": "healthy", "engine": "DuckDB"}
