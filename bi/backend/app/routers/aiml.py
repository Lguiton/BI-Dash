"""AI fundamentals lab endpoints: neural networks, NLP, machine learning concepts."""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.services import ml_concepts as mc
from app.services import nlp_lab as nl
from app.services import nn_lab as nn

router = APIRouter(prefix="/api/aiml", tags=["ai-fundamentals"])


def _w(fn, *a, **k):
    try:
        return fn(*a, **k)
    except (mc.MlcError, nl.NlpError, nn.NnError) as e:
        raise HTTPException(400, str(e)) from e


class TextIn(BaseModel):
    text: str = Field(max_length=3000)


class NeuronIn(BaseModel):
    inputs: list[float] = Field(max_length=20)
    weights: list[float] = Field(max_length=20)
    threshold: float = 0
    activation: str = "step"


class LayersIn(BaseModel):
    layers: list[int] = Field(max_length=12)


class TrainIn(BaseModel):
    dataset: str = "xor"
    hidden: list[int] = Field(default_factory=lambda: [4], max_length=3)
    activation: str = "tanh"
    epochs: int = 2000
    lr: float = 0.5


class ConvIn(BaseModel):
    image: str = "square"
    kernel: str = "vertical_edges"


class RulesIn(BaseModel):
    n: int = 600
    max_depth: int = 3


class SplitIn(BaseModel):
    n: int
    train: float = 60
    val: float = 20
    test: float = 20


class MetricsIn(BaseModel):
    tp: int
    fp: int
    fn: int
    tn: int


class KmIn(BaseModel):
    points: list[list[float]] | None = Field(default=None, max_length=500)
    k: int = 3


class RlIn(BaseModel):
    episodes: int = 400
    alpha: float = 0.5
    gamma: float = 0.9
    epsilon: float = 0.2


class ThermoIn(BaseModel):
    setpoint: float = 21
    outside: float = 10
    hours: int = 12
    proactive: bool = False


class RpaIn(BaseModel):
    rule_based: bool = False
    digital: bool = False
    repetitive: bool = False
    structured_input: bool = False
    stable_screens: bool = False
    volume_per_month: int = 0
    minutes_each: float = 0


class ApproachIn(BaseModel):
    task: str
    labeled_data: str = "some"
    data_size: str = "medium"
    need_explain: bool = False
    unstructured: bool = False


class ClfIn(BaseModel):
    examples: list[dict] = Field(max_length=300)
    tests: list[str] = Field(default_factory=list, max_length=20)


class BotIn(BaseModel):
    intents: list[dict] = Field(max_length=30)
    utterance: str = Field(max_length=300)
    threshold: float = 0.25


class RagIn(BaseModel):
    docs: list[str] = Field(max_length=100)
    question: str = Field(max_length=300)
    k: int = 2
    min_score: float = 0.1


@router.get("")
def concepts():
    return {**mc.reference(), "nn": nn.reference(), "nlp": nl.reference()}


@router.post("/neuron")
def neuron(b: NeuronIn):
    return _w(nn.neuron, b.inputs, b.weights, b.threshold, b.activation)


@router.post("/params")
def params(b: LayersIn):
    return _w(nn.parameter_count, b.layers)


@router.post("/train")
def train(b: TrainIn):
    return _w(nn.train_mlp, b.dataset, b.hidden, b.activation, b.epochs, b.lr)


@router.post("/convolve")
def convolve(b: ConvIn):
    return _w(nn.convolve, b.image, b.kernel)


@router.post("/rules")
def rules(b: RulesIn):
    return _w(mc.learn_rules, b.n, b.max_depth)


@router.post("/split")
def split(b: SplitIn):
    return _w(mc.split_sizes, b.n, b.train, b.val, b.test)


@router.post("/metrics")
def metrics(b: MetricsIn):
    return _w(mc.metrics, b.tp, b.fp, b.fn, b.tn)


@router.post("/kmeans")
def kmeans(b: KmIn):
    return _w(mc.kmeans, b.points, b.k)


@router.post("/qlearning")
def qlearning(b: RlIn):
    return _w(mc.q_learning, b.episodes, b.alpha, b.gamma, b.epsilon)


@router.post("/thermostat")
def thermostat(b: ThermoIn):
    return _w(mc.thermostat, b.setpoint, b.outside, b.hours, b.proactive)


@router.post("/rpa")
def rpa(b: RpaIn):
    return _w(mc.rpa_fit, b.rule_based, b.digital, b.repetitive, b.structured_input, b.stable_screens, b.volume_per_month, b.minutes_each)


@router.post("/approach")
def approach(b: ApproachIn):
    return _w(mc.choose_approach, b.task, b.labeled_data, b.data_size, b.need_explain, b.unstructured)


@router.post("/nlp/tokens")
def tokens(b: TextIn):
    return _w(nl.tokenize, b.text)


@router.post("/nlp/stems")
def stems(b: TextIn):
    return _w(nl.stem_vs_lemma, b.text)


@router.post("/nlp/pos")
def pos(b: TextIn):
    return _w(nl.pos_tag, b.text)


@router.post("/nlp/entities")
def ents(b: TextIn):
    return _w(nl.entities, b.text)


@router.post("/nlp/sentiment")
def sent(b: TextIn):
    return _w(nl.sentiment, b.text)


@router.post("/nlp/spam")
def spam(b: TextIn):
    return _w(nl.spam_check, b.text)


@router.post("/nlp/understand")
def understand(b: TextIn):
    return _w(nl.understand, b.text)


@router.post("/nlp/classify")
def classify(b: ClfIn):
    return _w(nl.train_classifier, b.examples, b.tests)


@router.post("/nlp/chatbot")
def chatbot(b: BotIn):
    return _w(nl.chatbot, b.intents, b.utterance, b.threshold)


@router.post("/nlp/rag")
def rag(b: RagIn):
    return _w(nl.rag, b.docs, b.question, b.k, b.min_score)
