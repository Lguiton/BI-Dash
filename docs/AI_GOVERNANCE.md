# AI governance lab and the Python libraries tour

From "The Big Book of AI Governance" (Databricks) and a Python-for-AI infographic of 19 libraries.

## Built (AI Engineering track)
- **AI governance lab**: an asset registry (models, agents, MCP servers, tools, coding agents, datasets, prompts) with a risk tier and issue list per asset; a shadow-AI check against what you see in use; a use-case risk tier modelled on the EU AI Act's four levels with NIST AI RMF pointers; a policy simulator (allow, deny, approve; deny beats approve beats allow; default deny); spend attribution by user, team, app and model with budgets, outliers and a "move simple tasks to a cheaper model" what-if; and a reference tab mapping the book's ideas to what is here.
- **Python libraries behind AI work**: the 19 libraries with area, good-for, a first exercise, install status, docs link and an offline demo (12 run on a typical install; the others report the pip command or why they cannot run in a page).
- Steps `ai-gov-registry`, `ai-gov-risk`, `ai-gov-policy-spend`, `py-libs-tour`, 14 questions, three agent notes, five tool-map rows.

## Not built
Unity Catalog, Unity Gateway, MLflow Tracing on Databricks, Genie, Lakewatch: platform products. Live enforcement of budgets, guardrails, approvals and on-behalf-of-user identity needs a gateway in front of real traffic. Free ways to learn the same ideas: OpenTelemetry, MLflow, Open Policy Agent, LiteLLM.

## Mistakes and overclaims in the sources
See `SLIPS` in `ai_gov.py` and `pylib_map.py`. In short: vendor figures (30%, 50%, 14,000 organisations, "only") with no method; unsourced "model every five days" and Gartner forecast; five principles that turn into three themes; guardrails presented as a cure for injection; no regulation, bias testing or accountability; and an infographic that calls general web and cloud tools "AI", mislabels PyTorch/TensorFlow, Airflow and Kivy, and promotes a lead-generation offer.

## Limits
The risk tier is a learning aid, not legal advice. The registry and policy simulator enforce nothing. Spend uses the usage you paste. The PyTorch demo has not been run in the build environment (it could not be installed there); the others have.
