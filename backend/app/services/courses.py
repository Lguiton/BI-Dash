"""Free AI and machine learning course list, with progress and a sensible order.

From an infographic of "60 best free courses". The list is kept as given (titles and providers), with its mistakes marked. This app does
not know whether a course is still free, current or open today: providers change that often. Check each course page before you start.
Ordering and goal paths are my own suggestion, not the infographic's.
"""
from __future__ import annotations

import json

from app.services import state


class CourseError(Exception):
    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.message, self.status = message, status


SECTIONS = {1: "Beginner and foundations", 2: "Python, math and ML foundations", 3: "Machine learning (core)", 4: "Deep learning", 5: "Generative AI and LLMs", 6: "Computer vision and applied AI", 7: "NLP and other topics"}
_RAW = """1|Elements of AI|University of Helsinki|1
2|AI For Everyone|DeepLearning.AI|1
3|Google's Machine Learning Crash Course|Google|1
4|CS50AI: Introduction to Artificial Intelligence with Python|Harvard (edX)|1
5|Introduction to Machine Learning|Kaggle|1
6|Introduction to AI|IBM (SkillsBuild)|1
7|What is Machine Learning?|Udemy|1
8|Welcome to Artificial Intelligence|Udemy|1
9|Learn Basics About AI|Udemy|1
10|Machine Learning with Python|IBM|2
11|Mathematics for Machine Learning Specialization|Imperial College London|2
12|Linear Algebra Refresher with Python|Udacity|2
13|Introduction to Data Science Using Python|Udemy|2
14|Deep Learning Prerequisites: NumPy Stack in Python|Udemy|2
15|Python Crash Course for Data Science and Machine Learning|Udemy|2
16|Data Science, Machine Learning, Data Analysis and Python and R|Udemy|2
17|Machine Learning Specialization|Stanford / DeepLearning.AI|3
18|Machine Learning for All|University of London|3
19|Machine Learning Fundamentals|UC San Diego|3
20|Machine Learning by Georgia Tech|Udacity|3
21|Intro to Machine Learning|Udacity|3
22|Intermediate Machine Learning|Kaggle|3
23|Feature Engineering|Kaggle|3
24|ML Explainability|Kaggle|3
25|Advanced Machine Learning|NYU|3
26|Deep Learning Specialization|DeepLearning.AI|4
27|MIT 6.S191: Introduction to Deep Learning|MIT|4
28|Intro to Deep Learning|Kaggle|4
29|Intro to TensorFlow for Deep Learning|Udacity|4
30|Intro to Deep Learning with PyTorch|Udacity|4
31|Introduction to TensorFlow Lite|Udacity|4
32|Reinforcement Learning|Udacity|4
33|Deep Learning with PyTorch: Zero to GANs|Udemy|4
34|Introduction to TensorFlow for AI, ML, and Deep Learning|DeepLearning.AI|4
35|Generative AI Learning Path|Google Cloud|5
36|DeepLearning.AI Short Courses|DeepLearning.AI|5
37|Building Systems with the ChatGPT API|DeepLearning.AI|5
38|LangChain for LLM Application Development|DeepLearning.AI|5
39|Hugging Face NLP Course|Hugging Face|5
40|Microsoft AI Skills Initiative|Microsoft|5
41|Learn with Google AI|Google|5
42|Google AI Essentials|Google|5
43|AI and Machine Learning Made Simple|Udemy|5
44|Computer Vision|Kaggle|6
45|Introduction to Computer Vision|Udacity|6
46|Core ML: Machine Learning for iOS|Udacity|6
47|Artificial Intelligence for Robotics|Udacity|6
48|Machine Learning for Trading|Udacity|6
49|AWS DeepRacer|Udacity|6
50|AI in Bioinformatics|Udemy|6
51|Amazing AI: Music Editing with Deep Learning|Udemy|6
52|Natural Language Processing|Kaggle|7
53|Intro to Game AI and Reinforcement Learning|Kaggle|7
54|Reinforcement Learning|Udacity|7
55|Machine Learning, Unsupervised Learning|Udacity|7
56|Knowledge-Based AI: Cognitive Systems|Udacity|7
57|Secure and Private AI|Udacity|7
58|Machine Learning Interview Preparation|Udacity|7
59|Spark|Udacity|7
60|Data Wrangling with MongoDB|Udacity|7"""
COURSES = []
for _l in _RAW.splitlines():
    n, t, p, s = _l.split("|")
    COURSES.append({"id": int(n), "title": t, "provider": p, "section": int(s)})

# Providers whose free status is stable enough to say; others must be checked.
_USUALLY_FREE = {"Kaggle", "Google", "Google Cloud", "Hugging Face", "Microsoft", "University of Helsinki", "MIT", "IBM (SkillsBuild)"}
_VERIFY = {"Udemy": "Udemy courses are usually paid; free ones are often limited-time or short previews.",
           "Udacity": "Udacity moved many free courses behind sign-up or removed them. Check before planning around one.",
           "DeepLearning.AI": "Short courses are free; Coursera specializations are free to watch or audit but certificates and graded work may cost.",
           "Stanford / DeepLearning.AI": "Coursera: audit or watch is usually free; certificate and graded work may cost.",
           "Imperial College London": "Coursera: audit or watch is usually free; certificate may cost.",
           "University of London": "Coursera: audit or watch is usually free; certificate may cost.",
           "UC San Diego": "Coursera/edX: audit or watch is usually free; certificate may cost.",
           "Harvard (edX)": "edX: audit track is free; certificate costs money.", "NYU": "Check the platform; free access varies.",
           "IBM": "Coursera/edX: audit or watch is usually free; certificate may cost."}
for _c in COURSES:
    p = _c["provider"]
    _c["free_status"] = "usually free" if p in _USUALLY_FREE else "check before you start"
    _c["note"] = _VERIFY.get(p, "")

# What this app already teaches that covers the same ground.
HERE = {1: "AI track: AI fundamentals and the learning path", 2: "Python lab, Analysis lab, ML lab", 3: "ML track: learning path and ML lab",
        4: "ML and AI tracks: inference and deep-learning lessons (no GPU training here)", 5: "AI track: AI workbench, MLOps and governance lab; calling a hosted model needs your own key",
        6: "ML track covers the ideas; no image models run here", 7: "Analysis lab and ML track; no Spark cluster here"}

PATHS = {
    "ai-literacy": ("Understand AI without coding", [1, 2, 6, 42, 41, 40]),
    "ml-foundations": ("Python, math, then core machine learning", [15, 11, 10, 3, 5, 22, 23, 24, 17]),
    "deep-learning": ("From core ML to neural networks", [17, 26, 28, 27, 30, 34]),
    "genai-builder": ("Build applications on language models", [42, 35, 36, 37, 38, 39]),
    "vision": ("Computer vision", [5, 28, 44, 45]),
}


def catalog(section: int | None = None, q: str = "") -> dict:
    rows = [c for c in COURSES if (section is None or c["section"] == section) and (not q or q.lower() in (c["title"] + " " + c["provider"]).lower())]
    done = _done()
    return {"courses": [{**c, "section_name": SECTIONS[c["section"]], "done": c["id"] in done, "here": HERE[c["section"]]} for c in rows], "count": len(rows), "done_count": len(done),
            "sections": SECTIONS}


def _done() -> set:
    try:
        return set(json.loads(state.kv_get("courses_done", "[]") or "[]"))
    except ValueError:
        return set()


def mark(course_id: int, done: bool) -> dict:
    if not any(c["id"] == course_id for c in COURSES):
        raise CourseError("No course with that number.", 404)
    d = _done()
    (d.add if done else d.discard)(course_id)
    state.kv_set("courses_done", json.dumps(sorted(d)))
    return {"done": sorted(d)}


def duplicates() -> list[dict]:
    seen: dict[tuple, list] = {}
    for c in COURSES:
        seen.setdefault((c["title"].lower(), c["provider"].lower()), []).append(c["id"])
    return [{"title": k[0], "provider": k[1], "ids": v} for k, v in seen.items() if len(v) > 1]


def path(goal: str) -> dict:
    if goal not in PATHS:
        raise CourseError("Pick one of: " + ", ".join(PATHS), 404)
    title, ids = PATHS[goal]
    done = _done()
    by = {c["id"]: c for c in COURSES}
    steps = [{"order": i + 1, **{k: by[n][k] for k in ("id", "title", "provider", "free_status", "note")}, "done": n in done} for i, n in enumerate(ids)]
    nxt = next((s for s in steps if not s["done"]), None)
    return {"goal": goal, "title": title, "steps": steps, "next": nxt,
            "caution": "The order is this app's suggestion. Course lengths are not given in the source, so no time estimate is made. Do the exercises, not just the videos."}


SLIPS = [
    "60 free courses list: the same course (Reinforcement Learning, Udacity) appears twice, as number 32 and number 54, so there are 59 different ones.",
    "60 free courses list: 'FREE' is a promise the list cannot keep. Udemy courses are mostly paid unless a promotion is running, many Udacity courses have moved behind sign-up, and Coursera or edX courses are free to audit but the certificate costs money. Check each page the day you start.",
    "60 free courses list: items are in the wrong section. Unsupervised Learning, Spark and MongoDB data wrangling sit under 'NLP and other topics', while the Hugging Face NLP course sits under generative AI, so the NLP section has one real NLP course.",
    "60 free courses list: levels are mixed with no order. Machine Learning for Trading and Secure and Private AI are advanced, but sit beside beginner topics, and nothing says which course to do before which or how long each takes.",
    "60 free courses list: 'best' is not backed by anything: no ratings, completion rates or criteria. Half the list (30 of 60) comes from just two providers, Udacity and Udemy, so it reads as a catalogue, not a ranking.",
]
NOT_BUILT = ["Checking whether a course is still free or open today (no live access to the providers here).",
             "Hosting the courses, videos, graded assignments or certificates."]


def reference() -> dict:
    return {"sections": SECTIONS, "paths": {k: v[0] for k, v in PATHS.items()}, "slips": SLIPS, "not_built": NOT_BUILT, "duplicates": duplicates()}
