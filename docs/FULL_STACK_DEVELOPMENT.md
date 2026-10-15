# Full stack development: the vocabulary and one vertical slice

A full stack developer owns a feature from the database table to the pixel. This project is the practice ground: a
FastAPI + DuckDB backend, a Next.js + React + TypeScript frontend, and pytest tests. Open **Tracks > Full Stack Developer**.

## Vocabulary
* **Endpoint**: a method plus a path, like `GET /api/pm`. The API map lists every one of them from the running app.
* **Contract**: the agreed shape of requests and responses. FastAPI turns Pydantic models into the OpenAPI schema (`/docs`).
* **Validation**: reject bad input at the edge (a 422), never deep inside.
* **Parameterised SQL**: values go in `?` placeholders, never glued into the SQL string. This is what stops SQL injection.
* **Idempotent**: doing it twice has the same effect as doing it once (PUT and DELETE should be).
* **Status codes**: 2xx worked, 4xx you sent something wrong, 5xx we failed.
* **CORS**: the browser's rule about which web origins may call the API. List origins; don't use `*`.
* **Fixture**: test setup. Each test here gets its own temporary database, so tests can't affect each other.
* **Vertical slice**: one thin feature through every layer (table, API, UI, test) before building wide.

## One vertical slice, step by step
1. **Table**: decide columns, types and the primary key (open the Schema page).
2. **Query**: prototype the SQL in SQL Lab.
3. **API**: use *Scaffold* to generate a router from the table; read it; tighten validation; register it in `app/main.py`.
4. **Try it**: send requests from *API map and tester*. Try a bad body and read the 422.
5. **Type**: add the TypeScript interface that mirrors the response.
6. **UI**: a panel that handles loading, empty, error and success. Look at `PmPanel.tsx`.
7. **Test**: at least one happy path and one failure path.
8. **Release**: tests green, configuration reviewed (*Stack and config* tab), backup taken.

## Honest limits
The scaffold is generated from columns only. It knows nothing about your business rules, permissions or relationships, so
treat it as a first draft. The "Stack and config" tab shows facts the running app can see; it is not a security audit.
The request tester can only call this app's own `/api/` paths, and only sends writes while the Practice workspace is active.

## Software engineering lab
Open *Software engineering* in the Full Stack tab. Seven sub-tabs:
- **Process**: the six-phase lifecycle, a Waterfall / V-model / Agile chooser that shows its reasons, and the testing levels and types.
- **Requirements**: a user-story checker that flags vague words, and a traceability matrix that finds untested requirements and orphan tests.
- **Versions**: compare two versions, bump major / minor / patch, and test a version against a range such as `^1.2.0` or `~1.2`.
- **Testing**: a regression-test prioritiser.
- **Architecture**: a pattern advisor, a production topology that lists single points of failure, a state-diagram checker and a class-diagram builder.
- **Pseudocode**: turns plain pseudocode (IF, WHILE, FOR, INPUT, PRINT) into a flowchart.
- **Reference**: documents, tools, stacks, languages, environments and corrections to common course errors.

Limits: CI/CD, containers, load balancers and cloud hosting are explained but cannot run here. Availability figures are illustrative and assume independent failures. The method and architecture scores explain trade-offs; they do not decide for you. Qual templates added: SRS, design document, test plan and SOP.

## Generate code (copy and paste)
Full Stack field dashboard and the Full Stack track tools both have a **Generate code** tab. Pick a language (Python, JavaScript, TypeScript, SQL, Bash, PowerShell), say what you want in a sentence or two, and optionally paste your own code or table columns. The assistant writes the code and a short note (what it does, how to run it, how to check it worked, cautions).
* Complex questions route to Claude first. Passwords and keys you type are blanked before sending; the request and context are capped (1,500 and 4,000 characters).
* Before you see it: Python, JavaScript and SQL get the same offline review as the Code Workbench. Bash is syntax-checked with `bash -n` (parse only). TypeScript and PowerShell are not syntax-checked. Every language gets a risk scan: recursive deletes, DROP/TRUNCATE, DELETE or UPDATE without WHERE, curl-pipe-to-shell, Invoke-Expression, eval, shell=True, turned-off certificate checks, world-writable permissions, and secrets written into the code.
* **Nothing is ever run.** Copy it, read it, and try it on sample data. A clean check means no common mistakes were found, not that it does what you meant. Generated code can be wrong.
* Files: `services/codegen.py`, `routers/code.py` (`/api/code/generate`), `panels/GenerateCode.tsx`, `tests/test_codegen.py`.
