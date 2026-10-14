"""Python libraries behind AI work: what each is for, whether it is installed here, and a tiny offline demo for each.

Demos use made-up data and never touch the network, a display or a GPU. A library that is not installed is reported with the
pip command, not treated as an error. Heavy or server-style libraries (Airflow, TensorFlow, Streamlit, Kivy, Selenium, LangChain)
are only checked for installation; the lesson says why.
"""
from __future__ import annotations

import importlib
import importlib.util
from importlib import metadata

# key, display, pip name, import name, area, good for, first exercise, in this app, docs
LIBS = [
    ("pandas", "pandas", "pandas", "pandas", "Data analysis and wrangling", "Tables in memory: clean, join, group, reshape.", "Load a CSV, fix the types, group by a column, find the top five.", "Analyst track; python_practice/02 and 03", "https://pandas.pydata.org/docs/"),
    ("numpy", "NumPy", "numpy", "numpy", "Scientific computing", "Fast arrays and maths; everything numeric is built on it.", "Make a 3x3 array, take the mean of each column, multiply by a vector.", "Scientist track", "https://numpy.org/doc/"),
    ("matplotlib", "Matplotlib", "matplotlib", "matplotlib", "Data visualisation", "Static charts you control completely.", "Plot a line and a bar chart on one figure and save it as a PNG.", "python_practice/06", "https://matplotlib.org/stable/"),
    ("bs4", "BeautifulSoup", "beautifulsoup4", "bs4", "Web scraping", "Read HTML and pull out tags and text. Respect robots.txt and the site's terms.", "Parse a small HTML string and list every link and its text.", "Web reader and web table tools in the app use the standard library parser", "https://www.crummy.com/software/BeautifulSoup/bs4/doc/"),
    ("sklearn", "scikit-learn", "scikit-learn", "sklearn", "Machine learning", "Classic models, splits, pipelines and scoring with one consistent API.", "Split data, fit a logistic regression, report accuracy against a baseline.", "ML track and ML tools", "https://scikit-learn.org/stable/"),
    ("cv2", "OpenCV", "opencv-python-headless", "cv2", "Computer vision", "Image reading, filtering, edges and classic vision.", "Make a grey image, blur it and find its edges.", "Taught only", "https://docs.opencv.org/"),
    ("torch", "PyTorch", "torch", "torch", "Deep learning", "Tensors and automatic gradients; the main research and increasingly production framework.", "Fit y = 2x + 1 with one parameter pair and a gradient step loop.", "ML and AI tracks teach it; no GPU here", "https://pytorch.org/docs/"),
    ("nltk", "NLTK", "nltk", "nltk", "Classic NLP", "Teaching toolkit for tokens, stemming and corpora. Modern NLP leans on spaCy and Transformers.", "Tokenise a sentence and count word frequencies.", "AI Lab text tools", "https://www.nltk.org/"),
    ("tensorflow", "TensorFlow", "tensorflow", "tensorflow", "Deep learning", "Google's framework, with Keras on top; common in mobile and edge deployment.", "Build a two-layer Keras model and read its summary.", "Taught only (large install)", "https://www.tensorflow.org/"),
    ("streamlit", "Streamlit", "streamlit", "streamlit", "Data apps", "Turn a script into a web app with widgets in a few lines.", "Write app.py with a slider and a chart, then run streamlit run app.py.", "Taught only (it runs its own server)", "https://docs.streamlit.io/"),
    ("fastapi", "FastAPI", "fastapi", "fastapi", "APIs and backends", "Typed Python web APIs with automatic docs. This app's backend uses it.", "Write one GET and one POST endpoint and call them with the test client.", "This app's backend; Full stack track", "https://fastapi.tiangolo.com/"),
    ("airflow", "Apache Airflow", "apache-airflow", "airflow", "Workflow orchestration", "Schedule and monitor pipelines of tasks (DAGs). It orchestrates work; it is not a general automation tool.", "Read apache_practice/airflow/dags/bi_etl_dag.py and name each task.", "apache_practice/airflow", "https://airflow.apache.org/docs/"),
    ("django", "Django", "django", "django", "Full-stack web", "Batteries-included web framework: ORM, admin, auth, templates.", "Follow the official polls tutorial through the admin page.", "Taught only", "https://docs.djangoproject.com/"),
    ("pyspark", "PySpark", "pyspark", "pyspark", "Big data processing", "Distributed data processing; needs Java. Overkill for data that fits in memory.", "Run apache_practice/spark/01_spark_basics.py.", "apache_practice/spark", "https://spark.apache.org/docs/latest/api/python/"),
    ("flask", "Flask", "flask", "flask", "Lightweight web", "Minimal web framework; you add what you need.", "Return JSON from one route and call it with the test client.", "Taught; FastAPI is used here", "https://flask.palletsprojects.com/"),
    ("kivy", "Kivy", "kivy", "kivy", "Cross-platform apps", "Touch-friendly GUI apps for desktop and mobile in Python. Needs a display. Tkinter and PyQt are the common desktop alternatives.", "Build a window with a button that changes a label.", "Not embedded (needs a display)", "https://kivy.org/doc/stable/"),
    ("boto3", "Boto3", "boto3", "boto3", "AWS automation", "Python SDK for AWS services. Never put keys in code; use roles or a credentials file.", "Sign a presigned URL offline, then (in a sandbox account) list one bucket.", "Taught only; needs an AWS account", "https://boto3.amazonaws.com/v1/documentation/api/latest/"),
    ("langchain", "LangChain", "langchain", "langchain", "LLM apps and agents", "One of several frameworks for chaining model calls, tools and retrieval. You can build the same with plain API calls.", "Call a model and a tool by hand first, then see what the framework saves.", "AI Engineering track builds the pieces by hand", "https://python.langchain.com/docs/"),
    ("selenium", "Selenium", "selenium", "selenium", "Browser automation and testing", "Drive a real browser. Playwright is the more modern alternative. Check a site's terms before automating it.", "Open a local HTML file, click a button and read the result.", "Taught; the app tests with Playwright", "https://www.selenium.dev/documentation/"),
]
EXTRA = [("spaCy", "spacy", "Modern NLP pipelines"), ("Hugging Face Transformers", "transformers", "Pretrained language and vision models"), ("Polars", "polars", "Faster dataframes"),
         ("XGBoost", "xgboost", "Strong tabular models"), ("MLflow", "mlflow", "Experiment tracking"), ("Pydantic", "pydantic", "Validation and structured output"), ("Playwright", "playwright", "Modern browser automation")]
KEYS = [l[0] for l in LIBS]


def _version(pip: str) -> str | None:
    try:
        return metadata.version(pip)
    except metadata.PackageNotFoundError:
        return None


def libraries() -> dict:
    rows = []
    for key, name, pip, imp, area, good, ex, inapp, docs in LIBS:
        v = _version(pip) or (_version("opencv-python") if key == "cv2" else None)
        rows.append({"key": key, "name": name, "area": area, "good_for": good, "first_exercise": ex, "in_this_app": inapp, "docs": docs,
                     "installed": v is not None, "version": v, "install": f"pip install {pip}", "has_demo": key in DEMOS})
    extra = [{"name": n, "install": f"pip install {p}", "for": f, "installed": _version(p) is not None} for n, p, f in EXTRA]
    return {"libraries": rows, "also_worth_knowing": extra, "installed": sum(1 for r in rows if r["installed"]), "total": len(rows),
            "note": "Install into your project's virtual environment, not globally."}


# ------------------------------------------------------------------ demos
def _d_pandas():
    import pandas as pd
    df = pd.DataFrame({"team": ["a", "b", "a", "b", "a"], "sales": [10, 20, 30, 40, 50]})
    return df.groupby("team")["sales"].agg(["sum", "mean"]).round(1).to_string()


def _d_numpy():
    import numpy as np
    a = np.arange(9).reshape(3, 3)
    return f"column means {a.mean(axis=0).tolist()}\nA @ [1,0,1] = {(a @ np.array([1, 0, 1])).tolist()}"


def _d_matplotlib():
    import io

    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(figsize=(3, 2))
    ax.plot([1, 2, 3], [2, 4, 3])
    ax.bar([1, 2, 3], [1, 2, 1])
    buf = io.BytesIO()
    fig.savefig(buf, format="png")
    plt.close(fig)
    return f"drew a line and a bar chart off-screen and encoded a PNG of {len(buf.getvalue())} bytes (it starts with {buf.getvalue()[1:4].decode()})"


def _d_bs4():
    from bs4 import BeautifulSoup
    html = '<p>See <a href="/a">first</a> and <a href="/b">second</a>.</p>'
    return "\n".join(f"{a.get_text()} -> {a['href']}" for a in BeautifulSoup(html, "html.parser").find_all("a"))


def _d_sklearn():
    import numpy as np
    from sklearn.dummy import DummyClassifier
    from sklearn.linear_model import LogisticRegression
    from sklearn.model_selection import train_test_split
    rng = np.random.default_rng(0)
    X = rng.normal(size=(200, 2))
    y = (X[:, 0] + 0.5 * X[:, 1] + rng.normal(scale=0.5, size=200) > 0).astype(int)
    Xt, Xv, yt, yv = train_test_split(X, y, random_state=0, stratify=y)
    return f"baseline accuracy {DummyClassifier().fit(Xt, yt).score(Xv, yv):.2f}, logistic regression {LogisticRegression().fit(Xt, yt).score(Xv, yv):.2f}"


def _d_cv2():
    import cv2
    import numpy as np
    img = np.zeros((20, 20), np.uint8)
    img[5:15, 5:15] = 255
    edges = cv2.Canny(cv2.GaussianBlur(img, (3, 3), 0), 50, 150)
    return f"20x20 image with a white square: {int((edges > 0).sum())} edge pixels found"


def _d_torch():
    import torch
    w = torch.zeros(1, requires_grad=True)
    b = torch.zeros(1, requires_grad=True)
    x = torch.linspace(-1, 1, 20)
    y = 2 * x + 1
    for _ in range(300):
        loss = ((w * x + b - y) ** 2).mean()
        loss.backward()
        with torch.no_grad():
            w -= 0.1 * w.grad
            b -= 0.1 * b.grad
            w.grad.zero_()
            b.grad.zero_()
    return f"learned w={w.item():.2f}, b={b.item():.2f} (target 2 and 1)"


def _d_nltk():
    from collections import Counter

    from nltk.tokenize import wordpunct_tokenize
    toks = [t.lower() for t in wordpunct_tokenize("The cat sat. The cat ran!") if t.isalpha()]
    return f"tokens {toks}\ncounts {dict(Counter(toks))}"


def _d_fastapi():
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    app = FastAPI()

    @app.get("/hi/{name}")
    def hi(name: str):
        return {"hello": name}
    r = TestClient(app).get("/hi/ada")
    return f"GET /hi/ada -> {r.status_code} {r.json()}"


def _d_flask():
    from flask import Flask, jsonify
    app = Flask(__name__)

    @app.get("/hi")
    def hi():
        return jsonify(hello="world")
    r = app.test_client().get("/hi")
    return f"GET /hi -> {r.status_code} {r.get_json()}"


def _d_boto3():
    import boto3
    from botocore.config import Config
    c = boto3.client("s3", region_name="us-east-1", aws_access_key_id="AKIAFAKEFAKEFAKE", aws_secret_access_key="fake", config=Config(signature_version="s3v4"))
    url = c.generate_presigned_url("get_object", Params={"Bucket": "demo", "Key": "a.txt"}, ExpiresIn=60)
    return f"signed a URL offline with fake keys; no request was made:\n{url.split('?')[0]}?... ({len(url)} characters)"


def _d_django():
    import django
    return f"Django {django.get_version()} is installed. A real project needs 'django-admin startproject', so follow the official tutorial."


def _d_pyspark():
    import pyspark
    return f"PySpark {pyspark.__version__} is installed. Starting a session needs Java 17+; run apache_practice/spark/01_spark_basics.py."


DEMOS = {"pandas": _d_pandas, "numpy": _d_numpy, "matplotlib": _d_matplotlib, "bs4": _d_bs4, "sklearn": _d_sklearn, "cv2": _d_cv2, "torch": _d_torch,
         "nltk": _d_nltk, "fastapi": _d_fastapi, "flask": _d_flask, "boto3": _d_boto3, "django": _d_django, "pyspark": _d_pyspark}
WHY_NO_DEMO = {"airflow": "Airflow needs its database and scheduler running. Read the example DAG in apache_practice instead.",
               "tensorflow": "TensorFlow is a large install and slow to import; the PyTorch demo shows the same idea of gradients.",
               "streamlit": "Streamlit runs its own server; run 'streamlit run app.py' yourself.",
               "kivy": "Kivy needs a display and a window.", "selenium": "Selenium needs a browser and a driver.",
               "langchain": "LangChain needs a model and an API key. Build the call by hand first (AI Engineering track)."}


def demo(key: str) -> dict:
    row = next((l for l in LIBS if l[0] == key), None)
    if row is None:
        return {"error": "No such library.", "status": 404}
    pip, imp = row[2], row[3]
    if importlib.util.find_spec(imp) is None:
        return {"key": key, "status": "missing", "install": f"pip install {pip}", "output": "", "note": WHY_NO_DEMO.get(key, "")}
    fn = DEMOS.get(key)
    if fn is None:
        return {"key": key, "status": "installed_no_demo", "output": "", "note": WHY_NO_DEMO.get(key, "No offline demo for this one.")}
    try:
        return {"key": key, "status": "ok", "output": fn(), "note": "Made-up data, no network."}
    except Exception as e:  # noqa: BLE001 - a broken optional library must not break the page
        return {"key": key, "status": "failed", "output": "", "note": f"The demo failed: {type(e).__name__}: {str(e)[:200]}. Check the library's install."}


SLIPS = [
    "Python-for-AI infographic: it is titled 'everything in AI', but Django, Flask, Kivy, Boto3 and Selenium are general software tools, not AI libraries. They matter for shipping AI, not for building it.",
    "Infographic: PyTorch is labelled 'research and production' and TensorFlow 'production and scaling'. Both are used for both; PyTorch dominates new research and large training, TensorFlow and its Keras API are still common for mobile and edge. Keras 3 can also run on PyTorch and JAX.",
    "Infographic: NLTK is listed as the NLP library. It is a teaching toolkit. For current work people use spaCy for pipelines and Hugging Face Transformers for pretrained models.",
    "Infographic: Apache Airflow is labelled 'workflow automation and scheduling'. It orchestrates data pipelines you write as code; it does not automate desktop or business tasks.",
    "Infographic: Kivy is labelled 'desktop app development'. It targets touch apps for desktop and mobile; Tkinter and PyQt are the usual desktop choices.",
    "Infographic: LangChain is shown as the way to build agents. It is one framework among several (LangGraph, LlamaIndex, provider SDKs) and you can build agents with plain API calls. Learn the loop by hand first.",
    "Infographic: missing from an AI map: spaCy, Hugging Face Transformers, Polars, XGBoost, MLflow, Pydantic and Playwright. Also a lead-generation post: the 'comment HERO' offer is a sales hook, not a course review.",
]
