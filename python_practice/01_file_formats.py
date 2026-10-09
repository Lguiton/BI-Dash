"""01 - File formats: CSV, TSV, JSON, XML, XLSX and Parquet.

Maps to your notes on file formats: delimited text (CSV/TSV), Excel Open XML (XLSX), XML, JSON,
plus Parquet (the Apache columnar format used by Spark, Arrow and most modern data stacks).
Run:  python 01_file_formats.py
"""
import pandas as pd

from common import OUT, banner, load_operations

df = load_operations()
cols = ["fact_id", "record_date", "entity_id", "revenue", "operational_cost", "units_processed", "status"]
data = df[cols].copy()   # record_date is a real datetime64 column here

banner("Write the SAME data in six formats")
paths = {
    "csv": OUT / "ops.csv", "tsv": OUT / "ops.tsv", "json": OUT / "ops.json",
    "xml": OUT / "ops.xml", "xlsx": OUT / "ops.xlsx", "parquet": OUT / "ops.parquet",
}
data.to_csv(paths["csv"], index=False)
data.to_csv(paths["tsv"], index=False, sep="\t")           # tab delimiter: safe when text contains commas
data.to_json(paths["json"], orient="records", indent=1)    # list of objects: what most web APIs return
data.to_xml(paths["xml"], index=False, parser="etree")     # self-describing tags
data.to_excel(paths["xlsx"], index=False, sheet_name="ops")  # a workbook: multiple sheets possible
data.to_parquet(paths["parquet"], index=False)             # binary + columnar + compressed + typed

banner("Read each one back and check it is identical")
readers = {
    "csv": lambda p: pd.read_csv(p), "tsv": lambda p: pd.read_csv(p, sep="\t"),
    "json": lambda p: pd.read_json(p, orient="records", convert_dates=False),
    "xml": lambda p: pd.read_xml(p, parser="etree"),
    "xlsx": lambda p: pd.read_excel(p, sheet_name="ops"), "parquet": lambda p: pd.read_parquet(p),
}
print(f"{'format':8} {'kind':18} {'size (KB)':>10} {'rows':>7} {'revenue sum':>14}  record_date comes back as")
kinds = {"csv": "delimited text", "tsv": "delimited text", "json": "text, nested-capable",
         "xml": "text, tagged", "xlsx": "zipped XML", "parquet": "binary, columnar"}
for fmt, path in paths.items():
    back = readers[fmt](path)
    same = abs(back["revenue"].sum() - data["revenue"].sum()) < 0.01 and len(back) == len(data)
    print(f"{fmt:8} {kinds[fmt]:18} {path.stat().st_size / 1024:10.1f} {len(back):7,} {back['revenue'].sum():14,.2f}  "
          f"{back['record_date'].dtype}{'' if same else '  <-- MISMATCH'}")

banner("What to notice")
print("""* Text formats (csv/tsv/json/xml) are human-readable but carry NO types: look at the last column. The date comes
  back as plain text ('str') or even an epoch number (JSON gives 'int64') until you parse it;
  only xlsx and parquet remember it was a date.
* XML repeats every tag on every row, so it is by far the biggest text format. Parquet is the smallest.
* XLSX can hold several sheets and formatting, but is slow to read at scale.
* Parquet stores each COLUMN together, so a query that needs 2 columns reads 2 columns. That is why it
  is the standard for analytics engines (Spark, DuckDB, BigQuery).

YOUR TURN
1. Add a PDF? Not a data format: it presents data, it does not exchange it. Why does that matter for BI?
2. Read ops.parquet with ONLY ['entity_id', 'revenue']:  pd.read_parquet(path, columns=[...])
3. Put a comma inside an entity name and watch what the CSV writer does (quoting). Why do TSVs avoid this?
4. Write ops.json with orient="columns" and compare to orient="records". Which would an API return?""")
