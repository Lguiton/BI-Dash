"""Learning paths for the ML and AI Engineering tracks, beginner to advanced.

The AI Engineering path follows the owner's own nine-level curriculum (Levels 0 to 8, each ending in a gate project).
The ML path is a seven-level companion built the same way. Every module is marked honestly:

  built   - this app has a tool or exercise you can run for it
  partial - this app covers part of it; the rest needs a notebook, library or outside course
  guide   - study and build it outside this app (nothing here to run)
  cannot  - needs GPUs, cloud services or hardware this app does not have

Progress (modules ticked, gates passed) is saved per workspace. Resources are from general knowledge, not a fresh web
check: confirm current editions and links before you buy or enrol.
"""
from __future__ import annotations

import json

from app.services import state, workspaces


class PathError(Exception):
    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.message, self.status = message, status


def M(mid, title, topics, status, where, practice):
    return {"id": mid, "title": title, "topics": topics, "status": status, "where": where, "practice": practice}


ML = {
    "title": "Machine Learning: beginner to advanced",
    "intro": "Seven levels. The thread running through all of them: a model is only good if it beats a simple guess on data it has never seen.",
    "levels": [
        {"id": "M0", "title": "Foundations", "weeks": "4 to 6", "gate": "A notebook that cleans a real data set and states, with numbers, three things it shows.",
         "modules": [
             M("M0.1", "Python, pandas and SQL", "Types, functions, DataFrames, joins, group-by, reading messy files", "built", "Python Lab, SQL Lab and the Analyst track", "Clean one real file and answer five questions in SQL and in pandas; compare the answers."),
             M("M0.2", "Statistics and probability", "Distributions, mean and spread, sampling, confidence intervals, hypothesis tests, Bayes' rule", "built", "Stats pages and the BI Toolkit distribution finder", "Explain a confidence interval and a p-value to a non-technical friend in four sentences."),
             M("M0.3", "Linear algebra and calculus for ML", "Vectors, matrices, dot product, derivatives, the chain rule, gradients", "partial", "Gradient descent tool shows the idea; the maths itself needs a course", "Compute a gradient by hand for y = w*x, then check it against the Gradient descent tool."),
         ]},
        {"id": "M1", "title": "The ML workflow", "weeks": "3 to 4", "gate": "A model that beats the naive baseline on a time-aware split, with a leakage check written down.",
         "modules": [
             M("M1.1", "Problem framing and baselines", "Supervised vs unsupervised, what you predict, what you know at prediction time, the dumb baseline", "built", "ML Lab (baseline shown beside every model) and AI fundamentals > Learning", "Write the prediction question, the metric and the baseline before opening ML Lab."),
             M("M1.2", "Splits, leakage and honest validation", "Train/validation/test, cross-validation, time splits, target leakage", "built", "ML Lab splits plus ML tools > Leakage scan", "Paste a CSV into the leakage scan; remove every flagged column and see the score drop."),
             M("M1.3", "Bias, variance and regularization", "Underfit, overfit, model complexity, L1/L2", "built", "ML tools > Bias and variance", "Find the best degree, change the seed, and explain why the answer moves."),
         ]},
        {"id": "M2", "title": "Core algorithms", "weeks": "4 to 6", "gate": "kNN, logistic regression and a decision tree written from scratch, compared on one data set with a written verdict.",
         "modules": [
             M("M2.1", "Gradient descent, linear and logistic regression", "Loss, learning rate, convergence, sigmoid", "built", "ML tools > Gradient descent", "Make it diverge, then make it crawl, then find a rate that converges in under 50 steps."),
             M("M2.2", "kNN, trees and naive Bayes", "Distance, splits and impurity, independence assumption", "built", "ML tools > Algorithms from scratch", "Raise tree depth from 1 to 10 and plot test accuracy; explain the shape."),
             M("M2.3", "Clustering and dimensionality reduction", "k-means, choosing k, PCA", "partial", "AI fundamentals > Learning has k-means; PCA, DBSCAN and UMAP are not built", "Cluster a data set, then label the clusters in plain words a manager would accept."),
         ]},
        {"id": "M3", "title": "Metrics, imbalance and tabular models", "weeks": "4 to 6", "gate": "A cost-aware threshold for a rare-event model, justified in money, with error slices.",
         "modules": [
             M("M3.1", "Classification and regression metrics", "Precision, recall, F1, ROC-AUC, PR-AUC, calibration, MAE, RMSE, R-squared", "built", "AI fundamentals > Learning metrics; ML tools > Scores and thresholds", "Take a model with 95% accuracy on 5% positives and show why that is useless."),
             M("M3.2", "Thresholds, costs and calibration", "Cost of a miss vs a false alarm, picking the cut-off, reliability of probabilities", "built", "ML tools > Scores and thresholds", "Set the miss to cost 10x a false alarm and find the cheapest threshold."),
             M("M3.3", "Random forests and gradient boosting", "Bagging, boosting, tuning, feature importance", "built", "ML Lab models: random forest, gradient boosting, histogram boosting; XGBoost and LightGBM are not installed by default", "Compare four models on one task in ML Lab and record the winner with its baseline gap."),
             M("M3.4", "Feature engineering and pipelines", "Encoding, scaling, missing values, time features, scikit-learn Pipelines", "partial", "ML Lab builds features for you; writing your own Pipeline needs a notebook (ML track notebook 13)", "Rebuild one ML Lab run as a scikit-learn Pipeline and match its score."),
         ]},
        {"id": "M4", "title": "Deep learning", "weeks": "6 to 8", "gate": "A small neural network trained from scratch in NumPy, with a loss curve and an overfitting demo.",
         "modules": [
             M("M4.1", "Neurons, networks and backpropagation", "Weights, activations, loss, the chain rule", "built", "AI fundamentals > Neural networks (neuron, XOR with and without a hidden layer)", "Train XOR with no hidden layer, watch it fail, then add one."),
             M("M4.2", "Optimizers, regularization and normalization", "SGD, momentum, Adam, dropout, batch/layer norm", "guide", "Study outside; Gradient descent tool shows plain SGD only", "Implement momentum on top of the gradient-descent loop."),
             M("M4.3", "PyTorch, CNNs and transformers", "Tensors, training loops, convolution, attention", "cannot", "AI fundamentals shows one convolution; PyTorch and GPU training are not available here", "Do a PyTorch tutorial on a free notebook service and keep the notebook in your repo."),
         ]},
        {"id": "M5", "title": "Specialised problems", "weeks": "4 to 8", "gate": "One specialised model (forecast, text, anomaly or recommender) with a backtest and an honest limit statement.",
         "modules": [
             M("M5.1", "Time series and forecasting", "Lags, seasonality, backtesting, forecast accuracy", "built", "BI Toolkit > Forecast methods", "Backtest three methods on your own monthly series; keep the one that beats seasonal-naive."),
             M("M5.2", "Text and NLP basics", "Tokens, TF-IDF, classifiers, intents", "built", "AI fundamentals > NLP", "Train the text classifier on 20 of your own examples per class and read its mistakes."),
             M("M5.3", "Anomaly detection, recommenders and causal thinking", "Outliers, similarity, A/B tests vs correlation", "partial", "Stats and Analyst tools cover outliers and A/B tests; recommenders are not built", "Write down one thing your model's correlation does NOT prove."),
         ]},
        {"id": "M6", "title": "MLOps and responsible ML", "weeks": "4 to 6", "gate": "A model release record: gate result, rollback plan, drift check and what you will watch.",
         "modules": [
             M("M6.1", "Experiments, registry and promotion", "Tracking runs, versions, champion/challenger, rollback", "built", "ML Lab runs, model registry and the MLOps lab", "Promote a model through the gate, then roll it back."),
             M("M6.2", "Monitoring, drift and retraining", "Input drift, performance decay, when to retrain", "built", "MLOps lab > Retrain advice and drift checks", "Run a drift check, read the advice, and decide by hand before automating."),
             M("M6.3", "Fairness, explainability and documentation", "Slices, permutation importance, model cards, data cards", "partial", "ML Lab shows permutation importance; Qual templates hold model and data cards; fairness testing is a manual exercise", "Score one model on two slices of your data and write down the gap."),
             M("M6.4", "Serving at scale", "APIs, batching, GPUs, feature stores, CI/CD", "cannot", "Registry predict and load test only; no autoscaling, GPUs or pipelines", "Containerise a model with FastAPI and Docker on your own machine."),
         ]},
    ],
    "resources": [
        {"level": "M0-M1", "name": "Mathematics for Machine Learning (Deisenroth, Faisal, Ong)", "type": "Free book"},
        {"level": "M1-M3", "name": "Hands-On Machine Learning with Scikit-Learn, Keras and TensorFlow (Aurelien Geron)", "type": "Book"},
        {"level": "M1-M3", "name": "Andrew Ng, Machine Learning Specialization", "type": "Course"},
        {"level": "M3", "name": "scikit-learn user guide (model evaluation, pipelines)", "type": "Docs"},
        {"level": "M4", "name": "Andrej Karpathy, Neural Networks: Zero to Hero", "type": "Video series with code"},
        {"level": "M4", "name": "Understanding Deep Learning (Simon Prince)", "type": "Book"},
        {"level": "M6", "name": "Designing Machine Learning Systems (Chip Huyen)", "type": "Book"},
    ],
}

AI = {
    "title": "AI Engineering: beginner to master",
    "intro": "Nine levels from your own curriculum, each ending in a gate project you ship and defend. Levels 0 and 1 are the ML path; Levels 3 to 5 are where this app is strongest; Levels 2 and 6 need GPUs it does not have.",
    "levels": [
        {"id": "L0", "title": "Foundations", "weeks": "6 to 10", "gate": "Tested, Dockerized CLI and API with CI green, plus a notebook that derives gradient descent by hand.",
         "modules": [
             M("0.1", "Python for engineers", "Types, classes, generators, async, packaging", "built", "Python Lab, Python practice folder", "Write a CLI that downloads, cleans and reports on a public data set."),
             M("0.2", "Software engineering fundamentals", "Git, pytest, FastAPI and Pydantic, Docker, CI, SQL", "built", "Full Stack track (API map, scaffold, Docker files) and SQL Lab", "Add a test and a GitHub Actions workflow to one of your own repos."),
             M("0.3", "Math for machine learning", "Linear algebra, calculus, probability, entropy and cross-entropy", "partial", "ML tools > Gradient descent; the maths itself is a course", "Implement softmax plus cross-entropy and a numeric gradient check in NumPy."),
             M("0.4", "Data tooling", "NumPy, pandas, plotting, Jupyter", "built", "Analyst track and Python practice notebooks", "Redo one dashboard chart in matplotlib."),
         ]},
        {"id": "L1", "title": "Classical machine learning", "weeks": "6 to 8", "gate": "Tabular ML pipeline with an honest evaluation report.",
         "modules": [
             M("1.1", "The ML workflow", "Splits, leakage, bias-variance, baselines", "built", "ML track: ML tools (Bias and variance, Leakage scan) and ML Lab", "See the ML path M1."),
             M("1.2", "Core algorithms", "Regression, kNN, trees, boosting, clustering", "built", "ML tools > Algorithms from scratch, Gradient descent; ML Lab", "See the ML path M2."),
             M("1.3", "Metrics and evaluation", "Precision, recall, AUC, calibration, cost thresholds", "built", "ML tools > Scores and thresholds", "See the ML path M3."),
             M("1.4", "Feature engineering and pipelines", "Encoding, Pipelines, MLflow, forecasting", "partial", "ML Lab runs and experiments; BI Toolkit forecasts", "See the ML path M3.4 and M5.1."),
         ]},
        {"id": "L2", "title": "Deep learning and transformers", "weeks": "8 to 10", "gate": "A small GPT (10 to 50 million parameters) trained from scratch in PyTorch.",
         "modules": [
             M("2.1", "Neural network fundamentals", "MLPs, backprop, optimizers, normalization", "partial", "AI fundamentals > Neural networks trains a tiny net by backpropagation", "Build a micrograd-style autograd engine in a notebook."),
             M("2.2", "PyTorch fluency", "Tensors, training loops, GPUs, debugging training", "cannot", "No GPU or PyTorch here", "Follow a PyTorch course on a free GPU notebook service."),
             M("2.3", "Tokens, embeddings and attention", "BPE, embeddings, self-attention, positional encoding", "partial", "AI workbench > Context and cost estimates tokens; AI fundamentals > NLP tokenizes; attention itself is not built", "Write a byte-pair-encoding tokenizer for a paragraph of text."),
             M("2.4", "The transformer", "Decoder-only models, sampling, KV cache, scaling laws", "partial", "Inference lab covers KV-cache memory, latency and cost arithmetic", "Use the Inference lab to size the KV cache for a 32k context and say why long context is expensive."),
             M("2.5", "Beyond text", "CNNs, ViT, diffusion, speech", "cannot", "Only a convolution demo; vision, diffusion and speech models cannot run here", "Read one overview of each and write a paragraph on the cost to serve it."),
         ]},
        {"id": "L3", "title": "LLM application engineering and RAG", "weeks": "6 to 8", "gate": "Production RAG service with citations and a 100-question evaluation set.",
         "modules": [
             M("3.1", "Working with model APIs", "Messages, streaming, tokens, rate limits, retries, caching", "built", "AI Lab (Gemini, OpenAI, Claude with routing and caps), AI workbench > Context and cost, AI tools > Reliability", "Plan monthly spend for a feature with caching on and off."),
             M("3.2", "Prompt and context engineering", "Instructions, few-shot, XML tags, injection awareness, prompt versions", "built", "AI workbench > Prompt versions (diff, tests, live run with confirmation)", "Write three versions of one prompt and compare them on the same ten test inputs."),
             M("3.3", "Structured output and function calling", "Schemas, Pydantic validation, repair loops", "built", "AI tools > Structured output; ai_engineering/01_structured_output.py", "Feed it five broken replies and write the repair prompt for each."),
             M("3.4", "Embeddings and vector search", "Cosine similarity, HNSW, hybrid search, rank fusion", "partial", "AI tools > Hybrid search (BM25 + n-gram vector, RRF, MMR). Learned embeddings and vector databases are not built", "Find a query where keyword search misses and the vector side rescues it, and one where it is the reverse."),
             M("3.5", "Retrieval-augmented generation", "Chunking, re-ranking, grounding, citations, refusal, retrieval metrics", "built", "AI workbench > RAG evaluation, AI tools > Retrieval metrics, ai_engineering/02_rag.py", "Build 20 answerable and 5 unanswerable questions and report recall@3 and abstain rate."),
         ]},
        {"id": "L4", "title": "Agents, tool use and orchestration", "weeks": "6 to 8", "gate": "Multi-tool agent with approval gates, full action trace and a task-success eval.",
         "modules": [
             M("4.1", "Agent fundamentals", "The agent loop, workflows vs agents, step budgets, loop detection", "built", "AI Lab (a working tool-use agent), AI tools > Agent trace", "Paste a trace with a loop and explain which rule caught it."),
             M("4.2", "Tools and MCP", "Tool design, MCP servers and clients, sandboxing", "built", "ai_engineering/04_mcp_server.py; AI workbench > Tool safety", "Add a fourth read-only tool to the MCP server and describe it so a model picks it correctly."),
             M("4.3", "Memory and state", "Context compaction, long-term memory, durable execution", "guide", "Study outside; nothing to run here", "Design a memory schema on paper: what is stored, for how long, and who can delete it."),
             M("4.4", "Multi-agent systems", "Orchestrator-worker, handoffs, per-agent cost", "partial", "The role agents in this app are separate specialists you consult one at a time; orchestration frameworks (LangGraph, Agents SDK) are not installed", "Draw the message contract between two agents and the failure that each can cause."),
             M("4.5", "Agent safety and control", "Least privilege, approvals, injection defence, audit logs", "built", "AI workbench > Tool safety; AI tools > Guard scan; ai_engineering/05_prompt_injection.py; the agents' policy limits", "Give an agent private data, untrusted input and an outbound channel in Tool safety and read the score."),
         ]},
        {"id": "L5", "title": "Evaluation, observability and reliability", "weeks": "4 to 6", "gate": "Versioned eval suite gating every deploy in CI, blocking a deliberately regressed prompt.",
         "modules": [
             M("5.1", "Evaluation design", "Golden sets, code checks first, LLM-as-judge calibration, statistical rigor", "built", "AI tools > Eval statistics (intervals, sample size, A/B, kappa); AI workbench > Prompt versions; ai_engineering/03_evals.py", "Work out how many test cases you need to detect a 5-point improvement."),
             M("5.2", "Evaluating complex systems", "RAG metrics, agent metrics, benchmarks and their limits, red-teaming", "built", "AI tools > Retrieval metrics, Agent trace, Guard scan", "Red-team your own prompt with five injection attempts and score the result."),
             M("5.3", "Observability", "Tracing, dashboards, drift alerts, online evaluation", "partial", "AI Lab usage log, Ops page and /metrics; Langfuse, LangSmith and OpenTelemetry are not built", "Add trace ids and token counts to your own agent logs and chart cost per task."),
             M("5.4", "Reliability engineering", "Timeouts, retries, fallbacks, guardrails, CI gating", "built", "AI tools > Reliability (back-off, error budgets, chained availability, retry amplification); LLM router fallback", "Compute the worst-case latency of your retry policy and fix it if it exceeds your deadline."),
         ]},
        {"id": "L6", "title": "Fine-tuning, training and inference", "weeks": "6 to 8", "gate": "LoRA fine-tune beating a prompted baseline, quantized and served, with cost per million tokens.",
         "modules": [
             M("6.1", "When to fine-tune", "Decision ladder, data curation and deduplication", "built", "MLOps lab > LLM approach chooser; AI tools > Fine-tune data check", "Run your candidate training file through the data check and fix every issue."),
             M("6.2", "Post-training techniques", "SFT, LoRA and QLoRA, DPO, RL with verifiable rewards, distillation", "partial", "AI tools > LoRA and training size calculator explains memory and compute; actual training cannot run here", "Size a LoRA run for a 7B model and check it fits your GPU budget."),
             M("6.3", "Distributed training", "Parallelism, FSDP and ZeRO, mixed precision, memory maths", "partial", "Inference lab and the LoRA calculator do the memory arithmetic; no multi-GPU training", "Compute weights, gradients and optimizer memory for a 70B model by hand."),
             M("6.4", "Inference optimization and serving", "Quantization, vLLM, batching, speculative decoding, GPU economics", "built", "Inference lab (fit, bottleneck, latency, cost, speculative, scaling, quantization)", "Compare cost per million tokens self-hosted vs API at 20% and 80% utilisation."),
         ]},
        {"id": "L7", "title": "Production AI systems and LLMOps", "weeks": "6 to 8", "gate": "Multi-tenant AI service with a threat model, an OWASP LLM review and a cost model.",
         "modules": [
             M("7.1", "AI system architecture", "Gateway, orchestration, routing, caching, queues", "partial", "LLM router (routing, daily caps, fallback) and the pipelines pages; queues and a gateway product are not built", "Draw the reference architecture and mark which boxes this app implements."),
             M("7.2", "Multi-tenancy", "Tenant isolation, row-level security, metering, quotas", "partial", "Workspaces isolate data per workspace; Governance tab covers access; per-tenant billing is not built", "List every place tenant data could cross over in a RAG system."),
             M("7.3", "Security", "OWASP LLM Top 10, secrets, PII redaction, threat modelling", "built", "AI tools > Guard scan; AI workbench > Tool safety; Security track", "Threat-model one AI feature: assets, entry points, abuse cases, controls."),
             M("7.4", "Cost and performance engineering", "Unit economics, model tiering, caching, capacity", "built", "AI workbench > Cost planner; Inference lab > Cost and Scaling", "Model the margin of a feature at three prices and three cache hit rates."),
             M("7.5", "Governance and compliance", "NIST AI RMF, ISO 42001, EU AI Act tiers, HIPAA, model cards", "partial", "Qual templates (use case brief, model card, data card, incident review) and the Governance tab; frameworks are not certified or audited here", "Write a one-page mapping of your AI feature to the framework your customers will ask about."),
             M("7.6", "LLMOps lifecycle", "Registries, canary and shadow deploys, feedback loops, IaC", "partial", "MLOps lab: aliases, shadow run, traffic split, rollout plan, feedback log. Terraform, Kubernetes and GPU scheduling are not built", "Write the rollout plan for a prompt change, including the rollback trigger."),
         ]},
        {"id": "L8", "title": "Mastery: research, safety and leadership", "weeks": "ongoing", "gate": "Master capstone and a published write-up another engineer could reproduce.",
         "modules": [
             M("8.1", "Reading and reproducing research", "Paper-reading method, reproduce one result per quarter", "guide", "Study outside", "Read one paper and write the one-paragraph summary plus the claim you doubt most."),
             M("8.2", "Frontier topics", "Reasoning models, long context, MoE, interpretability", "guide", "Study outside", "Explain mixture-of-experts memory vs compute in the Inference lab's terms."),
             M("8.3", "AI safety and alignment", "RLHF, failure modes, dangerous-capability evals, autonomy levels", "partial", "Tool safety and the agents' approval limits show proportionate autonomy; alignment research is reading", "Write an autonomy ladder for one agent and the kill switch at each rung."),
             M("8.4", "Architecture and technical leadership", "Build vs buy, decision records, ROI for non-technical readers", "partial", "Company engagement templates and Qual decision notes", "Write an architecture decision record for model choice, including what would make you reverse it."),
             M("8.5", "Contributing back", "Open source, writing, talks", "guide", "Outside this app", "Publish one post-mortem of a failure from your own eval set."),
         ]},
    ],
    "capstones": ["Autonomous analytics workforce (Levels 3, 4, 5, 7)", "Regulated-domain operations copilot (3, 4, 5, 7)", "Self-improving support system (4, 5, 6, 7)",
                  "Domain small language model (2, 5, 6)", "Agent reliability platform (5, 7)"],
    "rubric": ["Correctness", "Evaluation", "Engineering", "Security", "Cost awareness", "Communication"],
    "resources": [
        {"level": "L0", "name": "Fluent Python (Luciano Ramalho)", "type": "Book"},
        {"level": "L0", "name": "3Blue1Brown: Essence of Linear Algebra and Calculus", "type": "Video series"},
        {"level": "L2", "name": "Andrej Karpathy, Neural Networks: Zero to Hero", "type": "Video series with code"},
        {"level": "L2", "name": "Build a Large Language Model (From Scratch) (Sebastian Raschka)", "type": "Book"},
        {"level": "L3-L4", "name": "AI Engineering (Chip Huyen)", "type": "Book"},
        {"level": "L4", "name": "Anthropic, Building Effective Agents; Model Context Protocol docs", "type": "Essay and spec"},
        {"level": "L5", "name": "Hamel Husain and Shreya Shankar on LLM evals", "type": "Articles and course"},
        {"level": "L6", "name": "Hugging Face courses; TRL and PEFT docs; vLLM docs", "type": "Courses and docs"},
        {"level": "L7", "name": "OWASP Top 10 for LLM Applications; NIST AI Risk Management Framework", "type": "Standards"},
        {"level": "L8", "name": "Stanford CS224N and CS336", "type": "Courses"},
    ],
}

# ---------------------------------------------------------------- outside links
# Official home pages and documentation landing pages for everything this app cannot run. They were NOT click-tested
# from the build environment (it has no general internet access), so run scripts/check_links.py on your own machine.
L = {
    "pytorch": ("PyTorch", "https://pytorch.org/"), "pytorch_tut": ("PyTorch tutorials", "https://pytorch.org/tutorials/"),
    "colab": ("Google Colab (free notebooks, GPU on request)", "https://colab.research.google.com/"), "kaggle": ("Kaggle notebooks", "https://www.kaggle.com/code"),
    "hf_docs": ("Hugging Face Transformers docs", "https://huggingface.co/docs/transformers"), "hf_course": ("Hugging Face LLM course", "https://huggingface.co/learn/llm-course"),
    "peft": ("Hugging Face PEFT (LoRA)", "https://huggingface.co/docs/peft"), "trl": ("Hugging Face TRL (SFT, DPO)", "https://huggingface.co/docs/trl"),
    "unsloth": ("Unsloth", "https://unsloth.ai/"), "deepspeed": ("DeepSpeed", "https://www.deepspeed.ai/"),
    "vllm": ("vLLM docs", "https://docs.vllm.ai/"), "vllm_gh": ("vLLM on GitHub", "https://github.com/vllm-project/vllm"),
    "llamacpp": ("llama.cpp", "https://github.com/ggml-org/llama.cpp"), "ollama": ("Ollama", "https://ollama.com/"),
    "langgraph": ("LangGraph docs", "https://langchain-ai.github.io/langgraph/"), "oai_agents": ("OpenAI Agents SDK", "https://openai.github.io/openai-agents-python/"),
    "claude_docs": ("Claude developer docs (API and Agent SDK)", "https://docs.claude.com/"), "mcp": ("Model Context Protocol", "https://modelcontextprotocol.io/"),
    "langfuse": ("Langfuse", "https://langfuse.com/"), "phoenix": ("Arize Phoenix", "https://phoenix.arize.com/"), "otel": ("OpenTelemetry", "https://opentelemetry.io/"),
    "langsmith": ("LangSmith", "https://www.langchain.com/langsmith"),
    "pgvector": ("pgvector", "https://github.com/pgvector/pgvector"), "qdrant": ("Qdrant", "https://qdrant.tech/"), "pinecone": ("Pinecone", "https://www.pinecone.io/"),
    "faiss": ("FAISS", "https://github.com/facebookresearch/faiss"), "chroma": ("Chroma", "https://www.trychroma.com/"),
    "litellm": ("LiteLLM (LLM gateway)", "https://www.litellm.ai/"), "pg_rls": ("PostgreSQL row-level security", "https://www.postgresql.org/docs/current/ddl-rowsecurity.html"),
    "xgboost": ("XGBoost", "https://xgboost.readthedocs.io/"), "lightgbm": ("LightGBM", "https://lightgbm.readthedocs.io/"),
    "sklearn": ("scikit-learn user guide", "https://scikit-learn.org/stable/user_guide.html"), "sk_pipe": ("scikit-learn pipelines", "https://scikit-learn.org/stable/modules/compose.html"),
    "sk_perm": ("scikit-learn permutation importance", "https://scikit-learn.org/stable/modules/permutation_importance.html"), "umap": ("UMAP", "https://umap-learn.readthedocs.io/"),
    "mlflow": ("MLflow", "https://mlflow.org/"), "wandb": ("Weights & Biases", "https://wandb.ai/"), "fastapi": ("FastAPI", "https://fastapi.tiangolo.com/"),
    "docker": ("Docker docs", "https://docs.docker.com/"), "terraform": ("Terraform", "https://developer.hashicorp.com/terraform"), "k8s": ("Kubernetes docs", "https://kubernetes.io/docs/home/"),
    "karpathy": ("Karpathy: Neural Networks, Zero to Hero", "https://karpathy.ai/zero-to-hero.html"), "mml": ("Mathematics for Machine Learning (free book)", "https://mml-book.github.io/"),
    "ng": ("Andrew Ng: Machine Learning Specialization", "https://www.deeplearning.ai/courses/machine-learning-specialization/"), "cs224n": ("Stanford CS224N", "https://web.stanford.edu/class/cs224n/"),
    "attention": ("Attention Is All You Need (paper)", "https://arxiv.org/abs/1706.03762"), "pagedattn": ("PagedAttention (vLLM paper)", "https://arxiv.org/abs/2309.06180"), "arxiv": ("arXiv", "https://arxiv.org/"),
    "effective_agents": ("Anthropic: Building Effective Agents", "https://www.anthropic.com/engineering/building-effective-agents"), "anthropic_research": ("Anthropic research", "https://www.anthropic.com/research"),
    "owasp_llm": ("OWASP Top 10 for LLM Applications", "https://genai.owasp.org/llm-top-10/"), "nist_rmf": ("NIST AI Risk Management Framework", "https://www.nist.gov/itl/ai-risk-management-framework"),
    "iso42001": ("ISO/IEC 42001", "https://www.iso.org/standard/42001"), "eu_ai": ("EU AI Act (European Commission)", "https://digital-strategy.ec.europa.eu/en/policies/regulatory-framework-ai"),
}
MODULE_LINKS = {
    "M0.3": ["mml"], "M2.3": ["sklearn", "umap"], "M3.3": ["xgboost", "lightgbm"], "M3.4": ["sk_pipe"], "M4.2": ["pytorch_tut", "karpathy"],
    "M4.3": ["pytorch", "pytorch_tut", "colab", "kaggle", "attention"], "M6.1": ["mlflow", "wandb"], "M6.3": ["sk_perm"], "M6.4": ["fastapi", "docker", "mlflow"],
    "0.3": ["mml"], "2.1": ["karpathy"], "2.2": ["pytorch", "pytorch_tut", "colab", "kaggle"], "2.3": ["hf_docs", "karpathy"], "2.4": ["attention", "pagedattn"], "2.5": ["hf_course", "pytorch_tut"],
    "3.4": ["pgvector", "qdrant", "pinecone", "faiss", "chroma"], "4.3": ["langgraph", "mcp"], "4.4": ["langgraph", "oai_agents", "claude_docs"],
    "5.3": ["langfuse", "phoenix", "otel", "langsmith"], "6.2": ["peft", "trl", "unsloth"], "6.3": ["deepspeed", "pytorch"], "6.4": ["vllm", "llamacpp", "ollama"],
    "7.1": ["litellm", "mcp"], "7.2": ["pg_rls"], "7.3": ["owasp_llm", "nist_rmf"], "7.5": ["nist_rmf", "iso42001", "eu_ai", "owasp_llm"], "7.6": ["terraform", "k8s", "mlflow"],
    "8.1": ["arxiv", "cs224n"], "8.2": ["arxiv", "anthropic_research"], "8.3": ["anthropic_research"], "8.5": ["vllm_gh"],
}
RESOURCE_LINKS = {
    "Mathematics for Machine Learning (Deisenroth, Faisal, Ong)": "mml", "Andrew Ng, Machine Learning Specialization": "ng", "scikit-learn user guide (model evaluation, pipelines)": "sklearn",
    "Andrej Karpathy, Neural Networks: Zero to Hero": "karpathy", "Anthropic, Building Effective Agents; Model Context Protocol docs": "effective_agents", "Hugging Face courses; TRL and PEFT docs; vLLM docs": "hf_course",
    "OWASP Top 10 for LLM Applications; NIST AI Risk Management Framework": "owasp_llm", "Stanford CS224N and CS336": "cs224n",
}
# Things the app cannot run, grouped, with one line on what each is and why it is not here.
NOT_HERE = [
    {"group": "Deep learning and GPUs", "items": [
        ("PyTorch", "The standard library for building and training neural networks.", "No PyTorch or GPU in this app.", ["pytorch", "pytorch_tut"]),
        ("Free GPU notebooks", "Run PyTorch code with a GPU without buying one.", "A hosted service; this app is local.", ["colab", "kaggle"]),
        ("Transformers, tokenizers and the Hugging Face course", "Pre-trained models and the standard LLM course.", "Needs model downloads and usually a GPU.", ["hf_docs", "hf_course"])]},
    {"group": "Fine-tuning and serving", "items": [
        ("PEFT and TRL (LoRA, SFT, DPO)", "Parameter-efficient fine-tuning and preference training.", "Training cannot run here; the LoRA size tool only does the arithmetic.", ["peft", "trl"]),
        ("Unsloth and DeepSpeed", "Faster fine-tuning and distributed training.", "Need GPUs.", ["unsloth", "deepspeed"]),
        ("vLLM, llama.cpp and Ollama", "Serving engines and local model runners.", "Need model weights and (for speed) a GPU.", ["vllm", "llamacpp", "ollama"])]},
    {"group": "Retrieval and vector search", "items": [
        ("Vector databases and indexes", "Store learned embeddings and search them fast (HNSW, IVF).", "Need an embedding model and a database server; hybrid search here uses an n-gram stand-in.", ["pgvector", "qdrant", "pinecone", "faiss", "chroma"])]},
    {"group": "Agents and observability", "items": [
        ("Agent frameworks", "Orchestration for multi-step and multi-agent systems.", "Not installed; the AI Lab agent loop is hand-written.", ["langgraph", "oai_agents", "claude_docs"]),
        ("Tracing and eval platforms", "Record every model call and score quality over time.", "Hosted or server tools; the trace analyser reads a pasted log instead.", ["langfuse", "phoenix", "langsmith", "otel"])]},
    {"group": "Classical ML libraries", "items": [
        ("XGBoost and LightGBM", "Fast gradient-boosted trees for tabular data.", "Not installed by default; ML Lab has histogram boosting.", ["xgboost", "lightgbm"]),
        ("PCA, DBSCAN and UMAP", "Dimensionality reduction and density clustering.", "Not built; use scikit-learn and umap-learn in a notebook.", ["sklearn", "umap"]),
        ("Experiment tracking", "Track runs, parameters and metrics across experiments.", "ML Lab keeps its own run log; MLflow and W&B are separate tools.", ["mlflow", "wandb"])]},
    {"group": "Platform, security and compliance", "items": [
        ("Gateways, containers and orchestration", "Route model calls; package and run services.", "Cannot run clusters or gateways here.", ["litellm", "docker", "k8s", "terraform"]),
        ("Frameworks and standards", "What auditors and customers ask about.", "Reading and mapping exercises; nothing here certifies or audits.", ["owasp_llm", "nist_rmf", "iso42001", "eu_ai"])]},
    {"group": "Learning resources", "items": [
        ("Courses and papers", "Where to study what the app does not teach.", "Study material, not a tool.", ["karpathy", "ng", "mml", "cs224n", "attention", "pagedattn", "effective_agents", "anthropic_research"])]},
]


def _lk(keys):
    return [{"label": L[k][0], "url": L[k][1]} for k in keys]

PATHS = {"ml": ML, "ai": AI}
STATUSES = ("built", "partial", "guide", "cannot")
SLIPS = [
    "Your curriculum's schedule table writes the Level 0 duration as '6‘10 weeks' with a stray quote mark in place of a dash.",
    "The curriculum puts XGBoost, LightGBM, UMAP and PCA in Level 1; this app has histogram gradient boosting but not those libraries or PCA.",
    "Level 6 and Level 7 gate projects (vLLM serving, a multi-tenant platform, Terraform, Kubernetes) need cloud or GPU resources; here they are design and arithmetic exercises.",
    "The resource lists are from general knowledge, not a fresh web check. Editions and course contents change.",
    "The 12 to 18 month estimate assumes 10 to 15 hours a week; most people also need a repeat pass over Levels 1 and 2.",
]


def _ws() -> str:
    return workspaces.active()


def _key(track: str) -> str:
    return f"learnpath:{track}:{_ws()}"


def _load(track: str) -> dict:
    try:
        d = json.loads(state.kv_get(_key(track)) or "{}")
    except ValueError:
        d = {}
    return d if isinstance(d, dict) else {}


def _check(track: str) -> dict:
    if track not in PATHS:
        raise PathError("Learning paths exist for 'ml' and 'ai'.", 404)
    return PATHS[track]


def path(track: str) -> dict:
    p = _check(track)
    prog = _load(track)
    done = set(prog.get("done", [])); gates = set(prog.get("gates", []))
    levels, tot, dn = [], 0, 0
    counts = {s: 0 for s in STATUSES}
    for lv in p["levels"]:
        mods = []
        for m in lv["modules"]:
            counts[m["status"]] += 1
            mods.append({**m, "done": m["id"] in done, "links": _lk(MODULE_LINKS.get(m["id"], []))})
        d = sum(1 for m in mods if m["done"]); tot += len(mods); dn += d
        levels.append({**{k: v for k, v in lv.items() if k != "modules"}, "modules": mods, "done": d, "total": len(mods), "gate_passed": lv["id"] in gates})
    return {"track": track, "title": p["title"], "intro": p["intro"], "levels": levels, "done": dn, "total": tot, "pct": round(dn / tot * 100) if tot else 0,
            "gates_passed": len(gates), "coverage": counts,
            "resources": [{**r, "url": L[RESOURCE_LINKS[r["name"]]][1] if r["name"] in RESOURCE_LINKS else None} for r in p["resources"]],
            "not_here": [{"group": g["group"], "items": [{"name": n, "what": w, "why": y, "links": _lk(k)} for n, w, y, k in g["items"]]} for g in NOT_HERE],
            "link_note": "Links go to each project's official home or documentation page. They were not click-tested from the build environment: run scripts/check_links.py on your own computer to find any that have moved.", "capstones": p.get("capstones", []), "rubric": p.get("rubric", []), "slips": SLIPS,
            "limit": "Tick a module only after you have PROVED it (a test, a metric or a written explanation another person could follow). 'Built' means this app has something to run, not that it replaces the course."}


def _ids(track: str):
    p = _check(track)
    return {m["id"] for lv in p["levels"] for m in lv["modules"]}, {lv["id"] for lv in p["levels"]}


def set_module(track: str, mid: str, done: bool) -> dict:
    mods, _ = _ids(track)
    if mid not in mods:
        raise PathError("No such module.", 404)
    prog = _load(track); s = set(prog.get("done", []))
    (s.add if done else s.discard)(mid)
    prog["done"] = sorted(s)
    state.kv_set(_key(track), json.dumps(prog))
    return {"saved": True}


def set_gate(track: str, level: str, passed: bool) -> dict:
    _, lvls = _ids(track)
    if level not in lvls:
        raise PathError("No such level.", 404)
    prog = _load(track); g = set(prog.get("gates", []))
    if passed:
        lv = next(l for l in _check(track)["levels"] if l["id"] == level)
        missing = [m["id"] for m in lv["modules"] if m["id"] not in set(prog.get("done", []))]
        if missing:
            raise PathError(f"Finish the modules first: {', '.join(missing)}. A gate is passed by shipping the project, so tick the modules you have proved.")
    (g.add if passed else g.discard)(level)
    prog["gates"] = sorted(g)
    state.kv_set(_key(track), json.dumps(prog))
    return {"saved": True}
