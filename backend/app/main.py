import time
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import cors_origins
from app.routers import ai, analytics, apache, charts, data as data_router, dataset, export, glossary, ingest, kpis, ml, pipeline, progress, python_lab, quality, report, scd, sql, tracks, workspaces as workspaces_router, sources as sources_router, backups as backups_router, audit as audit_router, pm as pm_router, sysanalyst as sa_router, dba as dba_router, fullstack as fs_router, company as company_router, agents as agents_router, alerts as alerts_router, compare as compare_router, search as search_router, hub as hub_router, workflows as workflows_router, dq as dq_router, pipelines as pipelines_router, models as models_router, security as security_router, extras as extras_router, more as more_router, net as net_router, it as it_router, system as system_router, stats as stats_router, cookbook as cookbook_router, relational as relational_router, se as se_router, aiml as aiml_router, aieng as aieng_router, mlops as mlops_router, aplus as aplus_router, itfund as itfund_router, itshell as itshell_router, itdrills as itdrills_router, bitools as bitools_router, netgen as netgen_router, honeypot as honeypot_router, endpoint as endpoint_router, learnpath as learnpath_router, infra as infra_router, review as review_router, portfolio as portfolio_router, frames as frames_router, aigov as aigov_router, infoaudit as infoaudit_router, aiimpl as aiimpl_router, lessons2 as lessons2_router, cpe as cpe_router, cpesim as cpesim_router, netsim as netsim_router, sectools as sectools_router, datalab as datalab_router, mlbuild as mlbuild_router, backuplab as backuplab_router, itagent as itagent_router, authr as authr_router, bizpacks as bizpacks_router, briefing as briefing_router, healthcheck as healthcheck_router, services_list as services_list_router, mlhand as mlhand_router, nlpdl as nlpdl_router, mlstudio as mlstudio_router, intake as intake_router, code as code_router, sysdesign as sysdesign_router, clients as clients_router, sectrack as sectrack_router, toolbox as toolbox_router, fieldbox as fieldbox_router, fieldpacks as fieldpacks_router, fixlog as fixlog_router, worklog as worklog_router, jobs as jobs_router, auto as auto_router, howto as howto_router, checklists as checklists_router, money as money_router, leads as leads_router, clientnotes as clientnotes_router, bizbackup as bizbackup_router, today as today_router, knownissues as knownissues_router, workteam as workteam_router
from app.services import aida, guard, metrics, sources, state, workspaces
from app.services import auth as auth_service
from app.services.db import close_connection


@asynccontextmanager
async def lifespan(_: FastAPI):
    auth_service.init()
    workspaces.startup()
    scheduler = sources.Scheduler()
    scheduler.start()
    aida_task = aida.start()  # status to Project AIDA once a minute; does nothing unless AIDA_INTAKE_* are set
    yield
    scheduler.stop()
    await aida.stop(aida_task)
    close_connection()
    state.close_all()


app = FastAPI(title="BI Analytics Engine", version="2.0.0", lifespan=lifespan)


@app.exception_handler(Exception)
async def _unexpected_error(request, exc):
    """A request failed with an error nobody handled: tell Project AIDA (class name and code location only), answer a plain 500."""
    from fastapi.responses import JSONResponse
    aida.report_error(exc, request.method, aida.route_template(request))
    return JSONResponse({"detail": "Internal Server Error"}, status_code=500)

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


@app.middleware("http")
async def _guard(request, call_next):
    """Always on, with or without the login: wrong Host names and other websites' writes are refused, and every answer carries security headers."""
    from fastapi.responses import JSONResponse
    h = request.headers
    if not guard.host_ok(h.get("host")):
        return JSONResponse({"detail": "Blocked: unknown host name. Use http://localhost."}, status_code=400)
    if not guard.origin_ok(request.method, h.get("origin"), h.get("host"), cors_origins(), h.get("sec-fetch-site")):
        state.audit("blocked_cross_site", f"{request.method} {request.url.path} from {h.get('origin') or 'cross-site'}", ok=False)
        return JSONResponse({"detail": "Blocked: this request did not come from the dashboard."}, status_code=403)
    response = await call_next(request)
    for k, v in guard.HEADERS.items():
        response.headers.setdefault(k, v)
    if request.url.path.startswith("/api/auth"):
        response.headers["Cache-Control"] = "no-store"
    return response


@app.middleware("http")
async def _login_gate(request, call_next):
    """With BI_AUTH=1 every API call needs the owner's session cookie, and browsers may only change data from our own pages."""
    from fastapi.responses import JSONResponse
    from urllib.parse import urlparse
    if request.method != "OPTIONS" and auth_service.needs_login(request.url.path):
        if not auth_service.valid_token(request.cookies.get(auth_service.COOKIE)):
            return JSONResponse({"detail": "Sign in required."}, status_code=401)
        origin = request.headers.get("origin")
        if request.method not in ("GET", "HEAD") and origin and origin not in cors_origins() and urlparse(origin).netloc != request.headers.get("host"):
            return JSONResponse({"detail": "Blocked: this request did not come from the dashboard."}, status_code=403)
    return await call_next(request)


app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins(),
    allow_credentials=True,
    expose_headers=["Content-Disposition"],
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

app.include_router(authr_router.router)
app.include_router(bizpacks_router.router)
app.include_router(bizpacks_router.models_router)
app.include_router(briefing_router.router)
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
for _r in (money_router, leads_router, clientnotes_router, bizbackup_router, today_router):
    app.include_router(_r.router)
app.include_router(audit_router.router)
app.include_router(healthcheck_router.router)
app.include_router(services_list_router.router)
app.include_router(mlhand_router.router)
app.include_router(nlpdl_router.router)
app.include_router(mlstudio_router.router)
app.include_router(intake_router.router)
app.include_router(code_router.router)
app.include_router(sysdesign_router.router)
app.include_router(clients_router.router)
app.include_router(knownissues_router.router)
app.include_router(sectrack_router.router)
app.include_router(toolbox_router.router)
app.include_router(fieldbox_router.router)
app.include_router(fieldpacks_router.router)
app.include_router(fixlog_router.router)
app.include_router(worklog_router.router)
app.include_router(jobs_router.router)
app.include_router(workteam_router.router)
app.include_router(auto_router.router)
app.include_router(howto_router.router)
app.include_router(checklists_router.router)
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
app.include_router(aigov_router.router)
app.include_router(infoaudit_router.router)
app.include_router(aiimpl_router.router)
app.include_router(lessons2_router.router)
app.include_router(cpe_router.router)
app.include_router(cpesim_router.router)
app.include_router(netsim_router.router)
app.include_router(sectools_router.router)
app.include_router(datalab_router.router)
app.include_router(mlbuild_router.router)
app.include_router(backuplab_router.router)
app.include_router(itagent_router.router)
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
