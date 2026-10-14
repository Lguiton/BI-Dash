"""Analysis Lab API: descriptive, diagnostic, predictive and prescriptive analysis on your own data."""
from typing import Literal

from fastapi import APIRouter, File, HTTPException, UploadFile
from pydantic import BaseModel, Field

from app.services import bigdata, cleaning, fileformats, mining, prescribe, qual, stats_basics, stats_infer
from app.services import stats_lab as sl
from app.services.datasets import DataError

router = APIRouter(prefix="/api/stats", tags=["analysis-lab"])

TYPES = [
    {"id": "descriptive", "label": "Descriptive: what happened?", "blurb": "Summarize the past with counts, averages, trends and filters."},
    {"id": "diagnostic", "label": "Diagnostic: why did it happen?", "blurb": "Find what moves with a result and where a change came from."},
    {"id": "predictive", "label": "Predictive: what might happen?", "blurb": "Project trends forward and estimate how likely things are."},
    {"id": "prescriptive", "label": "Prescriptive: what should we do?", "blurb": "Rank where effort pays most and which levers matter."},
]


def _g(fn, *a, **k):
    try:
        return fn(*a, **k)
    except DataError as e:
        raise HTTPException(e.status, e.message) from e


class Cond(BaseModel):
    column: str = Field(min_length=1, max_length=120)
    op: Literal["eq", "ne", "gt", "gte", "lt", "lte", "between", "in", "contains", "is_null", "not_null"] = "eq"
    value: str | float | int | bool | list[str] | None = None
    value2: str | float | int | None = None


class Base(BaseModel):
    source: str = Field(default=sl.OPS, min_length=1, max_length=120)
    filters: list[Cond] = Field(default_factory=list, max_length=sl.MAX_FILTERS)
    mode: Literal["and", "or"] = "and"

    def fl(self) -> list[dict]:
        return [c.model_dump() for c in self.filters]


class FilterIn(Base):
    preview: int = Field(default=15, ge=1, le=50)


class ProbIn(Base):
    event: Cond
    group_by: str | None = None
    given: Cond | None = None
    entity_col: str | None = None


class TsIn(Base):
    date_col: str
    value_col: str | None = None
    agg: Literal["sum", "avg", "count", "min", "max"] = "sum"
    bucket: Literal["day", "week", "month"] = "day"
    window: int | None = Field(default=None, ge=2, le=60)
    horizon: int = Field(default=0, ge=0, le=60)


class RegIn(Base):
    y: str
    x_numeric: list[str] = Field(default_factory=list, max_length=8)
    x_categorical: list[str] = Field(default_factory=list, max_length=8)
    predict: dict[str, str | float | int] | None = None


class DiagIn(Base):
    y: str
    group_col: str | None = None
    date_col: str | None = None
    split: str | None = None


class OppIn(Base):
    value_col: str
    group_col: str
    higher_is_better: bool = True
    benchmark: Literal["median", "top_quartile", "best"] = "median"
    min_rows: int = Field(default=5, ge=1, le=1000)
    levers_y: str | None = None
    levers: list[str] = Field(default_factory=list, max_length=8)


@router.get("/sources")
def get_sources():
    return {"types": TYPES, "sources": sl.sources()}


@router.post("/describe")
def post_describe(b: Base):
    return _g(sl.describe, b.source, b.fl(), b.mode)


@router.post("/filter")
def post_filter(b: FilterIn):
    return _g(sl.filter_report, b.source, b.fl(), b.mode, b.preview)


@router.post("/probability")
def post_probability(b: ProbIn):
    return _g(sl.probability, b.source, b.event.model_dump(), b.fl(), b.mode, b.group_by, b.given.model_dump() if b.given else None, b.entity_col)


@router.post("/timeseries")
def post_timeseries(b: TsIn):
    return _g(sl.timeseries, b.source, b.date_col, b.value_col, b.agg, b.bucket, b.fl(), b.mode, b.window, b.horizon)


@router.post("/regression")
def post_regression(b: RegIn):
    return _g(sl.regression, b.source, b.y, b.x_numeric, b.x_categorical, b.fl(), b.mode, b.predict)


@router.post("/diagnose")
def post_diagnose(b: DiagIn):
    return _g(sl.diagnose, b.source, b.y, b.group_col, b.date_col, b.split, b.fl(), b.mode)


@router.post("/opportunities")
def post_opportunities(b: OppIn):
    return _g(sl.opportunities, b.source, b.value_col, b.group_col, b.higher_is_better, b.benchmark, b.min_rows, b.fl(), b.mode, b.levers_y, b.levers)


class ArimaIn(Base):
    date_col: str
    value_col: str | None = None
    agg: Literal["sum", "avg", "count", "min", "max"] = "sum"
    bucket: Literal["day", "week", "month"] = "day"
    horizon: int = Field(default=14, ge=1, le=60)
    d: int = Field(default=1, ge=0, le=1)


class BizIn(Base):
    date_col: str
    revenue_col: str
    cost_col: str | None = None
    entity_col: str | None = None
    cash: float | None = Field(default=None, ge=0, le=1e12)


@router.post("/arima")
def post_arima(b: ArimaIn):
    return _g(sl.arima_forecast, b.source, b.date_col, b.value_col, b.agg, b.bucket, b.horizon, b.d, b.fl(), b.mode)


@router.post("/business")
def post_business(b: BizIn):
    return _g(sl.business_metrics, b.source, b.date_col, b.revenue_col, b.cost_col, b.entity_col, b.cash, b.fl(), b.mode)


# ------------------------------------------------------------------ qualitative notes and themes
class QualIn(BaseModel):
    kind: str = Field(min_length=1, max_length=20)
    title: str = Field(min_length=1, max_length=140)
    data: dict = Field(default_factory=dict)
    tags: list[str] = Field(default_factory=list, max_length=8)


class QualPatch(BaseModel):
    title: str | None = Field(default=None, max_length=140)
    data: dict | None = None
    tags: list[str] | None = Field(default=None, max_length=8)


class ThemesIn(BaseModel):
    text: str | None = Field(default=None, max_length=qual.MAX_TEXT_IN)
    source: str | None = None
    text_col: str | None = None
    include_notes: bool = False
    top: int = Field(default=15, ge=5, le=40)


@router.get("/qual")
def get_qual():
    return qual.list_items()


@router.post("/qual")
def post_qual(b: QualIn):
    return _g(qual.create, b.kind, b.title, b.data, b.tags)


@router.put("/qual/{item_id}")
def put_qual(item_id: str, b: QualPatch):
    return _g(qual.update, item_id, b.title, b.data, b.tags)


@router.delete("/qual/{item_id}")
def delete_qual(item_id: str):
    return _g(qual.delete, item_id)


@router.post("/themes")
def post_themes(b: ThemesIn):
    return _g(qual.themes, b.text, b.source, b.text_col, b.include_notes, b.top)


# ------------------------------------------------------------------ data mining and machine learning
class ClusterIn(Base):
    features: list[str] = Field(min_length=2, max_length=8)
    k: int | None = Field(default=None, ge=2, le=10)


class AssocIn(Base):
    basket_col: str
    item_col: str
    min_support_pct: float = Field(default=1.0, gt=0, le=100)
    min_confidence_pct: float = Field(default=30.0, ge=0, le=100)


class OutlierIn(Base):
    features: list[str] = Field(min_length=1, max_length=8)
    label_col: str | None = None
    top: int = Field(default=15, ge=1, le=50)


class PredictIn(Base):
    target: str
    x_numeric: list[str] = Field(default_factory=list, max_length=12)
    x_categorical: list[str] = Field(default_factory=list, max_length=12)
    model: str | None = None
    test_pct: int = Field(default=20, ge=10, le=50)
    positive: str | None = None
    case: dict[str, str | float | int] | None = None


@router.post("/cluster")
def post_cluster(b: ClusterIn):
    return _g(mining.cluster, b.source, b.features, b.k, b.fl(), b.mode)


@router.post("/associations")
def post_associations(b: AssocIn):
    return _g(mining.associations, b.source, b.basket_col, b.item_col, b.min_support_pct, b.min_confidence_pct, b.fl(), b.mode)


@router.post("/outliers")
def post_outliers(b: OutlierIn):
    return _g(mining.outliers, b.source, b.features, b.label_col, b.top, b.fl(), b.mode)


@router.post("/predict")
def post_predict(b: PredictIn):
    return _g(mining.predict, b.source, b.target, b.x_numeric, b.x_categorical, b.model, b.test_pct, b.positive, b.case, b.fl(), b.mode)


@router.get("/ml-models")
def get_ml_models():
    return mining.MODELS


# ------------------------------------------------------------------ prescriptive: goals and optimization
class GoalIn(Base):
    y: str
    target: float
    levers: list[str] = Field(min_length=1, max_length=8)


class AllocIn(Base):
    group_col: str
    return_col: str
    effort_col: str
    budget: float | None = Field(default=None, gt=0, le=1e12)
    min_mult: float = Field(default=0.5, ge=0, le=1)
    max_mult: float = Field(default=1.5, ge=1, le=5)
    min_rows: int = Field(default=10, ge=1, le=10000)


@router.post("/goal")
def post_goal(b: GoalIn):
    return _g(prescribe.goal_seek, b.source, b.y, b.target, b.levers, b.fl(), b.mode)


@router.post("/allocate")
def post_allocate(b: AllocIn):
    return _g(prescribe.optimize_allocation, b.source, b.group_col, b.return_col, b.effort_col, b.budget, b.min_mult, b.max_mult, b.min_rows, b.fl(), b.mode)


class BriefIn(Base):
    metric: str
    group_col: str | None = None
    date_col: str | None = None
    higher_is_better: bool = True


@router.post("/brief")
def post_brief(b: BriefIn):
    return _g(prescribe.brief, b.source, b.metric, b.group_col, b.date_col, b.higher_is_better, b.fl(), b.mode)


class CheckIn(Base):
    columns: list[str] = Field(min_length=1, max_length=12)
    date_col: str | None = None
    group_col: str | None = None


class TrackIn(Base):
    title: str = Field(min_length=1, max_length=140)
    action: str = Field(default="", max_length=500)
    metric: str
    date_col: str
    target: float | None = None
    baseline_days: int = Field(default=30, ge=7, le=365)


@router.post("/input-check")
def post_input_check(b: CheckIn):
    return _g(prescribe.input_check, b.source, b.columns, b.date_col, b.group_col, b.fl(), b.mode)


@router.get("/track")
def get_track():
    return {"items": prescribe.track_list()}


@router.post("/track")
def post_track(b: TrackIn):
    return _g(prescribe.track_add, b.title, b.source, b.metric, b.date_col, b.action, b.target, b.baseline_days, b.fl(), b.mode)


@router.delete("/track/{item_id}")
def delete_track(item_id: str):
    return _g(prescribe.track_delete, item_id)


# ------------------------------------------------------------------ big data practice
class BigIn(BaseModel):
    rows: int = Field(ge=10_000, le=bigdata.MAX_ROWS)


@router.get("/bigdata")
def get_bigdata():
    return bigdata.state()


@router.get("/bigdata/job")
def get_bigdata_job():
    return bigdata.job()


@router.post("/bigdata/generate")
def post_bigdata_generate(b: BigIn):
    return _g(bigdata.start_generate, b.rows)


@router.post("/bigdata/benchmark")
def post_bigdata_benchmark():
    return _g(bigdata.start_benchmark)


@router.delete("/bigdata")
def delete_bigdata():
    return _g(bigdata.cleanup)


@router.post("/themes/upload")
async def post_themes_upload(file: UploadFile = File(...), top: int = 15):
    """Find themes in a text file (.txt, .md, .log, .csv) or a PDF."""
    name = (file.filename or "").lower()
    raw = await file.read(10 * 1024 * 1024 + 1)
    if len(raw) > 10 * 1024 * 1024:
        raise HTTPException(413, "File is larger than 10 MB.")
    if not name.endswith((".txt", ".md", ".log", ".csv", ".pdf")):
        raise HTTPException(400, "Use a .txt, .md, .log, .csv or .pdf file.")
    top = max(5, min(40, top))
    def go():
        from app.services import datasets
        text = fileformats.pdf_text(raw) if name.endswith(".pdf") else datasets.decode(raw)
        return qual.themes(text=text[: qual.MAX_TEXT_IN], top=top)
    return _g(go)


# ------------------------------------------------------------------ data cleaning
class CleanIn(BaseModel):
    table: str = Field(min_length=1, max_length=120)
    new_table: str = Field(min_length=1, max_length=80)
    steps: list[dict] = Field(min_length=1, max_length=cleaning.MAX_STEPS)
    note: str = Field(default="", max_length=200)


@router.get("/clean/inspect")
def get_clean_inspect(table: str):
    return _g(cleaning.inspect, table)


class RollupIn(BaseModel):
    table: str = Field(min_length=1, max_length=120)
    entity_col: str = Field(min_length=1, max_length=120)
    new_table: str = Field(min_length=1, max_length=80)
    cohort: list[Cond] = Field(default_factory=list, max_length=sl.MAX_FILTERS)
    mode: Literal["and", "or"] = "and"
    note: str = Field(default="", max_length=200)


@router.post("/rollup")
def post_rollup(b: RollupIn):
    return _g(cleaning.rollup, b.table, b.entity_col, b.new_table, [c.model_dump() for c in b.cohort], b.mode, b.note)


@router.post("/clean")
def post_clean(b: CleanIn):
    return _g(cleaning.clean, b.table, b.new_table, b.steps, b.note)


# ------------------------------------------------------------------ descriptive and inferential statistics
class DistIn(Base):
    column: str
    bins: int = Field(default=20, ge=5, le=50)
    confidence: float = 0.95


class CompareIn(Base):
    value_col: str
    group_col: str
    groups: list[str] | None = Field(default=None, max_length=stats_infer.MAX_GROUPS)


class CorrIn(Base):
    columns: list[str] = Field(min_length=2, max_length=stats_infer.MAX_CORR)


@router.post("/distribution")
def post_distribution(b: DistIn):
    return _g(stats_infer.distribution, b.source, b.column, b.fl(), b.mode, b.bins, b.confidence)


@router.post("/compare")
def post_compare(b: CompareIn):
    return _g(stats_infer.compare, b.source, b.value_col, b.group_col, b.groups, b.fl(), b.mode)


@router.post("/correlation")
def post_correlation(b: CorrIn):
    return _g(stats_infer.correlate, b.source, b.columns, b.fl(), b.mode)


# ------------------------------------------------------------------ more data mining: decision tree, sequences
class TreeIn(Base):
    target: str
    x_numeric: list[str] = Field(default_factory=list, max_length=10)
    x_categorical: list[str] = Field(default_factory=list, max_length=10)
    max_depth: int = Field(default=3, ge=1, le=5)
    focus_class: str | None = Field(default=None, max_length=120)
    focus_cost: float = Field(default=1.0, ge=1, le=20)


class SeqIn(Base):
    entity_col: str
    event_col: str
    date_col: str
    top: int = Field(default=12, ge=3, le=30)
    collapse_repeats: bool = True


@router.post("/tree")
def post_tree(b: TreeIn):
    return _g(mining.decision_tree, b.source, b.target, b.x_numeric, b.x_categorical, b.max_depth, b.fl(), b.mode, b.focus_class, b.focus_cost)


@router.post("/sequences")
def post_sequences(b: SeqIn):
    return _g(mining.sequences, b.source, b.entity_col, b.event_col, b.date_col, b.top, b.collapse_repeats, b.fl(), b.mode)


# ------------------------------------------------------------------ statistics fundamentals
class FreqIn(Base):
    column: str
    top: int = Field(default=15, ge=3, le=40)


class CrossIn(Base):
    row_col: str
    col_col: str


class MeanTestIn(Base):
    column: str
    mu0: float
    alternative: Literal["two-sided", "greater", "less"] = "two-sided"
    alpha: float = Field(default=0.05, ge=0.001, le=0.2)
    sigma: float | None = Field(default=None, gt=0)


class SamplingIn(Base):
    column: str
    n: int = Field(default=30, ge=2, le=500)
    reps: int = Field(default=1000, ge=100, le=5000)


class MarginIn(BaseModel):
    sd: float = Field(gt=0)
    margin: float | None = Field(default=None, gt=0)
    n: int | None = Field(default=None, ge=2)
    confidence: float = 0.95
    population_sd_known: bool = True


@router.get("/variables")
def get_variables(source: str = sl.OPS):
    return _g(stats_basics.variable_types, source)


@router.post("/frequency")
def post_frequency(b: FreqIn):
    return _g(stats_basics.frequency, b.source, b.column, b.fl(), b.mode, b.top)


@router.post("/crosstab")
def post_crosstab(b: CrossIn):
    return _g(stats_basics.crosstab, b.source, b.row_col, b.col_col, b.fl(), b.mode)


@router.post("/meantest")
def post_meantest(b: MeanTestIn):
    return _g(stats_basics.test_mean, b.source, b.column, b.mu0, b.alternative, b.alpha, b.sigma, b.fl(), b.mode)


@router.post("/sampling")
def post_sampling(b: SamplingIn):
    return _g(stats_basics.sampling_demo, b.source, b.column, b.n, b.reps, b.fl(), b.mode)


@router.post("/margin")
def post_margin(b: MarginIn):
    return _g(stats_basics.margin_calc, b.sd, b.margin, b.n, b.confidence, b.population_sd_known)
