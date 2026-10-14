# Machine learning and AI engineering learning paths

Open the **ML** or **AI Engineering** track and find *Machine learning: beginner to advanced* or *AI engineering: beginner to master*. The first tab is the path; the other tabs are tools you can run for free, offline.

## The paths
- **AI engineering** follows your nine-level curriculum (Levels 0 to 8, each with a gate project, the 1 to 5 rubric, and the five capstone options). Module names and gate projects come from that document; the "where in the app" and "prove it" columns are added here.
- **ML** is a seven-level companion (M0 foundations, M1 workflow, M2 core algorithms, M3 metrics and tabular models, M4 deep learning, M5 specialised problems, M6 MLOps and responsible ML).
- Every module carries one of four badges: **Built here** (something to run), **Partly here**, **Study outside**, **Can't run here** (needs GPUs, cloud or libraries this app does not install).
- Tick a module only after you have *proved* it. A level's gate can be marked passed only when all its modules are ticked. Progress is saved per workspace.

## ML tools
| Tool | What it shows | Honest limit |
|---|---|---|
| Bias and variance | Polynomial fits of rising degree; training error always falls, validation error turns up. | One small random split: change the seed and the winner moves. |
| Gradient descent | Linear or logistic regression; a learning rate that diverges, crawls or converges. | Two features, synthetic data. |
| Algorithms from scratch | kNN, logistic regression, a decision tree and naive Bayes on two-moons data against the majority baseline. | Two features, one split; for understanding, not speed. |
| Scores and thresholds | Paste `score,label`: ROC-AUC, PR-AUC, calibration (Brier, ECE) and the cheapest threshold for your miss and false-alarm costs. | Only as good as the rows you paste; rows used in training make it optimistic. |
| Leakage scan | Paste a CSV and name the target: near-perfect single-column signal, outcome-sounding names, ID columns, duplicates, rare classes. | Single-column heuristics; misses leaks hidden in combinations. |

## AI engineering tools (none calls a model)
| Tool | What it does | Honest limit |
|---|---|---|
| Retrieval metrics | recall@k, precision@k, MRR, nDCG and the abstain rate on unanswerable questions. | Binary relevance; your labels decide quality. |
| Hybrid search | BM25 plus a character n-gram vector, merged by reciprocal rank fusion, then MMR for diversity. | **The vector is a stand-in, not a learned embedding**: it matches spelling, not meaning. |
| Structured output | Parses a model reply (strips code fences and prose), checks types, enums, ranges, patterns and extra fields, writes the repair prompt. | Shape only; a valid object can still be false. |
| Agent trace | Finds identical repeated calls, three failures in a row, step-budget overruns, side-effect tools without approval, no final answer, and the token cost. | Reads the log you paste; tool names are matched by keyword. |
| Eval statistics | Wilson interval, test-set size, A/B significance, judge-versus-human kappa, pass@k. | Independent-case assumptions; not paired tests. |
| Reliability | Back-off schedule and worst-case time, error budget, chained availability with a backup provider, retry amplification across layers. | Assumes independent failures. |
| Fine-tune data | JSONL format, roles, duplicates, empty messages, train-test overlap. | Format and duplication, not quality or truth. |
| LoRA size | Full fine-tune versus LoRA memory and compute, Chinchilla token rule of thumb. | Ignores activations and overhead; no GPU is used. |
| PII and injection scan | Redacts emails, phone, SSN-like, IPs, Luhn-valid cards and key patterns; flags instruction-like text, exfiltration phrasing and hidden unicode. | Patterns only; "clean" never means "safe". |

## Already in the app (not duplicated)
AI Lab and routing, AI workbench (token budget, RAG evaluation, tool safety, prompt versions, cost planner), MLOps lab, Inference lab, AI fundamentals, ML Lab, and the `ai_engineering/` scripts.

## Not built
PyTorch and GPU training, transformer and diffusion models, learned embeddings and vector databases (pgvector, Qdrant, Pinecone), LoRA/QLoRA training runs, vLLM serving, LangGraph and other agent frameworks, Langfuse/LangSmith/OpenTelemetry, Terraform and Kubernetes, XGBoost/LightGBM, PCA/UMAP/DBSCAN, and certification-style compliance work. The path says so module by module and gives a "prove it" you can do on your own machine or a free notebook service.

## Slips and cautions in the source
- The curriculum's duration table has a stray quote mark in "6'10 weeks" (Level 0).
- It lists XGBoost, LightGBM, UMAP and PCA in Level 1; this app has histogram gradient boosting but not those.
- Level 6 and 7 gate projects need GPUs, cloud and orchestration; here they are design and arithmetic exercises.
- The resource lists are from general knowledge, not a fresh web check. Confirm current editions and links.
- 12 to 18 months assumes 10 to 15 hours a week; most people repeat Levels 1 and 2.

## Links to what the app cannot run
Every module marked *Study outside* or *Can't run here* now has a **Get it** line with links (PyTorch, Hugging Face PEFT/TRL, vLLM, vector databases, LangGraph, Langfuse, XGBoost, Terraform, OWASP, NIST and more). The same links are grouped under **Can't run here: where to get it**, with one line on what each thing is and why it is not in this app. Resource entries link to their pages where one exists.

The links are official home or documentation pages written from general knowledge. The build environment has no general internet access, so they were **not click-tested**. Run `python scripts/check_links.py` on your own computer to find any that have moved; a FAIL can also mean a site blocks scripts, so open it in a browser before deciding.
