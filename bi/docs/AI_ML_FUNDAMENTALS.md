# AI and ML fundamentals lab

Open the **AI Engineering** or **ML** track and scroll to *AI fundamentals*. Tabs:

- **Concepts**: how AI, ML, deep learning, foundation models and LLMs nest; types of AI; the approach chooser; the six steps of AI adoption.
- **Learning**: learn rules from (synthetic) data with a train/validation/test split, a metrics calculator, k-means (unsupervised), Q-learning (reinforcement), RPA fit check and a reactive-versus-proactive thermostat.
- **Neural networks**: one neuron by hand, parameter counting, a small network trained with backpropagation (try XOR with and without a hidden layer), and convolution on a small image.
- **NLP**: tokenization, stemming versus lemmatization, part-of-speech tags, entities, sentiment, spam cues, intent and slots, and a text classifier you train yourself.
- **Chatbot and RAG**: an intent chatbot with a hand-over threshold, and retrieval-augmented generation over passages you paste.
- **Reference**: generative model types, foundation model trade-offs, agents, robots, edge/IoT, uses, careers, corrections and what cannot be built.

## Limits
Training large models, GANs, diffusion, vision or speech models and real robots cannot run here. Demos use tiny or synthetic data with fixed seeds and teach the mechanics; they are not medical, financial or legal tools. The NLP tools use short word lists and keyword-based retrieval (no embeddings), so they miss synonyms and sarcasm. Statistics quoted in the source course are dated.

## AI workbench (AI Engineering track)
Five checks. Only the live prompt test calls a model, and only after you confirm:
- **Context and cost:** estimate tokens, check a prompt fits a window you enter, plan RAG chunking and plan monthly spend with caching and routing savings. Prices and window sizes are always typed in because they change.
- **RAG evaluation:** your documents and test questions (include ones they can't answer). Compares three chunk sizes by hit rate, MRR and correct "found nothing".
- **Tool safety:** tick what each agent tool can do. Flags destructive actions without confirmation, sends without an allow-list, and private data + untrusted content + an outside channel together.
- **Prompt versions:** save, diff and delete versions per workspace; compare outputs pasted from two versions against required and forbidden text, or **run the tests live**. A live run first previews the number of calls and tokens (no calls made), then needs a ticked confirmation, respects the workspace's AI on/off setting, stops early if the provider refuses, and keeps the last five runs. It sends the prompt and test inputs to your provider and uses your daily allowance, so keep personal data out of test inputs.
- **Checklist:** what to have before shipping. Record results in the AI use case brief, Model card, Data card and AI incident review templates.

Limits: token counts are estimates; retrieval is keyword-based, so synonyms are missed; the tool review finds design risks and cannot prove safety; prompt tests check text rules, not quality, and live replies vary from run to run.

## MLOps lab (ML and AI tracks)
Source: the Databricks *Big Book of MLOps*, 2nd edition (2023). It is a vendor guide, so the principles are used and the products are not.

**What it adds on top of the model registry** (ML Lab > Models, which already had versions, stages, predict and a drift check):
| Tool | What it does | Honest limit |
|---|---|---|
| Promotion gate | Checks a version loads, scores a sample, has documented inputs, beats the naive baseline by a margin you set, and has a note. Passing sets the *challenger* alias. | Catches sloppy models, not wrong ones. No slice checks. |
| Champion / challenger | Compares the challenger with the live version (or with the baseline on a first deployment). Promote and roll back both need a confirmation, and both are audited. | Uses the scores stored at training time, not a fresh common test set. |
| Shadow run | Both versions score the same made-up rows; shows how often they disagree. | Rows are drawn from training ranges, not real traffic, and there are no true outcomes. |
| Traffic split and rollout plan | Shows how a canary or A/B split behaves (hashing an id) and writes advance and rollback rules before the first step. | A plan and a record. This app does not route live traffic. |
| Load test | p50, p95, p99, throughput and errors against a latency target you set. | One process, one request at a time, no network, no autoscaling, no stress to failure. |
| Retrain advice | Reads saved drift checks and says stable / watch / investigate, with steps. | Input drift only. Do not automate retraining until you have handled alerts by hand. |
| LLM approach chooser | Prompt, RAG, fine-tune or pre-train; hosted vs self-hosted; vector library vs database; cost levers; evaluation advice. | Rules of thumb from one guide. |
| Feedback log | Thumbs and "asked for a human" signals per prompt version, with a warning when there are fewer than 20. | Hand-kept, capped at 500; keep personal details out of notes. |

**Slips and caveats in the source:** performance figures and "only tool" claims are the vendor's own; it is dated (Llama 2, MLflow AI Gateway); the "Merge code" section repeats a paragraph from the training section; "only a small number of weights are updated" is true of parameter-efficient fine-tuning, not full fine-tuning; automated promotion is shown as the default although the book itself says regulated settings need human approval.

**Not built:** Unity Catalog, Model Serving, Lakehouse Monitoring, Workflows, MLflow, MosaicML, autoscaling or GPU serving, fine-tuning, quantization, vector databases, CI/CD pipelines. The Qual template *Model release record* captures the gate result, rollback plan and what you will watch.
