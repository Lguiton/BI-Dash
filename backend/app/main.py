from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import cors_origins
from app.routers import ai, analytics, apache, charts, dataset, export, glossary, ingest, kpis, ml, pipeline, progress, python_lab, quality, report, scd, sql, tracks
from app.services import study
from app.services.db import close_connection, init_bi_schema


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_bi_schema()
    scd.ensure_tables()
    kpis.ensure_table()
    study.ensure_tables()
    yield
    close_connection()


app = FastAPI(title="BI Analytics Engine", version="2.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins(),
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

app.include_router(analytics.router)
app.include_router(charts.router)
app.include_router(dataset.router)
app.include_router(ingest.router)
app.include_router(sql.router)
app.include_router(export.router)
app.include_router(apache.router)
app.include_router(scd.router)
app.include_router(kpis.router)
app.include_router(quality.router)
app.include_router(report.router)
app.include_router(python_lab.router)
app.include_router(ml.router)
app.include_router(ai.router)
app.include_router(tracks.router)
app.include_router(progress.router)
app.include_router(glossary.router)
app.include_router(pipeline.router)


@app.get("/health")
def health():
    return {"status": "healthy", "engine": "DuckDB"}
