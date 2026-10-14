"""Learning paths (ML, AI engineering) and the offline learning tools behind them."""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.services import ai_tools as at, learn_path as lp, ml_tools as mt

router = APIRouter(prefix="/api/learn", tags=["learn"])


def _w(fn, *a, **k):
    try:
        return fn(*a, **k)
    except lp.PathError as e:
        raise HTTPException(e.status, e.message) from e
    except (mt.MlToolError, at.AiToolError) as e:
        raise HTTPException(getattr(e, "status", 400), str(e)) from e


class DoneIn(BaseModel):
    done: bool


class GateIn(BaseModel):
    passed: bool


@router.get("/path/{track}")
def path(track: str):
    return _w(lp.path, track)


@router.put("/path/{track}/module/{mid}")
def module(track: str, mid: str, b: DoneIn):
    return _w(lp.set_module, track, mid, b.done)


@router.put("/path/{track}/gate/{level}")
def gate(track: str, level: str, b: GateIn):
    return _w(lp.set_gate, track, level, b.passed)


# ---- ML tools
class BvIn(BaseModel):
    n: int = 40
    noise: float = 0.3
    degrees: list[int] | None = None
    seed: int = 7


class GdIn(BaseModel):
    task: str = "linear"
    lr: float = 0.1
    steps: int = 100
    seed: int = 3


class ScIn(BaseModel):
    n: int = 300
    noise: float = 0.25
    k: int = 7
    depth: int = 4
    seed: int = 11


class ScoreIn(BaseModel):
    text: str = Field(max_length=2_000_000)
    fp_cost: float = 1.0
    fn_cost: float = 5.0


class LeakIn(BaseModel):
    csv: str = Field(max_length=3_100_000)
    target: str = Field(max_length=200)


@router.post("/ml/bias-variance")
def bias_variance(b: BvIn):
    return _w(mt.bias_variance, b.n, b.noise, b.degrees, b.seed)


@router.post("/ml/gradient-descent")
def grad(b: GdIn):
    return _w(mt.grad_descent, b.task, b.lr, b.steps, b.seed)


@router.post("/ml/scratch")
def scratch(b: ScIn):
    return _w(mt.scratch_compare, b.n, b.noise, b.k, b.depth, b.seed)


@router.post("/ml/scores")
def scores(b: ScoreIn):
    return _w(mt.score_report, b.text, b.fp_cost, b.fn_cost)


@router.post("/ml/leak")
def leak(b: LeakIn):
    return _w(mt.leak_check, b.csv, b.target)


@router.get("/ml/reference")
def ml_reference():
    return mt.reference()


# ---- AI tools
class RetIn(BaseModel):
    cases: list[dict] = Field(max_length=500)
    k: int = 5


class HybIn(BaseModel):
    docs: list = Field(max_length=500)
    query: str = Field(max_length=2000)
    k: int = 3
    rrf_k: int = 60
    mmr_lambda: float = 0.7


class SchemaIn(BaseModel):
    output: str = Field(max_length=200_000)
    schema_: dict = Field(alias="schema")


class TraceIn(BaseModel):
    steps: list[dict] = Field(max_length=500)
    max_steps: int = 12
    price_in_per_million: float = 0
    price_out_per_million: float = 0


class StatsIn(BaseModel):
    mode: str
    args: dict = {}


class FtIn(BaseModel):
    train: str = Field(max_length=5_100_000)
    test: str = Field(default="", max_length=5_100_000)


class LoraIn(BaseModel):
    params_b: float
    layers: int = 32
    hidden: int = 4096
    rank: int = 16
    targets: int = 4
    weight_bytes: float = 2
    tokens_m: float = 10
    epochs: int = 3
    gpu_tflops: float = 100
    mfu_pct: float = 30


class GuardIn(BaseModel):
    text: str = Field(max_length=200_000)


@router.post("/ai/retrieval")
def retrieval(b: RetIn):
    return _w(at.retrieval_metrics, b.cases, b.k)


@router.post("/ai/hybrid")
def hybrid(b: HybIn):
    return _w(at.hybrid_search, b.docs, b.query, b.k, b.rrf_k, b.mmr_lambda)


@router.post("/ai/schema")
def schema(b: SchemaIn):
    return _w(at.schema_check, b.output, b.schema_)


@router.post("/ai/trace")
def trace(b: TraceIn):
    return _w(at.agent_trace, b.steps, b.max_steps, b.price_in_per_million, b.price_out_per_million)


@router.post("/ai/eval-stats")
def eval_stats(b: StatsIn):
    return _w(at.eval_stats, b.mode, **b.args)


@router.post("/ai/reliability")
def reliability(b: StatsIn):
    return _w(at.reliability, b.mode, **b.args)


@router.post("/ai/finetune-data")
def finetune_data(b: FtIn):
    return _w(at.finetune_check, b.train, b.test)


@router.post("/ai/lora")
def lora(b: LoraIn):
    return _w(at.lora_calc, b.params_b, b.layers, b.hidden, b.rank, b.targets, b.weight_bytes, b.tokens_m, b.epochs, b.gpu_tflops, b.mfu_pct)


@router.post("/ai/guard")
def guard(b: GuardIn):
    return _w(at.guard_scan, b.text)


@router.get("/ai/reference")
def ai_reference():
    return at.reference()
