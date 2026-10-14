"""AI engineering workbench endpoints."""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.services import ai_eng_lab as ae

router = APIRouter(prefix="/api/aieng", tags=["ai-engineering"])


def _w(fn, *a, **k):
    try:
        return fn(*a, **k)
    except ae.AieError as e:
        raise HTTPException(getattr(e, "status", 400), str(e)) from e


class TextIn(BaseModel):
    text: str = Field(max_length=2_000_000)


class FitIn(BaseModel):
    prompt_tokens: float
    window_tokens: float
    output_tokens: float = 1000
    safety_pct: float = 10


class ChunkIn(BaseModel):
    doc_tokens: float
    chunk_tokens: float = 300
    overlap_tokens: float = 40
    top_k: int = 3
    queries_per_day: float = 100
    price_in_per_million: float = 0
    question_tokens: float = 40
    system_tokens: float = 200


class RagIn(BaseModel):
    docs: list[str] = Field(max_length=50)
    cases: list[dict] = Field(max_length=100)
    chunk_sizes: list[int] = Field(default_factory=lambda: [200, 400, 800], max_length=5)
    k: int = 3
    min_score: float = 0.12


class ToolsIn(BaseModel):
    tools: list[dict] = Field(max_length=40)


class SaveIn(BaseModel):
    name: str = Field(max_length=50)
    text: str = Field(max_length=8000)
    note: str = Field(default="", max_length=200)


class DiffIn(BaseModel):
    name: str = Field(max_length=50)
    a: int
    b: int


class CmpIn(BaseModel):
    cases: list[dict] = Field(max_length=100)
    outputs_a: dict
    outputs_b: dict


class LiveIn(BaseModel):
    name: str = Field(max_length=50)
    a: int
    b: int | None = None
    cases: list[dict] = Field(max_length=20)
    provider: str = "auto"
    confirm: bool = False


class CostIn(BaseModel):
    requests_per_day: float
    input_tokens: float
    output_tokens: float
    price_in_per_million: float
    price_out_per_million: float
    cache_hit_pct: float = 0
    cache_discount_pct: float = 90
    cheap_share_pct: float = 0
    cheap_price_in: float = 0
    cheap_price_out: float = 0
    days: int = 30


@router.get("")
def reference():
    return ae.reference()


@router.post("/tokens")
def tokens(b: TextIn):
    return _w(ae.estimate_tokens, b.text)


@router.post("/fit")
def fit(b: FitIn):
    return _w(ae.context_fit, b.prompt_tokens, b.window_tokens, b.output_tokens, b.safety_pct)


@router.post("/chunks")
def chunks(b: ChunkIn):
    return _w(ae.chunk_plan, **b.model_dump())


@router.post("/rag-eval")
def rag_eval(b: RagIn):
    return _w(ae.rag_eval, b.docs, b.cases, b.chunk_sizes, b.k, b.min_score)


@router.post("/tool-safety")
def tool_safety(b: ToolsIn):
    return _w(ae.tool_safety, b.tools)


@router.get("/prompts")
def prompts():
    return ae.prompts()


@router.get("/prompts/{name}/{version}")
def prompt_get(name: str, version: int):
    return _w(ae.prompt_get, name, version)


@router.post("/prompts")
def prompt_save(b: SaveIn):
    return _w(ae.prompt_save, b.name, b.text, b.note)


@router.delete("/prompts/{name}")
def prompt_delete(name: str):
    return _w(ae.prompt_delete, name)


@router.post("/prompts/diff")
def prompt_diff(b: DiffIn):
    return _w(ae.prompt_diff, b.name, b.a, b.b)


@router.post("/prompts/compare")
def compare(b: CmpIn):
    return _w(ae.compare_versions, b.cases, b.outputs_a, b.outputs_b)


@router.post("/live/plan")
def live_plan(b: LiveIn):
    return _w(ae.live_plan, b.name, b.a, b.b, b.cases)


@router.post("/live/run")
def live_run(b: LiveIn):
    return _w(ae.live_run, b.name, b.a, b.b, b.cases, b.provider, b.confirm)


@router.get("/live/history")
def live_history():
    return {"runs": ae.live_history()}


@router.post("/cost")
def cost(b: CostIn):
    return _w(ae.cost_plan, **b.model_dump())
