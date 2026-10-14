# Part 8: Full Stack Developer

## The role in one page

A full stack developer builds a feature from the database table to the pixel on the screen, and keeps it working afterwards. In this project that means a DuckDB database, a FastAPI backend written in Python, a Next.js and React frontend written in TypeScript, and pytest tests. You decide the columns, write the query, expose it as an endpoint, describe the response shape, draw the screen, and write the test that proves it. You do not need to be the best at any one layer. You need to understand all of them well enough that the joins between them do not break.

You work with product people (who say what is wanted), designers, other developers, testers, and whoever runs the system. A typical day: pick up a small change, read the existing code around it, prototype the SQL, add or change an endpoint, update the TypeScript type, adjust a component, write a test, run everything, and read a log to see why something is slow or failing. A lot of the day is reading, not writing.

Good looks like a small, boring, reliable change. The endpoint rejects bad input with a clear message. The SQL uses bound parameters. The screen shows loading, empty, error and success states. There is a test that fails if you break the behaviour. Another developer can read the change in ten minutes. Releases are uneventful because you checked configuration and took a backup first.

What the role is not: it is not knowing every framework, and it is not typing code fast. It is not design or security research (Part 9 covers security), and it is not data engineering at scale (Part 4). A full stack developer who ships features without tests, or who pastes SQL together from user input, is doing the job badly however quickly.

The honest hard parts:

- The layers move at different speeds. Frontend libraries change fast; SQL and HTTP barely change. Learn the stable parts first.
- Most bugs live between layers: a field renamed on one side, a null the UI did not expect, a status code nobody handled.
- Tests feel slow to write until the first time they save you.
- You will always be a beginner at something. The skill is knowing how to find out.
- Small tools hide complexity. A personal-scale app with no login is fine for one person and dangerous the moment it is exposed.

## How to use this part

Four levels, times at about five hours a week.

| Level | Focus | Time at ~5 h/week |
|---|---|---|
| 1. Foundations | HTTP, endpoints, JSON, running the app | about 15 hours, 3 weeks |
| 2. Practitioner | Validation, bound SQL, services, types | about 25 hours, 5 weeks |
| 3. Advanced | Testing, UI states, middleware, performance | about 30 hours, 6 weeks |
| 4. Expert | Trade-offs, failure modes, review, team scale | about 25 hours, 5 weeks |

The examples use a typical modern stack: a Python backend with FastAPI, an SQL database, a TypeScript and React frontend, and pytest for tests. Every idea transfers to other stacks (Express, Django, Rails, Vue, Go), so if you prefer another, translate the examples as you go. Build one small project alongside the reading, for example a task list with a table, an API and a screen, and treat it as your practice ground.

Tests run from a terminal with your test runner; with pytest, run `pytest` in the backend folder. Run your backend with its dev server (for FastAPI, `uvicorn` with a module name and port) and your frontend with its dev command. A FastAPI app serves interactive API documentation at `/docs`.

Keep honest limits in mind: generated code is a first draft, a configuration check is not a security audit, and any request tool you build or use should only touch systems you own.

## Level 1: Foundations (beginner)

### What you will be able to do

- You can explain what an endpoint is and read a method and path such as `GET /api/projects`.
- You can read an HTTP status code and say whether the client or the server is at fault.
- You can read a JSON response and describe its shape.
- You can start the backend and frontend and find the API documentation.
- You can send a request with curl or a REST client and explain a 422 response.
- You can draw the layers a request passes through, from browser to table and back.

### Core ideas

#### Layers and the round trip

A request travels through layers. The browser runs React code, which calls a fetch function in a small shared module, which sends an HTTP request to the backend. The backend framework matches the method and path to a handler. The handler calls service code, which runs SQL against the database. The result goes back as JSON, the frontend turns it into state, and React draws it.

Knowing the path tells you where to look. A blank screen with a 200 response is a frontend problem. A 500 is a backend problem. A 422 means the request did not match what the endpoint expected. An empty table with a 200 might be a SQL problem, or just the wrong database file or environment. Always locate the layer before changing code.

#### Endpoints, methods and paths

An **endpoint** is a method plus a path. `GET /api/projects` reads; `POST /api/requirements` creates; `PUT /api/requirements/3` replaces or updates item 3; `DELETE` removes. The path has a stable shape: `/api/<area>/<thing>/<id>`. Query parameters carry options: `/api/calc/capacity?load=50&capacity=100&growth=10`.

Most frameworks can list every endpoint from a machine-readable OpenAPI schema; FastAPI serves it at `/openapi.json` and renders it at `/docs`. Reading that map before reading code is a good habit: you learn what the system promises before you see how it keeps the promise.

#### Status codes

The first digit tells you who is at fault. **2xx** worked (200 OK, 201 Created). **4xx** the client sent something wrong: 400 bad request, 404 not found, 409 conflict, 422 the body or parameters did not match the schema. **5xx** the server failed. This project uses the split deliberately: a missing required query parameter or a number outside a declared range gives a 422 from the framework, while a rule broken inside the logic (a due date in the past, say) gives a 400 with a readable message.

Worked example: `GET /api/tasks?limit=0` returns 422 because `limit` is declared to be at least 1. The same call with `limit=20` returns 200 and a list. The code did not change; the input did.

#### JSON

JSON is the text format between layers. It has objects (`{"a": 1}`), arrays (`[1, 2]`), strings, numbers, booleans and `null`. It has no dates: a date travels as a string such as `"2026-10-09"`, and both sides agree how to read it. A response like `{"status": "healthy", "engine": "DuckDB"}` from `GET /health` is an object with two string fields. When you read a response, write down its shape (field names and types) before you read the values.

#### Reading an error message

FastAPI's validation errors arrive as a list of objects, each with where the problem is, a message, and a type. A small shared fetch module can turn them into one readable line by joining the messages. Read the error before touching the code: it usually names the field. If the message is generic ("Request failed (500)"), the server's log is where the real cause is.

### Practice on your own

1. Install Python and run a minimal FastAPI app (or the equivalent in your stack) with a `GET /health` endpoint. Open its interactive docs page and find the endpoint, its parameters and its response.
2. Add `GET /api/tasks` with a `limit` query parameter. Call it with curl or a REST client. Record the status for `limit=20`, `limit=0` and `limit=abc`, and read each message.
3. Draw the layers a click passes through in a small app you know, naming the file or technology at each step.
4. Write down the shape (field names and types, not values) of three real JSON responses from a public or local API you can call.
5. Cause a 404 and a 405 on purpose and write one sentence on how they differ.

### Exercises

1. What does each part of `GET /api/calc/queue?arrival_rate=8&service_rate=10` mean?
2. Match the situation to a status: (a) a page that does not exist, (b) the server crashed on a valid request, (c) a body missing a required field, (d) a new row was created.
3. Is `{"id": 3, "done": false, "due": null}` valid JSON? Name each field's type.
4. A request returns 200 but the screen is blank. Which layers do you check, and in what order?
5. A POST from your REST client returns 405. Give two reasons it might.
6. Write down, in words, the path of a click on "Calculate" in the queueing calculator through every layer and back.
7. Why does an API map help before you read the code?
8. What is the difference between a 400 and a 422 in this project?

### Answers and hints

1. Method GET (read). Path `/api/calc/queue` (the queue calculator). Query parameters arrival_rate = 8 and service_rate = 10 (same time unit).
2. (a) 404. (b) 500. (c) 422. (d) 201.
3. Yes. id is a number, done a boolean, due is null (no value).
4. Browser network tab or a REST client first (is the body what you expect?), then the type the UI reads, then the component state and rendering.
5. 405 means the method is not allowed on that path: the endpoint only accepts GET, or you used the wrong path. A 404 would mean no such path at all. Read the API map to see which methods exist.
7. It tells you what the system offers and what each endpoint expects, so you know the contract before reading the implementation.
8. A 422 comes from the framework's declared validation (types, ranges, missing fields). A 400 comes from the project's own rule check inside the logic.

### Checkpoint

1. Name the layers a request passes through.
2. What does the first digit of a status code tell you?
3. What is an endpoint?
4. Which status means the body did not match the schema?
5. How does a date travel in JSON?
6. Where do you look first when a response is 500?
7. Where is the API documentation, and what produces it?
8. Why should you test writes only against a practice database?

Common mistakes:

- Changing code before locating which layer is at fault.
- Reading only the values in a response and not its shape.
- Treating every non-200 as "the server is broken" instead of reading the 4xx versus 5xx split.
- Ignoring the error message, which usually names the field.
- Testing writes against data you care about.
- Mixing up the path (identifies a thing) and the query string (options).

## Level 2: Practitioner (intermediate)

### What you will be able to do

- You can write a FastAPI endpoint with typed, validated parameters and a Pydantic body.
- You can write SQL with bound parameters and explain what injection is and why placeholders stop it.
- You can separate a thin router from a testable service and map errors to status codes.
- You can mirror an API response with a TypeScript interface and say what the type does not guarantee.
- You can read a shared fetch module and explain how its errors reach the screen.
- You can generate starter code from a table and name three things it does not know.

### Core ideas

#### Validation at the edge

Reject bad input where it enters, not deep inside. FastAPI does this from declarations. A query parameter declared `Query(gt=0)` returns 422 for zero or negative values before your function runs. A Pydantic model does the same for bodies:

```python
from typing import Literal
from fastapi import APIRouter
from pydantic import BaseModel, Field

router = APIRouter(prefix="/api/demo")

class RequirementIn(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    priority: Literal["must", "should", "could", "wont"] = "should"

@router.post("/requirements", status_code=201)
def create(body: RequirementIn):
    return {"title": body.title, "priority": body.priority}
```

Posting `{"title": "", "priority": "urgent"}` gets a 422 listing both problems. Some codebases take `body: dict` and validate inside the service instead, returning a 400 with a plain message. Both work; the model approach gives you the documentation and the sample body in `/docs` for free, while the dict approach keeps rules next to the logic. Know which one you are looking at.

#### Parameterised SQL

SQL injection happens when user input is glued into the query text. Suppose a lookup is written as:

```python
cur.execute(f"SELECT * FROM users WHERE name = '{name}'")
```

If `name` is `x' OR '1'='1`, the query becomes `... WHERE name = 'x' OR '1'='1'` and returns every row. The fix is to send values separately:

```python
cur.execute("SELECT * FROM users WHERE name = ?", [name])
```

The database treats the value as data, never as SQL. The limit: placeholders only stand in for values. You cannot bind a table or column name. When a name must vary, check it against a list you control (a `COLS` list in the handler does this) and quote it, never accept it raw.

#### Routers stay thin; services hold the logic

Keep route handlers thin. Each handler is one or two lines and calls a function in a service module. A small helper runs the call and turns the service's own error type into an HTTP error: the service raises `AppError(message, status)`, and the helper raises `HTTPException(status, message)`. This split has three payoffs. The logic can be tested without HTTP: a test can call `queue_wait(8, 10)` directly. The HTTP rules live in one place. And the service can be reused by something that is not a web request.

#### Types that mirror the response

TypeScript interfaces describe the shape the frontend expects:

```typescript
export interface Health { status: string; engine: string }
const h = await getJson<Health>("/health");
console.log(h.engine);
```

The `<Health>` is a promise you make, not a check. A typical helper ends with `return (await res.json()) as T`. TypeScript types disappear when the code runs, so if the backend renames `engine`, the compiler stays quiet and `h.engine` is `undefined`. Mirror carefully, keep the type next to the endpoint it describes, and let a test or a quick request catch drift.

#### The fetch layer and its errors

One module should be the single place that talks to the backend. It reads the base URL from configuration (in Next.js, an environment variable such as `NEXT_PUBLIC_API_URL`) with a local default. Each helper (`getJson`, `postJson`, `putJson`, `deleteJson`) sends the request and, if the response is not OK, calls an error converter. That function reads the FastAPI `detail`: a string becomes the message; a list (validation errors) has its messages joined; an object contributes a message and a list of error lines. The result is an `ApiError` with a status, so a screen can show one banner. If the network fails, show "Can't reach the API", which is more useful than a bare "Failed to fetch".

#### What generated code gives you

A scaffold generator turns a table into starter code: SQL, Pydantic models, a CRUD router, a TypeScript interface, a React component and a test skeleton. It reads column names and types and writes text for you to paste. It cannot know your business rules, who may see what, or how tables relate. A typical generated router takes `body: dict`, so the generated Pydantic models are not yet used for validation. Treating that as a first draft, and tightening it, is the exercise.

### Practice on your own

1. Create a `tasks` table (id, title, done, due) in SQLite or any SQL engine. Write a handler that lists tasks with a bound `limit`, and another that inserts one with a Pydantic model that rejects an empty title.
2. Demonstrate injection safely on your own throwaway database: build one query with an f-string and the input `x' OR '1'='1`, see it return every row, then fix it with a placeholder and confirm it returns none.
3. Split the code into a router and a service. Make the service raise your own error type with a status, and map it to an HTTP error in one helper.
4. Write a TypeScript interface for the task response and a typed fetch helper. Rename a field on the backend and observe what the compiler does and what the browser does.
5. Generate starter code for the table with any scaffold tool (or write it by hand). Find every place a value is bound, and list three things it does not know about your tasks.

### Exercises

1. Declare a query parameter `limit` that must be an integer from 1 to 100 with a default of 20.
2. Rewrite `cur.execute(f"DELETE FROM items WHERE id = {item_id}")` safely.
3. Why can't you bind a table name with `?`, and what do you do instead?
4. A service raises `ValueError("bad")`. What does the client see? What should the service raise instead, in this project's style?
5. The backend renames `status` to `state`. What does TypeScript tell you? What does the browser do?
6. Write an interface for `{"deleted": 3}`.
7. Why is `PUT` expected to be idempotent? Give a request pair that shows it.
8. Add a Pydantic constraint so that `weight` must be between 0 and 10.

### Answers and hints

1. `limit: int = Query(20, ge=1, le=100)`.
2. `cur.execute("DELETE FROM items WHERE id = ?", [item_id])`, and declare `item_id: int` in the endpoint so FastAPI rejects non-integers.
3. Placeholders carry values only. Check the name against an allowed list and quote it with double quotes, escaping any inner double quote.
4. An unhandled exception gives a 500 with no useful message. Raise the service's own error with a status, for example `SaError("Give the requirement a title.")`, so the router returns a 400.
5. Nothing; the types compile. At runtime the field is `undefined`, and the screen shows blanks or errors.
6. `interface Deleted { deleted: number }`.
7. Sending the same PUT twice leaves the same state as sending it once. Two identical `PUT /api/requirements/3` calls with the same body leave requirement 3 identical.

### Checkpoint

1. What does edge validation mean, and what does it return when it fails?
2. What is SQL injection, and what exactly stops it?
3. What can and cannot be bound with `?`?
4. Why does the router call a service rather than hold the logic?
5. Why is `as T` in `getJson` not a safety check?
6. How does `toError` turn a FastAPI error into one message?
7. What are three things a code generator does not know?
8. When would you choose a Pydantic model over a dict body?

Common mistakes:

- Building SQL with f-strings and values.
- Binding an identifier and wondering why it fails, or pasting it in raw.
- Letting exceptions escape as 500s when the problem is the client's input.
- Trusting a TypeScript interface as proof of the response shape.
- Putting business rules in the router where they cannot be tested without HTTP.
- Using generated code without reading it.

## Level 3: Advanced

### What you will be able to do

- You can explain every line of a test client fixture and why each test gets its own database.
- You can write a happy-path and a failure-path test for an endpoint, with an expected value you computed by hand.
- You can build a React panel that handles loading, empty, error and success, and cancels stale requests.
- You can explain a timing middleware, a CORS setup and an application start-up sequence.
- You can spot an N+1 query and fix it, and paginate a list correctly.
- You can read a request's timing and decide whether it is a problem.

### Core ideas

#### An isolated test database

Open a `conftest.py` for a FastAPI project and expect something like the following. The `client` fixture does this, in order:

1. Sets three environment variables with `monkeypatch`: a database-path variable to a file inside pytest's `tmp_path`, a seed variable so sample data exists, and a scheduler variable set off so no background thread runs.
2. Closes any open database connection and state, so nothing from an earlier test leaks in.
3. Imports the app module inside the fixture, after the environment is set.
4. Opens `TestClient(app)` in a `with` block, which runs the app's start-up code.
5. Yields the client to the test, and closes everything afterwards.

`tmp_path` is a fresh folder per test, so every test starts clean and can run in any order. Without this, one test that adds a row makes another test count wrong, and the failures depend on order, which is the worst kind. The same file can hold small helpers, such as one that builds the upload dictionary for file-import tests.

#### Happy path, failure path, and a number you computed

A test is a claim with an expected value. Write the happy path and at least one failure path. Take the capacity calculator. For load 50, capacity 100 and growth 10%, months to full is ln 2 ÷ ln 1.1 = 7.27, so 7.3 after rounding.

```python
def test_capacity_endpoint(client):
    ok = client.get("/api/calc/capacity",
                    params={"load": 50, "capacity": 100, "growth": 10})
    assert ok.status_code == 200
    assert ok.json()["months_to_full"] == 7.3
    bad = client.get("/api/calc/capacity",
                     params={"load": -5, "capacity": 100, "growth": 10})
    assert bad.status_code == 422
```

The expected 7.3 came from arithmetic, not from running the code and pasting its output. A test whose expected value is whatever the code returned only proves the code is consistent with itself. Notice, too, that a generated test which accepts `201` or `422` is only a skeleton: replace it with a definite assertion.

#### Four states in the UI

Every panel that loads data has four states: **loading**, **empty**, **error**, **success**. Take a typical component: the data starts as `null` (loading text shows), a failure sets an error that renders a banner, and success renders the content. Missing empty states are the most common gap. A related hazard is a stale response arriving after you navigated away or changed a filter. The usual pattern is an `AbortController`:

```typescript
useEffect(() => {
  const ctl = new AbortController();
  getJson<Overview>("/api/overview", ctl.signal)
    .then(setD)
    .catch((e) => { if (!ctl.signal.aborted) setErr(String(e)); });
  return () => ctl.abort();
}, [ver]);
```

When the effect re-runs or the component unmounts, the cleanup cancels the request, and the `catch` ignores the abort. `getJson` rethrows `AbortError` untouched for this reason. Note that `putJson` and `deleteJson` do not accept a signal; fine for short writes, but a place to improve.

#### Application entry: lifespan, middleware, CORS

An application's entry file builds the app in a fixed order. The **lifespan** function runs start-up work (opening databases, starting schedulers) before the app serves, and on shutdown stops background work and closes connections. The **timing middleware** wraps every request: it starts a timer, assumes status 500, calls the next handler, and in a `finally` block records method, route and duration. Because it records the route template (`/api/requirements/{rid}`) and not the raw path, ten thousand different ids still produce one metric line, and unmatched paths are recorded as "(no route)". The `finally` means even a crash is counted, as a 500.

**CORS** controls which web origins a browser lets call the API. The origins come from configuration (an environment variable, with local development ports as defaults), the methods list includes PATCH, and `Content-Disposition` is exposed so the frontend can read download file names. Credentials are allowed, and browsers refuse the wildcard `*` in that case, which is a good reason to list origins. CORS is enforced by the browser: `curl` ignores it, so it is not a security control for the API itself.

#### Performance: N+1 and pagination

An **N+1** problem is one query for a list, then one more per row. Say 100 rows and an assumed 2 ms per query: that is 101 queries, about 200 ms, against one joined query that might take 5 ms. The fix is a JOIN or a single `WHERE id IN (...)`. **Pagination** keeps responses small: `LIMIT ? OFFSET ?`, with offset = (page − 1) × page size, so page 3 of size 50 starts at offset 100. Cap the limit (1,000 is a common ceiling). A caveat: large offsets still scan the skipped rows, and a list with a stable order key is needed or pages will overlap.

### Practice on your own

1. Write a test fixture that gives every test its own temporary database. Prove isolation: one test inserts a task, another asserts the table is empty.
2. For an endpoint that computes months until a load reaches capacity, write a happy-path test with a value you computed by hand (50, 100, 10% growth gives 7.3) and a failure-path test that expects a 422.
3. Build a task list screen with loading, empty, error and success states. Switch your backend off to see the error state, and clear the table to see the empty state.
4. Add a timing middleware that records route templates. Call one route with ten different ids and confirm you get one metric line.
5. Add 1,000 tasks, fetch them with an N+1 pattern and then with a single query, and time both. Add pagination and check page 3 of size 50 starts at offset 100.

### Exercises

1. Why is `tmp_path` better than a shared test database?
2. A test passes alone and fails when run after another. What is the likely cause and the first thing to check?
3. Write a failure-path test for `GET /api/calc/availability?parts=abc`. The service returns 400 for it.
4. A panel shows a spinner forever when the API is down. Which of the four states is missing and what do you add?
5. Compute the offset for page 4 with page size 25.
6. The timing middleware records `/api/x/17` as a separate metric line for each id. What went wrong?
7. A browser blocks a call from `http://localhost:3005` but `curl` succeeds. Why, and what do you change?
8. Rewrite `getJson` and `postJson` so they share one request helper. List what you would keep identical in behaviour.

### Answers and hints

1. Each test starts clean, so results do not depend on order, and tests cannot damage real data.
2. Shared state: a database, a module-level cache or an open connection. Check whether the fixture closes and recreates it.
3. `assert client.get(url, params={"parts": "abc"}).status_code == 400`, and read the message to check it mentions numbers.
4. The error state. Catch the failure, store a message, render a banner, and stop the spinner.
5. (4 − 1) × 25 = 75.
6. It recorded the raw path instead of the route template. Use the matched route's path, as a well-built middleware does.
7. The origin `http://localhost:3005` is not in the allowed list and browsers enforce CORS; curl does not. Add the origin through configuration, not a wildcard.
8. A single `request(method, path, body?, signal?)` that builds the options, converts network failures to the "Can't reach" error, rethrows AbortError, and calls `toError`. Keep the messages and the error type identical so the UI banners do not change.

### Checkpoint

1. What does the `client` fixture set up and tear down?
2. Why compute the expected value by hand?
3. Name the four UI states.
4. What does the `finally` in the timing middleware guarantee?
5. Why record route templates rather than raw paths?
6. What is CORS enforced by, and what is it not?
7. What is an N+1 query, and what are two fixes?
8. How do you calculate an offset from a page number?

Common mistakes:

- Tests that share state and pass or fail by order.
- Expected values copied from the code's own output.
- No empty state, or an error that leaves a spinner running.
- Using `*` in CORS and treating CORS as access control.
- Loading every row to the browser rather than paginating.
- Reading a test count as quality without looking at what the tests assert.

## Level 4: Expert and professional judgement

### What you will be able to do

- You can explain a design trade-off in a small app (no login, an embedded database, generated code) and say when it stops being acceptable.
- You can tell a backward-compatible API change from a breaking one.
- You can design a write path that survives retries, partial failure and bad bulk input.
- You can review another developer's change with a checklist and write useful comments.
- You can write and run a release checklist.
- You can describe what changes when a team, not one person, owns the system.

### Core ideas

#### Trade-offs you can defend

Every choice has a reason and an edge. Take a small personal app with **no authentication**: that can be deliberate for a single user on one machine. The moment it is reachable beyond localhost, revisit it: put it behind a login or a private network first. An **embedded analytical database** such as DuckDB is excellent for queries and needs zero setup, but it is built around one application process holding it for writing, so many concurrent writers are not what it is for. Keeping practice and real data in separate database files is simple and safe, at the cost of no cross-queries. **Generated code** saves typing and teaches structure, but code you did not read is code you do not own.

A defensible trade-off names its alternative, its cost, and the trigger that would make you change it. "No login, because one user on localhost; revisit before any network exposure" is defensible. "No login" alone is an omission.

#### Contracts and compatibility

The API's schema is a contract with the frontend, with any script that calls it, and with your future self. A change is **backward compatible** if old clients keep working. Adding an optional response field or a new endpoint is safe. Renaming `status` to `state`, changing a number to a string, or making an optional parameter required is breaking. When you must break, prefer adding the new name beside the old, migrating callers, then removing the old one. With a single frontend in the same repository you can change both in one commit; with more consumers you cannot. Compare the OpenAPI output before and after a change.

Be honest about what the contract does not check. The frontend's types are promises, not checks (Level 2), so a contract test that calls the endpoint and asserts the field names is what actually keeps the two sides in step.

#### Writes that fail safely

Think about what happens when a write is interrupted, repeated or too big. A client times out and retries a POST; the server had already created the row, so now there are two. Fixes: a unique constraint so the second insert fails cleanly, an idempotency key, or an upsert such as `INSERT ... ON CONFLICT DO NOTHING` (check your database version's documentation). PUT and DELETE should be idempotent by design.

Defensive rules show good design. A failed import never leaves half-loaded data; a refresh that would shrink a table to under half its old size is rejected. With 1,000 rows today, a refresh returning 400 is refused and 600 is accepted. The rule will not catch a subtly wrong file of the right size, so it is a guardrail, not a vault. A request-testing tool is also a place for guardrails: blocking writes against real data and refusing paths outside your own API, because a tool that can silently change real data is a hazard.

#### Reviewing someone else's change

Read the description first, then the tests, then the code. Ask in order: Does it do what it says? Is there a failure-path test? Is input validated at the edge, and are values bound in SQL? Are identifiers whitelisted? Is a secret logged or returned? Is there a loading, empty and error state? Does it break the contract? Is it small enough to understand? Comment on behaviour and risk, ask questions rather than dictate, and mark which comments block the merge. If you cannot explain a piece of generated code, it should not merge, whoever (or whatever) wrote it.

#### Operating as a team: releases, observability, honesty

At team scale, habits become systems. Tests run automatically on every change (continuous integration). Reviews are required. Releases follow a written checklist. A sample one: tests green; frontend builds; configuration reviewed (CORS origins listed, `.env` ignored by git, secret names present but values never shown); a backup taken; a health endpoint answering after deploy; metrics showing normal error counts and timings.

Observability means you can answer "what is it doing and is it healthy?" without guessing: a health endpoint, request counts and durations by route, and an audit trail of actions. Ethics at this level is mostly plain honesty: report test results as they are, do not describe a configuration check as a security audit, do not log secrets or personal data, tell users what breaks, and keep a record of what you shipped and why. Passing tests show the checked behaviour works; they do not show the absence of bugs.

### Practice on your own

1. Write a one-page decisions note for your project: what you chose not to build (for example login), the cost, and the trigger that would change it.
2. Pick one endpoint and write one backward-compatible and one breaking change to it. Then plan the staged rename of a field in three steps.
3. Make your create endpoint duplicate-safe: add a unique constraint and decide what the second identical request should return. Test it.
4. Review a public open-source pull request, or a change of your own from a month ago, with the Level 4 checklist. Write five comments, marked blocking or optional.
5. Write a ten-line release checklist and run every step you can: tests, build, health check, a backup you actually restore from.

### Exercises

1. Classify as breaking or compatible: (a) add optional field `notes`, (b) rename `code` to `ref`, (c) make `limit` required, (d) add a new endpoint.
2. Give two ways to stop a retried POST from creating a duplicate.
3. A bulk refresh returns 300 rows where the table had 1,000. What should happen and why?
4. List four items you would check when reviewing a new endpoint that writes to the database.
5. A teammate says "all tests pass, so it is safe to ship." Respond in two sentences.
6. Draft the "trigger" that would make you add a login to this app.
7. The audit log records action names and results. What should it never contain?
8. Plan a staged rename of a response field from `status` to `state` with three steps.

### Answers and hints

1. (a) compatible, (b) breaking, (c) breaking, (d) compatible.
2. A unique constraint or primary key on a natural identifier; an idempotency key the server remembers; an upsert.
3. It should be refused: 300 is under 50% of 1,000, so it looks like a truncated or wrong file. Keep the old data, report why, and let a person decide.
4. Validation of body and parameters; bound parameters for all values; a whitelist for any identifier; a failure-path test; a status code that matches the problem; an audit entry.
5. Passing tests show only that the checked behaviour works. Ask what is not tested, whether the failure paths and configuration were reviewed, and whether a backup exists.
6. Any of: the app is reachable from another machine, a second person will use it, it holds data other people own, or it is deployed to a server.
7. Secrets, API key values, passwords, or personal data beyond what is needed.
8. First return both `status` and `state`; then migrate the frontend and any scripts to `state` and check nothing reads `status`; finally remove `status`.

### Checkpoint

1. Name one trade-off in this project, its cost and its trigger for change.
2. Which API changes are safe, and which break clients?
3. How do you make a retried write safe?
4. Why is the shrink guard a guardrail and not a vault?
5. What is your review order, and what blocks a merge?
6. What belongs on a release checklist?
7. What does observability let you answer?
8. Why is a configuration checklist not a security audit?

Common mistakes:

- Calling a missing feature (such as a login) a design choice without a trigger for change.
- Renaming a field and updating only one side.
- Assuming retries never happen.
- Merging code nobody can explain.
- Shipping with no backup and no health check.
- Treating green tests as proof of safety.

## Capstone projects

### Capstone 1: One vertical slice (small, about 8 hours)

**Brief.** Choose a small table (for example `reading_list`: id, title, status, added_on). Build it through every layer.

**Deliverables.** The table definition; a router with validation and bound SQL, registered with the app; a TypeScript interface; a screen with loading, empty, error and success states; one happy-path and one failure-path test with hand-computed expected values.

**Rubric (0 to 2 each).** Bad input gets a 422 or 400 with a clear message. No value is concatenated into SQL. The screen shows all four states. The failure test fails when the validation is removed. Another person can run it from your notes. A score of 9 or more is solid.

### Capstone 2: Add a field end to end and find the slow endpoint (medium, about 20 hours)

**Brief.** Add a field to an existing feature through every layer, then find and fix the slowest endpoint.

**Deliverables.** The column, API model, TypeScript type, form input and tests for the new field; a table of timings for ten endpoints (from curl, a REST client or the browser); one endpoint improved with before and after timings and a note on what changed.

**Rubric (0 to 2 each).** The change is backward compatible or the break is managed. Tests cover the new field and an invalid value. Timings are repeated, not single readings. The fix addresses the cause (for example an N+1 or missing pagination). Claims are modest about what a few runs show. A score of 9 or more is solid.

### Capstone 3: A release-ready feature with a review (large, about 35 hours)

**Brief.** Deliver a feature with a write path (for example saved filters), reviewed and released with a checklist.

**Deliverables.** The feature across all layers; idempotent or duplicate-safe writes; tests including failure paths and behaviour against an empty database; a written review of your own change against the Level 4 checklist; a release checklist with each step run and its evidence; a short note on trade-offs and their triggers.

**Rubric (0 to 2 each).** Writes survive a retry. Tests cover the failure paths. The self-review finds real issues and fixes them. The release checklist was actually run. Trade-offs are stated with costs and triggers. A score of 9 or more means you can hand it to a team.

## Tools reference

| Tool | What it is for | When you outgrow it |
|---|---|---|
| REST client or curl | Calling an API and reading status and timings | Automated API suites and contract testing |
| Code generators | A first draft of every layer from a table | When rules, permissions or relationships matter: hand-written code |
| FastAPI `/docs` | Generated interactive API documentation | Public API portals with versioned documentation |
| pytest and TestClient | Fast tests of the API without a server | Browser-level end-to-end tests and load tests need other tools |
| Git and GitHub | History, branches, reviews | Large teams adding branch protection and CI pipelines |
| Browser developer tools | Network, console and component inspection | Production monitoring and tracing platforms |

## Glossary

- **API**: the interface another program calls to use this one.
- **Async**: code that does not block while waiting, such as for a network reply.
- **AbortController**: browser object that cancels an in-flight request.
- **Backward compatible**: old clients keep working after the change.
- **CORS**: browser rule about which web origins may call an API.
- **CRUD**: create, read, update, delete.
- **Contract**: the agreed shape of requests and responses.
- **Dependency injection**: giving a function what it needs rather than having it build it.
- **Endpoint**: a method plus a path, such as `GET /api/projects`.
- **Fixture**: reusable test setup, such as the `client`.
- **Idempotent**: doing it twice has the same effect as once.
- **Idempotency key**: a value that lets the server recognise a repeat request.
- **JSON**: text format for objects, arrays, strings, numbers, booleans and null.
- **Lifespan**: code that runs at application start and stop.
- **Middleware**: code that wraps every request, such as timing.
- **N+1 query**: one query for a list plus one per row.
- **OpenAPI**: the machine-readable description of an API.
- **Pagination**: returning a list in pages with a limit and offset.
- **Parameterised query**: SQL with `?` placeholders and values sent separately.
- **Pydantic**: library that validates data against typed models.
- **Router**: a group of endpoints under a shared prefix.
- **Service**: logic code that does the work, separate from HTTP handling.
- **SQL injection**: input treated as SQL because it was glued into the query.
- **Status code**: three-digit result of an HTTP request.
- **Vertical slice**: one thin feature through every layer.
- **Validation**: rejecting bad input at the edge.
- **422**: the status for a request that does not match the declared schema.

## Career notes

**Roles this leads to.** Full stack developer, software engineer, backend or frontend engineer, web developer, API developer, and with experience, technical lead. The same skills support internal-tools and product-engineering roles.

**How to show your skill.** Keep a repository people can run. Include tests, a README with start-up commands, a short decisions note ("why no login, and when I would add one"), and a visible history of small commits. Show a vertical slice and the review you did on it. Explain what you would change at ten times the scale. A working project you can talk through beats a list of frameworks.

**What to learn next.** Authentication and sessions, database migrations, continuous integration, containers (the project has a compose file to study), browser testing, accessibility, and security basics (Part 9). Certifications exist from cloud and vendor programmes; check the current exam objectives before deciding whether any is worth it, since a portfolio usually counts for more.


## Match it in the app

The project's dashboard has a Full Stack Developer track that uses the project itself as a practice ground. Open Tracks, then Full Stack Developer. Its stack is FastAPI, DuckDB, Next.js, React, TypeScript and pytest, so the book's examples map closely. The companion reading is `docs/FULL_STACK_DEVELOPMENT.md`. Use the Practice workspace for anything that writes.

**Level 1 (HTTP and endpoints).** The API map and tester tab lists every endpoint from the running app's own OpenAPI schema, with counts by method. Filter by a group, click **Use** to load an endpoint, and Send. Try `GET /api/pm`, then a bad query value on a calculator under `/api/sysanalyst/calc/` and read the 422. The tester only calls this app's own `/api/` paths and sends writes only while Practice is active. The backend also serves `/docs` on its port.

**Level 2 (validation, SQL, types).** The Scaffold from a table tab generates SQL, Pydantic models, a CRUD router, a TypeScript interface, a React panel and a pytest skeleton from any of your tables, as text only. Read the router for the `?` placeholders and the `COLS` whitelist, and note that it takes `body: dict`. Read `backend/app/routers/sysanalyst.py` beside `services/sysanalysis.py` for the thin-router pattern and its error helper, and `frontend/src/lib/api.ts` for the shared fetch layer and error conversion.

**Level 3 (testing, UI, operations).** Read `backend/tests/conftest.py` for the isolated-database fixture, and `tests/test_sysanalyst.py` for hand-computed expectations. Run `pytest` from the backend folder. The Codebase tab shows test functions, route functions and the test-to-code ratio. `frontend/src/components/panels/SaPanel.tsx` shows the four UI states and the AbortController pattern. `backend/app/main.py` holds the lifespan, timing middleware and CORS; `GET /api/ops` and `/metrics` show the recorded timings.

**Level 4 (judgement).** The Stack and config tab lists facts the running app can see: no authentication (deliberate, single user), CORS origins, whether database external access is off, whether `.env` is git-ignored, AI key names (never values) and the active workspace. The tab says it is not a security audit, and it is not. The source-refresh shrink guard in the app is a worked example of a defensive write rule.

**What the app does not cover.** It has no login, sessions or permissions to study, no database migrations, no continuous integration pipeline in the panel, no browser-level end-to-end tests, and no deployment beyond the compose files. The scaffold never writes files or knows your business rules. The tester cannot call other services. There is no Tests tab: running and reading tests happens in your terminal and editor. The capstones are best built outside the dashboard's own code, in a project of your own.
