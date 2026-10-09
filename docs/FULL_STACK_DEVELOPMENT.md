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
