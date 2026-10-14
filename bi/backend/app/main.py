import time
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import cors_origins
from app.routers import ai, analytics, apache, charts, data as data_router, dataset, export, glossary, ingest, kpis, ml, pipeline, progress, python_lab, quality, report, scd, sql, tracks, workspaces as workspaces_router, sources as sources_router, backups as backups_router, audit as audit_router, pm as pm_router, sysanalyst as sa_router, dba as dba_router, fullstack as fs_router, company as company_router, agents as agents_router, alerts as alerts_router, compare as compare_router, search as search_router, hub as hub_router, workflows as workflows_router, dq as dq_router, pipelines as pipelines_router, models as models_router, security as security_router, extras as extras_router, more as more_router, net as net_router, it as it_router, system as system_router, stats as stats_router, cookbook as cookbook_router, relational as relational_router, se as se_router, aiml as aiml_router, aieng as aieng_router, mlops as mlops_router, aplus as aplus_router, itfund as itfund_router, itshell as itshell_router, itdrills as itdrills_router, bitools as bitools_router, netgen as netgen_router, honeypot as honeypot_router, endpoint as endpoint_router, learnpath as learnpath_router, infra as infra_router, review as review_router, portfolio as portfolio_router, frames as frames_router
from app.services import metrics, sources, state, workspaces
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

@app.middleware("http")
async def _timing(request, call_next):
    t0 = time.perf_counter()
    status = 500
    try:
        response = await call_next(request)
        status = response.status_code
        return response
    finally:
        route = request.scope.get("route")
        metrics.record(request.method, getattr(route, "path", None) or "(no route)", status, time.perf_counter() - t0)


app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins(),
    allow_credentials=True,
    expose_headers=["Content-Disposition"],
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
app.include_router(alerts_router.router)
app.include_router(compare_router.router)
app.include_router(search_router.router)
app.include_router(hub_router.router)
app.include_router(workflows_router.router)
app.include_router(dq_router.router)
app.include_router(pipelines_router.router)
app.include_router(models_router.router)
app.include_router(security_router.router)
app.include_router(extras_router.router)
app.include_router(more_router.router)
app.include_router(net_router.router)
app.include_router(it_router.router)
app.include_router(system_router.router)
app.include_router(stats_router.router)
app.include_router(cookbook_router.router)
app.include_router(relational_router.router)
app.include_router(se_router.router)
app.include_router(aiml_router.router)
app.include_router(aieng_router.router)
app.include_router(mlops_router.router)
app.include_router(aplus_router.router)
app.include_router(itfund_router.router)
app.include_router(itshell_router.router)
app.include_router(itdrills_router.router)
app.include_router(bitools_router.router)
app.include_router(netgen_router.router)
app.include_router(honeypot_router.router)
app.include_router(endpoint_router.router)
app.include_router(learnpath_router.router)
app.include_router(infra_router.router)
app.include_router(frames_router.router)
app.include_router(review_router.router)
app.include_router(portfolio_router.router)


@app.get("/metrics", include_in_schema=False)
def prometheus_metrics():
    from fastapi.responses import PlainTextResponse
    return PlainTextResponse(metrics.prometheus(), media_type="text/plain; version=0.0.4")


@app.get("/api/ops", tags=["ops"])
def ops():
    return metrics.summary()


@app.get("/health")
def health():
    return {"status": "healthy", "engine": "DuckDB"}
