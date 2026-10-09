# AI engineering lab

Five exercises that mirror what AI engineers actually build. **No API key needed** - without one, `llm.py` falls back to a small rule-based stub so you can practise the plumbing for free. With keys in `backend/.env` (Google, OpenAI, Anthropic), the same code calls real models: simple tasks go Gemini -> OpenAI -> Claude, `kind="complex"` goes Claude -> OpenAI -> Gemini, with automatic fallback.

```bash
pip install -r requirements.txt
python 01_structured_output.py      # messy text -> validated JSON, bounded retries
python 02_rag.py "How is margin calculated?"   # retrieval + cited answer over this project's docs
python 03_evals.py                  # golden-set eval of a text-to-SQL feature (it catches a real bug!)
python 03_evals.py --compare        # same eval on every provider you have a key for: a model bake-off
python 04_mcp_server.py             # MCP server exposing 3 read-only tools (launched by a client)
python 05_prompt_injection.py       # deterministic defences against poisoned data
python -m pytest tests -q
```

| # | Skill | Real tools | What "done" looks like |
|---|-------|-----------|------------------------|
| 1 | Structured output | pydantic, JSON schema | invalid model output never reaches your database |
| 2 | RAG | scikit-learn TF-IDF (swap in embeddings later) | every answer cites its source, "I don't know" when nothing matches |
| 3 | Evals | DuckDB, golden set | a number you can track when you change a prompt |
| 4 | MCP | `mcp` SDK | Claude Desktop can query your data through typed, read-only tools |
| 5 | Security | allow-lists, argument validation | a poisoned row cannot make the agent run `DROP TABLE` |

Also see the **AI Lab** page in the dashboard (`/ai`): a working Claude tool-use agent over this data (`backend/app/services/ai_agent.py`).

## Honest notes
* The offline stub is deliberately simple (and, in exercise 3, deliberately wrong about margin so the eval has something to catch).
* Live-model behaviour was **not** exercised in the environment this lab was built in (no key there). Expect the live eval score to differ, and use that gap as your learning.
* `mcp` 2.x renamed `FastMCP` to `MCPServer`; the script handles both. Keep API keys in `backend/.env` (git-ignored), never in code. Tests set `BI_OFFLINE=1`, so they never spend money even if your keys are present.
* Cost: live calls cost money. Exercises 1-3 make a handful of small requests.

## Portfolio ideas
Add 20 golden questions and a CI job that fails below 90% - then show a before/after chart when you improve the prompt. Add a `--live` column to the eval comparing two models. Package exercise 4 and demo it in Claude Desktop.
