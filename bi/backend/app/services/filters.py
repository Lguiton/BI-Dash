"""Shared query filters for analytics endpoints."""
from dataclasses import dataclass
from datetime import date

from fastapi import HTTPException, Query

# Every analytics query uses this FROM clause. LEFT JOIN keeps facts whose
# entity row is missing so totals never silently drop revenue.
FROM_SQL = "FROM fact_operations f LEFT JOIN dim_entities e ON f.entity_id = e.entity_id"


@dataclass(frozen=True)
class Filters:
    date_from: date | None = None
    date_to: date | None = None
    entity_id: str | None = None
    category: str | None = None
    status: str | None = None

    def where(self) -> tuple[str, list]:
        clauses, params = [], []
        if self.date_from:
            clauses.append("f.record_date >= ?")
            params.append(self.date_from)
        if self.date_to:
            clauses.append("f.record_date <= ?")
            params.append(self.date_to)
        if self.entity_id:
            clauses.append("f.entity_id = ?")
            params.append(self.entity_id)
        if self.category:
            clauses.append("e.category = ?")
            params.append(self.category)
        if self.status:
            clauses.append("f.status = ?")
            params.append(self.status)
        return (" WHERE " + " AND ".join(clauses)) if clauses else "", params

    def with_dates(self, date_from: date | None, date_to: date | None) -> "Filters":
        return Filters(date_from, date_to, self.entity_id, self.category, self.status)


def get_filters(
    date_from: date | None = Query(None, description="Inclusive start date (YYYY-MM-DD)"),
    date_to: date | None = Query(None, description="Inclusive end date (YYYY-MM-DD)"),
    entity_id: str | None = Query(None),
    category: str | None = Query(None),
    status: str | None = Query(None),
) -> Filters:
    if date_from and date_to and date_from > date_to:
        raise HTTPException(status_code=422, detail="date_from must be on or before date_to")
    return Filters(date_from, date_to, entity_id or None, category or None, status or None)
