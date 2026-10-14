"""Neural network lab: the pieces of a network you can check by hand, and a tiny network you can train in a second.

Built: a single neuron (weights, threshold, activation), parameter counting, a small multi-layer network trained with
forward pass, loss and backpropagation (numpy, fixed seed), and a convolution you can see.
Not built: GPUs, image or speech models, transformers. Those need frameworks and hardware this app does not have.
"""
from __future__ import annotations

import math

import numpy as np


class NnError(Exception):
    pass


def _f(v, name, lo=-1e6, hi=1e6) -> float:
    try:
        x = float(v)
    except (TypeError, ValueError):
        raise NnError(f"{name} must be a number.") from None
    if not math.isfinite(x) or not lo <= x <= hi:
        raise NnError(f"{name} must be between {lo:g} and {hi:g}.")
    return x


ACTIVATIONS = {
    "step": ("Step", "1 if the sum is above zero, else 0. The original perceptron. Not smooth, so it can't be trained by gradients.", lambda z: np.where(z > 0, 1.0, 0.0)),
    "sigmoid": ("Sigmoid", "Squashes any number into 0 to 1. Good for a probability at the output.", lambda z: 1 / (1 + np.exp(-np.clip(z, -60, 60)))),
    "tanh": ("Tanh", "Squashes into -1 to 1, centred on zero.", np.tanh),
    "relu": ("ReLU", "0 for negatives, the value itself for positives. The usual choice inside deep networks.", lambda z: np.maximum(0, z)),
    "linear": ("Linear", "Passes the value through. Used for regression outputs.", lambda z: z),
}


def neuron(inputs, weights, threshold, activation="step") -> dict:
    xs = [_f(v, "Each input") for v in (inputs or [])]
    ws = [_f(v, "Each weight") for v in (weights or [])]
    if not xs or len(xs) != len(ws) or len(xs) > 20:
        raise NnError("Give the same number of inputs and weights (1 to 20).")
    if activation not in ACTIVATIONS:
        raise NnError("Unknown activation.")
    th = _f(threshold, "The threshold")
    parts = [x * w for x, w in zip(xs, ws)]
    z = sum(parts) - th
    out = float(ACTIVATIONS[activation][2](np.array(z)))
    return {"products": [round(p, 6) for p in parts], "weighted_sum": round(sum(parts), 6), "threshold": th, "z": round(z, 6), "output": round(out, 6),
            "decision": bool(out > 0.5) if activation in ("step", "sigmoid") else None,
            "text": f"sum of input x weight = {sum(parts):g}; minus threshold {th:g} = {z:g}; {ACTIVATIONS[activation][0]} gives {out:.4g}.",
            "lesson": "A neuron multiplies each input by a weight, adds them, subtracts a threshold (the bias) and passes the result through an activation function. A larger weight makes that input matter more."}


def parameter_count(layers) -> dict:
    ls = [int(v) for v in (layers or [])]
    if len(ls) < 2 or len(ls) > 12 or any(v < 1 or v > 100000 for v in ls):
        raise NnError("Give 2 to 12 layer sizes, each between 1 and 100000: input, hidden layers, output.")
    rows, total = [], 0
    for i in range(1, len(ls)):
        w, b = ls[i - 1] * ls[i], ls[i]
        rows.append({"from": ls[i - 1], "to": ls[i], "weights": w, "biases": b})
        total += w + b
    hidden = len(ls) - 2
    return {"layers": ls, "layer_count": len(ls), "hidden_layers": hidden, "connections": rows, "parameters": total,
            "kind": "perceptron (no hidden layer)" if hidden == 0 else "feed-forward, one hidden layer" if hidden == 1 else "deep feed-forward",
            "deep": len(ls) > 3,
            "note": "The course calls a network deep when it has more than three layers counting input and output. Other texts say two or more hidden layers: the line is a convention, not a law.",
            "lesson": "Each connection has a weight and each neuron has a bias; training adjusts every one of them."}


DATASETS = {
    "and": ([[0, 0], [0, 1], [1, 0], [1, 1]], [0, 0, 0, 1], "AND: 1 only when both inputs are 1. Linearly separable."),
    "or": ([[0, 0], [0, 1], [1, 0], [1, 1]], [0, 1, 1, 1], "OR: 1 when either input is 1. Linearly separable."),
    "xor": ([[0, 0], [0, 1], [1, 0], [1, 1]], [0, 1, 1, 0], "XOR: 1 when exactly one input is 1. Not linearly separable: no single straight line splits it."),
}


def train_mlp(dataset="xor", hidden=(4,), activation="tanh", epochs=2000, lr=0.5, seed=1) -> dict:
    if dataset not in DATASETS:
        raise NnError("Unknown dataset.")
    hid = [int(h) for h in (hidden or [])]
    if len(hid) > 3 or any(h < 1 or h > 16 for h in hid):
        raise NnError("Use up to 3 hidden layers of 1 to 16 neurons each (or none).")
    if activation not in ("sigmoid", "tanh", "relu"):
        raise NnError("Hidden activation must be sigmoid, tanh or relu.")
    ep = int(_f(epochs, "Epochs", 1, 5000))
    rate = _f(lr, "Learning rate", 0.001, 5)
    X0, y0, desc = DATASETS[dataset]
    X, y = np.array(X0, float), np.array(y0, float).reshape(-1, 1)
    rng = np.random.default_rng(int(seed))
    sizes = [2] + hid + [1]
    W = [rng.normal(0, 1, (sizes[i], sizes[i + 1])) * math.sqrt(1 / sizes[i]) for i in range(len(sizes) - 1)]
    B = [np.zeros((1, s)) for s in sizes[1:]]
    act = ACTIVATIONS[activation][2]

    def d_act(a):
        return {"sigmoid": a * (1 - a), "tanh": 1 - a * a, "relu": (a > 0).astype(float)}[activation]

    def forward():
        a, acts = X, [X]
        for i in range(len(W)):
            z = a @ W[i] + B[i]
            a = (1 / (1 + np.exp(-np.clip(z, -60, 60)))) if i == len(W) - 1 else act(z)
            acts.append(a)
        return acts

    def loss_of(p):
        p = np.clip(p, 1e-9, 1 - 1e-9)
        return float(-np.mean(y * np.log(p) + (1 - y) * np.log(1 - p)))

    curve, first = [], None
    for e in range(ep):
        acts = forward()
        L = loss_of(acts[-1])
        if e % max(1, ep // 40) == 0 or e == ep - 1:
            curve.append({"epoch": e, "loss": round(L, 5)})
        delta = (acts[-1] - y) / len(X)               # sigmoid + cross-entropy: the error at the output
        grads = []
        for i in range(len(W) - 1, -1, -1):             # backward pass
            grads.append((i, acts[i].T @ delta, delta.sum(0, keepdims=True)))
            if i > 0:
                delta = (delta @ W[i].T) * d_act(acts[i])
        if e == 0:
            first = {"loss": round(L, 5), "outputs": [round(float(v), 4) for v in acts[-1].ravel()], "gradient_size": round(float(sum(np.abs(g[1]).sum() for g in grads)), 5)}
        for i, gw, gb in grads:
            W[i] -= rate * gw
            B[i] -= rate * gb
    p = forward()[-1].ravel()
    preds = [{"input": X0[i], "expected": y0[i], "output": round(float(p[i]), 4), "predicted": int(p[i] > 0.5), "right": int(p[i] > 0.5) == y0[i]} for i in range(4)]
    acc = sum(1 for r in preds if r["right"]) / 4
    n_par = sum(w.size for w in W) + sum(b.size for b in B)
    msg = ("Learned it: every case is right." if acc == 1 else
           "Stuck at about 50%: with no hidden layer the network is a single straight line, and XOR can't be separated by one line. Add a hidden layer." if dataset == "xor" and not hid else
           "Not there yet: try more epochs, a different learning rate or more hidden neurons.")
    return {"dataset": dataset, "description": desc, "layers": sizes, "parameters": n_par, "activation": activation, "epochs": ep, "learning_rate": rate, "loss_curve": curve,
            "first_step": first, "final_loss": curve[-1]["loss"], "predictions": preds, "accuracy": acc, "message": msg,
            "lesson": "Training repeats three steps: a forward pass computes an output, the loss measures how far it is from the answer, and backpropagation sends the error backwards to nudge every weight and bias so the loss shrinks."}


IMAGES = {
    "square": ([[0, 0, 0, 0, 0, 0, 0, 0], [0, 0, 0, 0, 0, 0, 0, 0], [0, 0, 9, 9, 9, 9, 0, 0], [0, 0, 9, 9, 9, 9, 0, 0], [0, 0, 9, 9, 9, 9, 0, 0], [0, 0, 9, 9, 9, 9, 0, 0], [0, 0, 0, 0, 0, 0, 0, 0], [0, 0, 0, 0, 0, 0, 0, 0]], "A bright square on a dark background."),
    "stripes": ([[0, 9, 0, 9, 0, 9, 0, 9]] * 8, "Vertical stripes."),
}
KERNELS = {
    "vertical_edges": ([[-1, 0, 1], [-2, 0, 2], [-1, 0, 1]], "Responds where brightness changes from left to right."),
    "horizontal_edges": ([[-1, -2, -1], [0, 0, 0], [1, 2, 1]], "Responds where brightness changes from top to bottom."),
    "blur": ([[1 / 9] * 3] * 3, "Averages each pixel with its neighbours."),
    "sharpen": ([[0, -1, 0], [-1, 5, -1], [0, -1, 0]], "Boosts a pixel against its neighbours."),
    "identity": ([[0, 0, 0], [0, 1, 0], [0, 0, 0]], "Leaves the image unchanged."),
}


def convolve(image="square", kernel="vertical_edges") -> dict:
    if image not in IMAGES or kernel not in KERNELS:
        raise NnError("Unknown image or kernel.")
    img, k = np.array(IMAGES[image][0], float), np.array(KERNELS[kernel][0], float)
    h, w = img.shape
    out = np.array([[float((img[i:i + 3, j:j + 3] * k).sum()) for j in range(w - 2)] for i in range(h - 2)])
    return {"image": IMAGES[image][0], "kernel": [[round(float(v), 3) for v in r] for r in k], "output": [[round(float(v), 2) for v in r] for r in out],
            "image_note": IMAGES[image][1], "kernel_note": KERNELS[kernel][1],
            "lesson": "A convolutional neural network slides small kernels like this over an image. The difference is that it learns the kernel values during training instead of having them written by hand."}


def reference() -> dict:
    return {"activations": [{"id": k, "name": v[0], "what": v[1]} for k, v in ACTIVATIONS.items()], "datasets": [{"id": k, "what": v[2]} for k, v in DATASETS.items()],
            "images": [{"id": k, "what": v[1]} for k, v in IMAGES.items()], "kernels": [{"id": k, "what": v[1]} for k, v in KERNELS.items()],
            "types": [
                {"name": "Perceptron", "what": "The simplest network: input and output layers only. Can only draw a straight dividing line."},
                {"name": "Feed-forward", "what": "Information flows one way, input to output."},
                {"name": "Deep feed-forward", "what": "A feed-forward network with more than one hidden layer."},
                {"name": "Modular", "what": "Several networks whose outputs are combined."},
                {"name": "Convolutional (CNN)", "what": "Slides learned kernels over data; the standard choice for images."},
                {"name": "Recurrent (RNN)", "what": "Feeds earlier outputs back in, so it can use context in sequences such as text."},
                {"name": "Transformer", "what": "Uses attention instead of recurrence; the basis of today's large language models."}],
            "not_built": ["Training CNNs, RNNs or transformers on real images, audio or text: that needs GPUs and frameworks such as PyTorch.",
                          "Generative models (GANs, VAEs, diffusion): too heavy to train here; the Reference tab explains how they work."]}
