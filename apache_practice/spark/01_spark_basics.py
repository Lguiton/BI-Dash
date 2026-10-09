"""Apache Spark practice: the same BI questions you answer in SQL Lab, but on a distributed engine.

Run (from the project root, after `pip install pyspark` and having Java 17+ installed):
    python apache_practice/spark/01_spark_basics.py

Data: downloads the Parquet export from the dashboard API if it is running, otherwise it
converts data_samples/operations_clean.csv. Spark never touches the .duckdb file.

What to notice
  * DataFrame API and Spark SQL are two spellings of the same query plan (compare with .explain()).
  * Weighted margin = SUM(profit) / SUM(revenue): a ratio of sums, never an average of ratios
    (margin is a NON-ADDITIVE measure).
  * Spark is lazy: transformations build a plan, actions (show, count, write) run it.
  * Partitioned Parquet output (partitionBy) is how a data lake lays out a big fact table.
"""
import os
import urllib.request
from pathlib import Path

from pyspark.sql import SparkSession, Window
from pyspark.sql import functions as F

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent / "_out"
OUT.mkdir(exist_ok=True)
API = os.environ.get("BI_API_URL", "http://localhost:8020")


def get_source(spark: SparkSession):
    """Return the flat operations table as a Spark DataFrame."""
    parquet = OUT / "operations.parquet"
    try:
        with urllib.request.urlopen(f"{API}/api/export/operations?format=parquet", timeout=5) as r:
            parquet.write_bytes(r.read())
        print(f"source: Parquet export from {API}")
        return spark.read.parquet(str(parquet))
    except Exception:
        csv = ROOT / "data_samples" / "operations_clean.csv"
        if not csv.exists():
            raise SystemExit("API not running and data_samples/operations_clean.csv is missing. "
                             "Run: python scripts/generate_sample_data.py")
        print(f"source: {csv.name} (API not reachable)")
        df = spark.read.csv(str(csv), header=True, inferSchema=True)
        return (df.withColumn("record_date", F.to_date("record_date"))
                  .withColumn("profit", F.col("revenue") - F.col("operational_cost")))


def main():
    spark = (SparkSession.builder.appName("bi-practice").master("local[*]")
             .config("spark.ui.showConsoleProgress", "false")
             .config("spark.sql.shuffle.partitions", "4")  # tiny data: don't create 200 tiny tasks
             .getOrCreate())
    spark.sparkContext.setLogLevel("ERROR")

    ops = get_source(spark)
    if "profit" not in ops.columns:
        ops = ops.withColumn("profit", F.col("revenue") - F.col("operational_cost"))
    ops.createOrReplaceTempView("ops")
    print(f"\nrows: {ops.count():,}   columns: {len(ops.columns)}")
    ops.printSchema()

    print("\n1) Totals and weighted margin (DataFrame API)")
    (ops.agg(F.sum("revenue").alias("revenue"), F.sum("profit").alias("profit"))
        .withColumn("margin_pct", F.round(F.col("profit") / F.col("revenue") * 100, 2))
        .show())

    print("2) The same question in Spark SQL")
    spark.sql("""
        SELECT ROUND(SUM(revenue), 2) AS revenue,
               ROUND(SUM(profit), 2)  AS profit,
               ROUND(SUM(profit) / SUM(revenue) * 100, 2) AS margin_pct
        FROM ops
    """).show()

    print("3) Revenue and margin by category (non-additive measure done right)")
    (ops.groupBy("category")
        .agg(F.round(F.sum("revenue"), 2).alias("revenue"),
             F.round(F.sum("profit") / F.sum("revenue") * 100, 2).alias("margin_pct"))
        .orderBy(F.desc("revenue")).show())

    print("4) Window function: 7-day moving average of daily revenue")
    daily = ops.groupBy("record_date").agg(F.sum("revenue").alias("revenue"))
    w = Window.orderBy("record_date").rowsBetween(-6, 0)
    (daily.withColumn("revenue_7d_avg", F.round(F.avg("revenue").over(w), 2))
          .orderBy(F.desc("record_date")).limit(5).show())

    print("5) Month-over-month growth with lag()")
    monthly = (ops.withColumn("month", F.date_trunc("month", "record_date").cast("date"))
                  .groupBy("month").agg(F.sum("revenue").alias("revenue")))
    wm = Window.orderBy("month")
    (monthly.withColumn("prev", F.lag("revenue").over(wm))
            .withColumn("mom_pct", F.round((F.col("revenue") / F.col("prev") - 1) * 100, 1))
            .orderBy("month").show(12))

    print("6) Query plan (compare DataFrame vs SQL: they optimize to the same thing)")
    spark.sql("SELECT category, SUM(revenue) FROM ops GROUP BY category").explain()

    print("7) Write a partitioned Parquet table (a mini data lake layout)")
    target = OUT / "operations_by_category"
    (ops.write.mode("overwrite").partitionBy("category").parquet(str(target)))
    print(f"wrote {target}  ->", sorted(p.name for p in target.iterdir() if p.is_dir())[:6])

    spark.stop()


if __name__ == "__main__":
    main()
