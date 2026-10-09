from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import cors_origins
from app.routers import ai, analytics, apache, charts, data as data_router, dataset, export, glossary, ingest, kpis, ml, pipeline, progress, python_lab, quality, report, scd, sql, tracks, workspaces as workspaces_router, sources as sources_router, backups as backups_router, audit as audit_router, pm as pm_router, sysanalyst as sa_router, dba as dba_router, fullstack as fs_router, company as company_router, agents as agents_router
from app.services import sources, state, workspaces
from app.services.db import close_connection


@asynccontextmanager
async def lifespan(_: FastAPI):
    workspaces.startup()
    scheduler = sources.Scheduler()
    scheduler.start()
    yield
    scheduler.stop()
    close_connection()
    state.close_all()


app = FastAPI(title="BI Analytics Engine", version="2.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins(),
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
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
app.include_router(workspaces_router.router)
app.include_router(data_router.router)
app.include_router(sources_router.router)
app.include_router(backups_router.router)
app.include_router(audit_router.router)
app.include_router(pm_router.router)
app.include_router(sa_router.router)
app.include_router(dba_router.router)
app.include_router(fs_router.router)
app.include_router(company_router.router)
app.include_router(agents_router.router)


@app.get("/health")
def health():
    return {"status": "healthy", "engine": "DuckDB"}
