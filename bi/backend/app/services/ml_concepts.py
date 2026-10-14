"""Machine learning concepts you can run: rules versus learning, the three kinds of learning, metrics, an approach chooser,
a reactive agent, an RPA fit check, and a reference of how AI is organised.

Everything uses synthetic or user-typed data with fixed seeds. Nothing here is medical, financial or legal advice.
Not built: training large models, GANs/VAEs/diffusion, vision or speech models, real robots (see NOT_BUILT).
"""
from __future__ import annotations

import math

import numpy as np


class MlcError(Exception):
    pass


def _i(v, name, lo, hi) -> int:
    try:
        x = int(v)
    except (TypeError, ValueError):
        raise MlcError(f"{name} must be a whole number.") from None
    if not lo <= x <= hi:
        raise MlcError(f"{name} must be between {lo} and {hi}.")
    return x


def _f(v, name, lo, hi) -> float:
    try:
        x = float(v)
    except (TypeError, ValueError):
        raise MlcError(f"{name} must be a number.") from None
    if not math.isfinite(x) or not lo <= x <= hi:
        raise MlcError(f"{name} must be between {lo:g} and {hi:g}.")
    return x


# ------------------------------------------------------------------ rules versus learning
def _synthetic(n, seed):
    rng = np.random.default_rng(seed)
    bpm = rng.normal(78, 14, n).clip(45, 140)
    bmi = rng.normal(27, 5, n).clip(16, 50)
    age = rng.integers(25, 85, n).astype(float)
    sex = rng.integers(0, 2, n).astype(float)
    risk = 0.045 * (bpm - 78) + 0.09 * (bmi - 27) + 0.05 * (age - 55) + 0.3 * sex
    y = (risk + rng.normal(0, 0.9, n) > 1.0).astype(int)
    return np.column_stack([bpm, bmi, age, sex]), y


def learn_rules(n=600, max_depth=3, seed=7) -> dict:
    from sklearn.metrics import accuracy_score, precision_score, recall_score
    from sklearn.model_selection import train_test_split
    from sklearn.tree import DecisionTreeClassifier, export_text
    n, depth = _i(n, "Rows", 200, 5000), _i(max_depth, "Depth", 1, 6)
    X, y = _synthetic(n, int(seed))
    names = ["beats_per_minute", "body_mass_index", "age", "sex"]
    Xtr, Xrest, ytr, yrest = train_test_split(X, y, test_size=0.4, random_state=1, stratify=y)
    Xva, Xte, yva, yte = train_test_split(Xrest, yrest, test_size=0.5, random_state=1, stratify=yrest)
    m = DecisionTreeClassifier(max_depth=depth, random_state=1).fit(Xtr, ytr)

    def sc(Xs, ys, p):
        return {"rows": len(ys), "accuracy": round(float(accuracy_score(ys, p)), 3), "precision": round(float(precision_score(ys, p, zero_division=0)), 3), "recall": round(float(recall_score(ys, p, zero_division=0)), 3)}
    hand = lambda A: ((A[:, 0] > 90) & (A[:, 1] > 30)).astype(int)   # a rule a person might write by hand
    base = float(max(ytr.mean(), 1 - ytr.mean()))
    rows = [{"set": "training", **sc(Xtr, ytr, m.predict(Xtr))}, {"set": "validation", **sc(Xva, yva, m.predict(Xva))}, {"set": "test", **sc(Xte, yte, m.predict(Xte))}]
    gap = rows[0]["accuracy"] - rows[2]["accuracy"]
    return {"synthetic": True, "features": names, "event_rate": round(float(y.mean()), 3), "rules": export_text(m, feature_names=names), "scores": rows,
            "hand_written_rule": {"rule": "beats_per_minute > 90 and body_mass_index > 30", "test": sc(Xte, yte, hand(Xte))},
            "majority_baseline_accuracy": round(base, 3),
            "overfit_warning": f"Training accuracy is {gap:.0%} above test accuracy: the tree is memorising. Lower the depth." if gap > 0.08 else None,
            "lesson": "Traditional programming: you supply data and rules and get answers. Machine learning: you supply data and answers and get the rules. The training set fits the model, the validation set tunes it, and the test set (never touched until the end) estimates how it will do on new data.",
            "caution": "The data is invented to show the method. It says nothing about real hearts, and a real project would need clinical data, review and governance."}


def split_sizes(n, train=60, val=20, test=20) -> dict:
    n = _i(n, "Rows", 3, 100_000_000)
    a, b, c = (_f(v, w, 0, 100) for v, w in ((train, "Training %"), (val, "Validation %"), (test, "Test %")))
    if abs(a + b + c - 100) > 0.01 or min(a, b, c) <= 0:
        raise MlcError("The three percentages must each be above 0 and add up to 100.")
    nt, nv = round(n * a / 100), round(n * b / 100)
    nte = n - nt - nv
    if min(nt, nv, nte) < 1:
        raise MlcError("Too few rows for that split.")
    return {"training": nt, "validation": nv, "test": nte,
            "advice": "Split before you look at the data, and for time-ordered data split by time, not randomly (the ML Lab does this). Never tune on the test set." + (" With so few rows the scores will be noisy: use cross-validation." if n < 500 else "")}


def metrics(tp, fp, fn, tn) -> dict:
    tp, fp, fn, tn = (_i(v, w, 0, 10**12) for v, w in ((tp, "True positives"), (fp, "False positives"), (fn, "False negatives"), (tn, "True negatives")))
    n = tp + fp + fn + tn
    if n == 0:
        raise MlcError("Enter at least one case.")
    d = lambda a, b: round(a / b, 4) if b else None
    acc, pre, rec = d(tp + tn, n), d(tp, tp + fp), d(tp, tp + fn)
    f1 = d(2 * tp, 2 * tp + fp + fn)
    major = max(tp + fn, fp + tn) / n
    notes = []
    if acc is not None and major >= 0.8 and acc <= major + 0.02:
        notes.append(f"Accuracy {acc:.1%} is no better than always guessing the majority class ({major:.1%}). With unbalanced classes, read precision and recall instead.")
    if rec is not None and rec < 0.5:
        notes.append("Recall is below 50%: the model misses most real cases.")
    if pre is not None and pre < 0.5:
        notes.append("Precision is below 50%: most of its alerts are false alarms.")
    return {"total": n, "accuracy": acc, "precision": pre, "recall": rec, "specificity": d(tn, tn + fp), "f1": f1, "notes": notes,
            "meaning": {"accuracy": "Share of all cases it got right.", "precision": "Of the cases it flagged, how many were real.", "recall": "Of the real cases, how many it found.", "f1": "A single balance of precision and recall."}}


# ------------------------------------------------------------------ the three kinds of learning
def kmeans(points=None, k=3, seed=3) -> dict:
    from sklearn.cluster import KMeans
    k = _i(k, "Clusters", 2, 8)
    if points:
        try:
            P = np.array([[float(a), float(b)] for a, b in points], float)
        except (TypeError, ValueError):
            raise MlcError("Each point is two numbers.") from None
        if len(P) > 500 or not np.isfinite(P).all():
            raise MlcError("Use up to 500 finite points.")
        demo = False
    else:
        rng = np.random.default_rng(int(seed))
        P = np.vstack([rng.normal(c, 0.6, (25, 2)) for c in ((1, 1), (5, 5), (1, 6))])
        demo = True
    if len(P) < k * 2:
        raise MlcError("Give at least two points per cluster.")
    m = KMeans(n_clusters=k, n_init=10, random_state=1).fit(P)
    sizes = np.bincount(m.labels_, minlength=k).tolist()
    return {"demo": demo, "points": [[round(float(a), 3), round(float(b), 3)] for a, b in P], "labels": m.labels_.tolist(), "centers": [[round(float(a), 3), round(float(b), 3)] for a, b in m.cluster_centers_],
            "sizes": sizes, "inertia": round(float(m.inertia_), 3),
            "lesson": "Unsupervised learning is given no labels. It groups points by how close they are. The algorithm can't name the groups: that is your job, and k is your choice, so try several.",
            "caution": "K-means finds round, similar-sized groups and always returns k clusters, even if the data has none."}


def q_learning(episodes=400, alpha=0.5, gamma=0.9, epsilon=0.2, seed=5) -> dict:
    ep, a, g, eps = _i(episodes, "Episodes", 10, 5000), _f(alpha, "Learning rate", 0.01, 1), _f(gamma, "Discount", 0, 0.999), _f(epsilon, "Exploration", 0, 1)
    rng = np.random.default_rng(int(seed))
    N, goal, pit = 4, (3, 3), (1, 3)
    acts = [(-1, 0), (1, 0), (0, -1), (0, 1)]
    arrows = "^v<>"
    Q = np.zeros((N, N, 4))

    def step(s, ai):
        r, c = s[0] + acts[ai][0], s[1] + acts[ai][1]
        if not (0 <= r < N and 0 <= c < N):
            r, c = s
        ns = (r, c)
        if ns == goal:
            return ns, 10.0, True
        if ns == pit:
            return ns, -10.0, True
        return ns, -1.0, False
    rewards = []
    for _ in range(ep):
        s, tot = (0, 0), 0.0
        for _t in range(60):
            ai = int(rng.integers(4)) if rng.random() < eps else int(np.argmax(Q[s]))
            ns, r, done = step(s, ai)
            Q[s][ai] += a * (r + (0 if done else g * Q[ns].max()) - Q[s][ai])
            s, tot = ns, tot + r
            if done:
                break
        rewards.append(tot)
    grid = [["G" if (r, c) == goal else "X" if (r, c) == pit else arrows[int(np.argmax(Q[r, c]))] for c in range(N)] for r in range(N)]
    # follow the learned policy from the start
    s, path, ok = (0, 0), [(0, 0)], False
    for _ in range(20):
        ns, _r, done = step(s, int(np.argmax(Q[s])))
        path.append(ns)
        s = ns
        if done:
            ok = ns == goal
            break
    early, late = float(np.mean(rewards[:max(1, ep // 10)])), float(np.mean(rewards[-max(1, ep // 10):]))
    return {"policy": grid, "reaches_goal": ok, "path": path, "avg_reward_first_tenth": round(early, 2), "avg_reward_last_tenth": round(late, 2), "episodes": ep,
            "setup": "4x4 grid. Start top-left. G = goal (+10), X = pit (-10), every step costs -1. Actions: up, down, left, right.",
            "lesson": "Reinforcement learning has no labelled answers. The agent tries actions, is rewarded or penalised, and learns which action is best in each state. Exploration (epsilon) lets it try new things; discount (gamma) sets how much it values later rewards.",
            "caution": "A tiny, deterministic world. Real problems have huge state spaces, noisy rewards and need far more trials."}


# ------------------------------------------------------------------ agents and automation
def thermostat(setpoint=21.0, outside=10.0, hours=12, proactive=False) -> dict:
    sp, out, h = _f(setpoint, "Set point", 10, 30), _f(outside, "Outside temperature", -30, 45), _i(hours, "Hours", 1, 48)
    temp, rows, energy, heater_on = 17.0, [], 0.0, False
    for t in range(h):
        forecast_drop = (out - temp) * 0.1
        want = temp < sp - 0.5 or (bool(proactive) and temp + forecast_drop < sp - 0.5 + 0.3)
        heater_on = want or (heater_on and temp < sp + 0.3)
        temp += 1.2 if heater_on else 0.0
        temp += (out - temp) * 0.1
        energy += 1.0 if heater_on else 0.0
        rows.append({"hour": t + 1, "temp": round(temp, 1), "heater": heater_on})
    return {"mode": "proactive" if proactive else "reactive", "rows": rows, "heater_hours": energy, "final_temp": rows[-1]["temp"],
            "lesson": "A reactive agent responds to what it senses now (too cold: heat). A proactive agent acts on a prediction to reach a goal (it may start heating before the room drops below the set point). Both are sense, decide, act loops."}


def rpa_fit(rule_based, digital, repetitive, structured_input, stable_screens, volume_per_month, minutes_each) -> dict:
    vol, mins = _i(volume_per_month, "Volume per month", 0, 10**8), _f(minutes_each, "Minutes each", 0, 100000)
    checks = [("Rules are clear: the same input always gets the same action", bool(rule_based)), ("The work happens in software, not on paper or in a person's judgment", bool(digital)),
              ("It repeats often", bool(repetitive)), ("Inputs are structured (fields, forms, spreadsheets)", bool(structured_input)), ("The screens and systems it touches rarely change", bool(stable_screens))]
    passed = sum(1 for _, ok in checks if ok)
    hours = vol * mins / 60
    verdict = "good" if passed == 5 else "maybe" if passed >= 3 else "poor"
    adv = {"good": "A strong candidate for RPA.", "maybe": "Possible, but fix the failing checks first (or use AI for the unstructured parts).", "poor": "Not suited to RPA as it stands."}[verdict]
    return {"checks": [{"check": t, "ok": ok} for t, ok in checks], "passed": passed, "verdict": verdict, "advice": adv, "hours_per_month": round(hours, 1),
            "caution": "Hours saved are an upper bound: add the time to build, monitor and fix the robot when a screen changes. Automating a broken process only makes mistakes faster.",
            "lesson": "RPA software robots follow rules to copy, validate and enter data across digital systems. They don't learn; AI is added when the input is unstructured (documents, language)."}


# ------------------------------------------------------------------ which approach?
def choose_approach(task, labeled_data, data_size, need_explain, unstructured) -> dict:
    tasks = {"number": "predict a number", "category": "predict a category", "group": "find groups", "anomaly": "spot unusual cases", "act": "learn actions by trial and reward", "generate": "generate text, images or code", "answer": "answer questions from our documents", "rules": "apply fixed business rules"}
    if task not in tasks or data_size not in ("small", "medium", "large") or labeled_data not in ("none", "some", "plenty"):
        raise MlcError("Check the choices.")
    pick, why, alt = "", [], []
    if task == "rules":
        pick = "Plain code or RPA"; why.append("If the rules are known and stable you don't need to learn them.")
    elif task == "answer":
        pick = "Retrieval-augmented generation (RAG)"; why += ["Your documents stay outside the model and can be updated without retraining.", "The answer can cite its source and say 'I don't know'."]; alt.append("Plain keyword search if you only need to find the document.")
    elif task == "generate":
        pick = "A pre-trained foundation model, prompted (or lightly tuned)"; why += ["Training one yourself needs enormous data and compute.", "Check the output: generative models can state wrong things confidently."]
    elif task == "act":
        pick = "Reinforcement learning (or simple rules first)"; why.append("It needs a simulator or safe environment to try actions cheaply.")
    elif task == "group":
        pick = "Clustering (k-means, hierarchical)"; why.append("No labels needed; you name the groups afterwards.")
    elif task == "anomaly":
        pick = "Statistical limits or unsupervised anomaly detection" if labeled_data != "plenty" else "Supervised classification (you have labelled cases)"; why.append("Rare events are hard to label, so start with limits on normal behaviour.")
    else:
        kind = "regression" if task == "number" else "classification"
        if unstructured and data_size == "large" and labeled_data == "plenty" and not need_explain:
            pick = f"Deep learning ({kind})"; why.append("Images, audio and free text with plenty of labelled data is where deep learning beats the alternatives.")
            alt.append("Start with a pre-trained model and fine-tune it.")
        elif labeled_data == "none":
            pick = "Label some data first, or use clustering to explore"; why.append("Supervised learning needs labelled examples.")
        else:
            pick = f"Classical machine learning ({kind}: linear/logistic regression, decision trees, random forest)"; why.append("On tables with modest data these are accurate, fast and cheaper than deep learning.")
            if need_explain:
                why.append("You need explanations: prefer linear models or a shallow tree.")
            alt.append("Always compare with a naive baseline (the average, or the majority class).")
    if data_size == "small" and pick.startswith(("Deep", "Classical")):
        why.append("With little data keep models simple and use cross-validation.")
    return {"task": tasks[task], "pick": pick, "why": why, "also": alt,
            "lesson": "Deep learning is a subset of machine learning, which is a subset of AI. Not all machine learning is deep learning, and deep learning is sometimes overkill."}


# ------------------------------------------------------------------ reference
HIERARCHY = [
    {"level": "Artificial intelligence", "what": "Machines doing tasks that normally need human intelligence: learning, reasoning, problem solving, decisions."},
    {"level": "Machine learning", "what": "A subset of AI: algorithms learn patterns from data instead of following rules written by hand."},
    {"level": "Neural networks", "what": "Layers of connected nodes that learn weights; the backbone of deep learning."},
    {"level": "Deep learning", "what": "Neural networks with many layers; learns from raw images, audio and text."},
    {"level": "Foundation models", "what": "Very large deep models trained on broad data, then adapted to many tasks by prompting or tuning."},
    {"level": "Large language models / generative AI", "what": "Foundation models for text (LLMs); generative AI is any model that creates new content."},
]
AI_BY_STRENGTH = [
    {"type": "Narrow (weak) AI", "what": "Does one task or a limited set well: translators, spam filters, recommenders, assistants.", "status": "All AI in use today."},
    {"type": "General (strong) AI / AGI", "what": "Can learn and do unrelated tasks at human level, transferring knowledge between them.", "status": "Not achieved."},
    {"type": "Super AI", "what": "Would surpass human intelligence. Often described as conscious.", "status": "Theoretical."}]
AI_BY_FUNCTION = [
    {"type": "Reactive", "what": "Fixed response to the current input; no memory.", "example": "Thermostat, rule-based chess engine"},
    {"type": "Limited memory", "what": "Uses past data to decide.", "example": "Self-driving cars, recommenders"},
    {"type": "Theory of mind", "what": "Would understand human emotions and intent.", "example": "Research only"},
    {"type": "Self-aware", "what": "Would have its own consciousness.", "example": "Theoretical"}]
AI_BY_PURPOSE = [
    {"type": "Descriptive / diagnostic", "asks": "What happened and why?", "does": "Patterns, trends, comparisons, root cause."},
    {"type": "Predictive", "asks": "What will happen?", "does": "Forecasting, classification, propensity, decision trees."},
    {"type": "Prescriptive", "asks": "What should we do?", "does": "Optimisation, personalisation, next best action, fraud prevention."},
    {"type": "Generative", "asks": "Can you make something new?", "does": "Text, images, audio, video and code."}]
STRENGTHS = {"machines": ["Ingest huge amounts of data fast", "Don't tire", "Repeat tasks reliably"], "humans": ["Generalise from one example", "Creativity and new ideas", "Emotional intelligence"],
             "augmented": "Pair them: the machine does the volume and repetition, the person supplies judgment, creativity and care. Examples: screen readers, driver-assist alerts, evidence placed in front of an expert."}
HISTORY = [("1950", "Alan Turing proposes the Turing Test."), ("1956", "John McCarthy coins 'artificial intelligence' (Dartmouth workshop)."), ("1960s", "ELIZA (a chatbot) and SHRDLU."), ("1970s", "Expert systems."),
           ("1980s", "Surge in machine learning."), ("1997", "IBM Deep Blue beats the world chess champion."), ("1990s-2000s", "Neural networks, then the rise of deep learning."), ("2010s", "Deep learning spreads: NLP, computer vision."),
           ("2020s", "Large language models and generative AI.")]
GEN_MODELS = [
    {"name": "VAE (variational autoencoder)", "how": "An encoder squeezes data into a small latent representation; a decoder rebuilds or generates from it.", "uses": "Image generation, anomaly detection"},
    {"name": "GAN (generative adversarial network)", "how": "A generator makes samples and a discriminator tries to tell them from real ones; they train against each other.", "uses": "Image synthesis, style transfer, data augmentation"},
    {"name": "Autoregressive", "how": "Predicts the next element from the earlier ones, one step at a time.", "uses": "Text, music, raw audio (WaveNet)"},
    {"name": "Transformer", "how": "Uses attention to relate every part of the input to every other part.", "uses": "LLMs (GPT, Gemini, Claude, Llama), translation"},
    {"name": "Diffusion", "how": "Learns to remove noise step by step, starting from random noise.", "uses": "Text-to-image (Stable Diffusion) and video"}]
MODALITY = {"unimodal": "Same kind of data in and out (text to text).", "multimodal": "Handles several kinds (text, images, audio, video), in or out."}
FOUNDATION = {"pros": ["Strong performance from broad pre-training", "Far less labelled data needed for a new task", "One model serves many uses"],
              "cons": ["Expensive to train and to run (often several GPUs)", "Training data is unvetted, so bias and toxic content can come through", "Training data is often undisclosed", "Can hallucinate"],
              "adapt": [{"name": "Prompting", "what": "Describe the task in the input. No training; works with little or no data."}, {"name": "Tuning", "what": "Update the model's parameters with a small labelled set to specialise it."},
                        {"name": "RAG", "what": "Fetch relevant passages from your own content and add them to the prompt."}]}
ARCH = {"traditional": ["Repository (your own data)", "Analytics platform (build models)", "Application (act on predictions)", "Feedback loop (learn from right and wrong calls)"],
        "generative": ["Massive outside data", "Foundation model", "Prompting and tuning layer (make it yours)", "Application", "Feedback loop (back to prompting and tuning)"],
        "note": "A churn model with no feedback loop is predictive analytics. The loop that learns from outcomes is what makes it adaptive."}
AGENTS = {"characteristics": [{"name": "Autonomy", "what": "Works without constant human help."}, {"name": "Reactiveness", "what": "Responds immediately to changes."}, {"name": "Proactiveness", "what": "Takes initiative toward goals."}, {"name": "Social ability", "what": "Communicates and cooperates with other agents and people."}],
          "loop": ["Perceive (sensors/data)", "Understand (process the data)", "Decide (knowledge and logic)", "Act (actuators or outputs)", "Learn (improve from experience)"],
          "multi_agent": "Several agents cooperate or compete: marketplaces (buyer and seller agents), robot teams, traffic management.",
          "robot_parts": [{"part": "Sensors", "does": "Eyes and ears: cameras, microphones, temperature, distance."}, {"part": "Controller", "does": "The brain: software that turns sensor data into decisions."}, {"part": "Actuators", "does": "Muscles: motors and hydraulics that move things."}],
          "cobots": "Collaborative robots work beside people, using sensors and AI to coordinate tasks.", "rpa": "Robotic process automation: software robots that follow rules through digital systems. Not physical, and not learning by default."}
COGNITIVE = {"steps": ["Observe evidence", "Interpret it into a hypothesis", "Evaluate which hypotheses hold", "Decide and act"], "elements": ["Perception", "Learning", "Reasoning"],
             "what": "Cognitive computing tries to mimic human thought so systems act as partners, not just tools."}
EDGE = [{"term": "IoT", "what": "Physical devices (sensors, cameras, wearables) connected to the internet that collect and share data."}, {"term": "Cloud", "what": "Storage and computing in remote data centres, reached over the internet."},
        {"term": "Edge computing", "what": "Processing near where data is made, for speed and to keep working offline."}, {"term": "Edge AI", "what": "A model running on the device itself, such as face recognition on a camera."}]
ADOPTION = ["Define business goals: name the problem and the target.", "Identify suitable use cases.", "Check data readiness: collect, clean and organise it.", "Build capability: train people and prepare the setup.", "Deploy and integrate with existing systems.", "Monitor and optimise."]
USES = [{"area": "Customer service", "examples": "Chatbots, voice assistants, routing to a person"}, {"area": "Finance", "examples": "Fraud detection, risk, robo-advisers"}, {"area": "Healthcare", "examples": "Imaging support, predictive analytics, drug discovery"},
        {"area": "Manufacturing", "examples": "Predictive maintenance, visual defect inspection, cobots"}, {"area": "Retail", "examples": "Recommendations, demand forecasting, cashierless stores"}, {"area": "Transport", "examples": "Routing, ride matching, self-driving"},
        {"area": "Marketing and sales", "examples": "Lead scoring, personalisation, segmentation"}, {"area": "Security", "examples": "Intrusion detection, biometric login"}]
JOBS = [{"role": "AI ethicist", "does": "Checks systems are built and used responsibly."}, {"role": "AI product manager", "does": "Owns an AI product so it meets a real need."}, {"role": "AI strategist", "does": "Plans how AI serves business goals."}, {"role": "AI marketing specialist", "does": "Uses AI on customer data to improve marketing."}]
SLIPS = [
    "The course says super AI 'extends the concept of generative AI'. It extends general AI; generative AI is a different idea (creating content) and is not a step toward consciousness.",
    "ELISA should be ELIZA. DAL-E is DALL-E, Imogen Video is Imagen Video, Murph is Murf, and McKenzie is McKinsey.",
    "The reading says ML 'increases the reading time of radiologists'. It means it decreases it.",
    "'Machine learning algorithms do not follow rule-based algorithms' overstates it: a trained decision tree is a set of rules, learned from data instead of written by hand.",
    "'Between 60 and 73% of stock trading is done by ML algorithms' is about algorithmic trading in general; much of it is not machine learning.",
    "'Reinforcement learning ... to identify and respond to cyberattacks' is one approach; most intrusion detection uses supervised or unsupervised learning.",
    "The 2014 'Turing test' claim (a chatbot posing as a 13-year-old) is disputed, and the test is not a measure of general intelligence.",
    "Several lessons describe unsupervised learning as 'deep learning without labels' and supervised as 'human intervention'. The two axes are independent: deep networks can be trained with or without labels.",
    "'Neural networks have three layers' is the minimum shape (input, hidden, output); real networks have many hidden layers. 'More than three layers' is one convention for 'deep'.",
    "The video says devices like robot vacuums 'do not need human intervention' and 'figure things out on their own'. They follow trained models inside set limits and still need people for set-up and maintenance.",
    "Market and adoption figures (Goldman Sachs, Statista, Gartner, Fortune Business Insights, McKinsey, Pega, a $200 billion ML market) are dated and from the course. Check current sources before quoting them.",
    "Model names in the course (GPT-3 as the ChatGPT base, PaLM, Jukedeck, Amper) are from an earlier period; many have been replaced or withdrawn.",
]
NOT_BUILT = [
    "Training large language models, image, video or speech models, or GANs/VAEs/diffusion: these need GPUs and frameworks this app does not have. The tools here teach the mechanics on tiny examples.",
    "Computer vision, speech-to-text, text-to-speech, facial recognition and self-driving: they need trained models, cameras, microphones or vehicles.",
    "Real robots, IoT devices and edge hardware. The thermostat and robot-loop demos are simulations.",
    "Closed products named in the course (Watson, Sora, DALL-E, Gemini, Alexa, Copilot) can't be reproduced; use them through their own services.",
    "Semantic (meaning-based) search over documents needs an embedding model. The RAG demo uses keyword weighting (TF-IDF), which misses synonyms.",
]


def reference() -> dict:
    return {"note": "How AI, machine learning, deep learning, NLP and generative AI fit together, with tools that run the ideas on small examples. The Reference tab lists corrections to the source course.",
            "hierarchy": HIERARCHY, "by_strength": AI_BY_STRENGTH, "by_function": AI_BY_FUNCTION, "by_purpose": AI_BY_PURPOSE, "strengths": STRENGTHS, "history": [{"when": a, "what": b} for a, b in HISTORY],
            "generative_models": GEN_MODELS, "modality": MODALITY, "foundation": FOUNDATION, "architecture": ARCH, "agents": AGENTS, "cognitive": COGNITIVE, "edge": EDGE, "adoption": ADOPTION, "uses": USES, "jobs": JOBS,
            "slips": SLIPS, "not_built": NOT_BUILT,
            "approach_tasks": {"number": "Predict a number", "category": "Predict a category", "group": "Find groups", "anomaly": "Spot unusual cases", "act": "Learn actions by trial and reward", "generate": "Generate text, images or code", "answer": "Answer questions from our documents", "rules": "Apply fixed business rules"}}
