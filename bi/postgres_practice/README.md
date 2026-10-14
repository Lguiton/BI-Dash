# PostgreSQL practice

DuckDB (used by the dashboard) is built for analytics on one machine. **PostgreSQL** is what most companies run in production, so employers ask about it. This lab gives you a real one with the same data.

```bash
cd postgres_practice
docker compose up -d                 # starts PostgreSQL 16 on localhost:5433 (needs Docker Desktop with WSL integration)
pip install "psycopg[binary]"
python load_data.py                  # creates schema bi with keys and constraints, loads 3,650 rows
docker exec -it bi_postgres psql -U postgres -d bi     # then paste queries from exercises.sql
python -m pytest tests -q            # optional: checks the load, an index plan and a read-only role
```

**What to learn here:** primary/foreign keys and CHECK constraints (try `python load_data.py --messy` and read the rejection), `EXPLAIN ANALYZE` and indexes, views vs materialized views, transactions, and least-privilege roles. `exercises.sql` walks through each with what to look for.

**Notes**
- The password in `docker-compose.yml` is for local practice only, and the port is bound to 127.0.0.1.
- No Docker? Install PostgreSQL directly (`sudo apt install postgresql` in WSL), create a database, and set `PG_DSN=postgresql://user:pass@localhost:5432/dbname`.
- The loader, the schema and the test were verified against a real PostgreSQL 16 server. The `docker-compose.yml` itself could not be run in the environment where this lab was built (no Docker there), so if it misbehaves, tell me what you see.
