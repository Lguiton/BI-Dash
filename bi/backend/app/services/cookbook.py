"""Cookbook: SQL data-cleaning recipes, 50 SQL interview questions, a pandas cleaning cheat sheet and a learning-sites list.

Every recipe and every interview answer is DuckDB SQL that runs against a small built-in sample held in a throw-away in-memory
database, so it can never touch your data. Where the source cheat sheets used MySQL or SQL Server words (IFNULL, STR_TO_DATE,
LOCATE, DATE_FORMAT, STRING_SPLIT) the DuckDB equivalent is given and the difference is noted.
"""
from __future__ import annotations

import duckdb

MAX_ROWS = 50


class CookError(Exception):
    pass


SAMPLE_SQL = """
CREATE TABLE departments AS SELECT * FROM (VALUES (1,'Sales'),(2,'Engineering'),(3,'Support')) t(dept_id, dept_name);
CREATE TABLE employees AS SELECT * FROM (VALUES
 (1,'Asha Rao','Asha','Rao',2,95000,current_date - 400,NULL,'asha@gmail.com'),
 (2,'Ben Cole','Ben','Cole',2,82000,current_date - 20,1,'ben@corp.com'),
 (3,'Cara Diaz','Cara','Diaz',1,82000,current_date - 700,1,'cara@gmail.com'),
 (4,'Dev Patel','Dev','Patel',1,61000,current_date - 10,3,'dev@corp.com'),
 (5,'Eli Zhu','Eli','Zhu',3,48000,current_date - 90,3,'eli@gmail.com'),
 (6,'Fay Ng','Fay','Ng',3,52000,current_date - 5,5,'fay@corp.com'),
 (7,'Gus Wu','Gus','Wu',NULL,NULL,current_date - 1000,1,'gus@corp.com'),
 (8,'Al Zed Yoon-Park','Al','Zed Yoon-Park',2,99000,current_date - 30,1,'al@gmail.com')
) t(emp_id, name, first_name, last_name, dept_id, salary, join_date, manager_id, email);
CREATE TABLE customers AS SELECT * FROM (VALUES (1,'Anna','anna@gmail.com'),(2,'Zoe','zoe@corp.com'),(3,'Alex','alex@gmail.com'),(4,'Maz','maz@corp.com'),(5,'Lee','lee@gmail.com')) t(customer_id, name, email);
CREATE TABLE orders AS SELECT * FROM (VALUES
 (1,1,current_date - 3,120.0,10),(2,1,current_date - 2,80.0,11),(3,2,current_date - 2,450.0,10),(4,3,current_date - 9,60.0,12),
 (5,3,current_date - 8,500.0,10),(6,3,current_date - 1,35.0,13),(7,4,current_date - 40,250.0,11),(8,1,current_date - 0,300.0,12)
) t(order_id, customer_id, order_date, amount, product_id);
CREATE TABLE messy AS SELECT * FROM (VALUES
 (1,'  Ann Lee ','ann@x.com','(555) 123-4567','05-03-2024','Nwe York',52000,'AB-12#'),
 (2,'bob stone','bob@x.com','555.987.6543','2024/03/07','new york',NULL,'CD 34!'),
 (3,'Cy  Ng','cy@x.com','+1 555 222 3333','12-11-2023','NYC',1000000,'E5'),
 (4,'Dee Ray','ann@x.com','5551112222','01-01-2024',NULL,48000,'F-6'),
 (5,'Ed Fox','ed@x.com','555-000-9999','30-02-2024','Boston',50500,'G7$'),
 (6,'Flo Day','flo@x.com',NULL,'15-06-2024','boston',51000,'H8'),
 (7,'Gil Ray','gil@x.com','555 444 5555','2024/06/20','Boston',49000,'I9'),
 (8,'Ann Lee','ann@x.com','5551234567','05-03-2024','New York',52000,'AB12')
) t(id, full_name, email, phone, joined, city, salary, code);
CREATE TABLE logins AS SELECT * FROM (VALUES (1,current_date - 5),(1,current_date - 4),(1,current_date - 3),(1,current_date - 1),(2,current_date - 2),(2,current_date)) t(user_id, login_date);
CREATE TABLE seq AS SELECT * FROM (VALUES (1),(2),(3),(5),(6),(9)) t(n);
CREATE TABLE csv_tags AS SELECT * FROM (VALUES (1,'red,green,blue'),(2,'sql,python')) t(id, tags);
CREATE TABLE sales_wide AS SELECT * FROM (VALUES ('Pens',10,20,30),('Ink',5,6,7)) t(product, jan, feb, mar);
CREATE TABLE tbl_a AS SELECT * FROM (VALUES (1),(2),(3),(4)) t(x);
CREATE TABLE tbl_b AS SELECT * FROM (VALUES (3),(4),(5)) t(x);
"""


def _sample() -> duckdb.DuckDBPyConnection:
    con = duckdb.connect(":memory:")
    con.execute(SAMPLE_SQL)
    return con


SAMPLE_TABLES = ["departments", "employees", "customers", "orders", "messy", "logins", "seq", "csv_tags", "sales_wide", "tbl_a", "tbl_b"]

# ---------------------------------------------------------------- 1. cleaning recipes
# id, title, what, source SQL as printed on the cheat sheet, DuckDB preview (a SELECT: nothing is changed), permanent version, destructive?, note
R = lambda *a: dict(zip(("id", "title", "what", "source_sql", "sql", "permanent", "destructive", "note"), a))  # noqa: E731

RECIPES = [
    R("null_default", "Replace NULL with a default value", "Fills missing values while the query runs. The table itself is not changed.",
      "SELECT IFNULL(column_name, 'Default_Value') AS column_name FROM table_name;",
      "SELECT id, COALESCE(city, 'Unknown') AS city FROM messy",
      "CREATE TABLE messy_clean AS SELECT id, COALESCE(city, 'Unknown') AS city FROM messy;", False,
      "DuckDB accepts IFNULL too, but COALESCE is standard SQL and takes more than two arguments (first non-NULL wins)."),
    R("delete_nulls", "Delete rows with NULL values", "Keeps only rows that have a value. Shown here as a SELECT of what would be KEPT.",
      "DELETE FROM table_name WHERE column_name IS NULL;",
      "SELECT * FROM messy WHERE city IS NOT NULL",
      "CREATE TABLE messy_nonnull AS SELECT * FROM messy WHERE city IS NOT NULL;", True,
      "DELETE is permanent. Make a new table (as above) or work in the Practice workspace first. Ask whether the NULL means 'unknown' before dropping: you may be dropping the very rows that matter."),
    R("lower_trim", "Convert text to lower case (and trim)", "Makes 'New York' and ' new york ' compare as equal.",
      "UPDATE table_name SET column_name = LOWER(TRIM(column_name));",
      "SELECT id, lower(trim(city)) AS city FROM messy",
      "UPDATE messy SET city = lower(trim(city));", True,
      "UPDATE overwrites in place. Preview with SELECT first, and keep the original column until you trust the result."),
    R("find_dupes", "Find duplicate values", "Lists every value that appears more than once, with how many times.",
      "SELECT column_name, COUNT(*) AS occurrence_count FROM table_name GROUP BY column_name HAVING COUNT(*) > 1;",
      "SELECT email, COUNT(*) AS occurrence_count FROM messy GROUP BY email HAVING COUNT(*) > 1",
      "", False, "WHERE filters rows before grouping; HAVING filters the groups after. COUNT(*) > 1 is the whole trick."),
    R("dedupe_keep_one", "Remove duplicates, keep one row", "Numbers the rows within each duplicate group and keeps number 1.",
      "(not on the sheet; the interview sheet uses ROW_NUMBER() with DELETE)",
      "SELECT id, full_name, email FROM (SELECT *, row_number() OVER (PARTITION BY email ORDER BY id) AS rn FROM messy) WHERE rn = 1 ORDER BY id",
      "DELETE FROM messy WHERE id IN (SELECT id FROM (SELECT id, row_number() OVER (PARTITION BY email ORDER BY id) rn FROM messy) WHERE rn > 1);", True,
      "Decide which copy to keep (ORDER BY inside OVER). Here the lowest id wins; for 'newest wins' order by a date descending."),
    R("trim_spaces", "Remove leading and trailing spaces", "Spaces you cannot see break joins and GROUP BY.",
      "UPDATE table_name SET column_name = TRIM(column_name);",
      "SELECT id, trim(full_name) AS full_name, length(full_name) AS before_len, length(trim(full_name)) AS after_len FROM messy",
      "UPDATE messy SET full_name = trim(full_name);", True,
      "trim() only touches the ends. Spaces inside a name ('Cy  Ng' has two) need regexp_replace(full_name, ' +', ' ', 'g')."),
    R("split_name", "Split a full name into first and last", "Cuts at the first space.",
      "UPDATE table_name SET first_name = LEFT(full_name, LOCATE(' ', full_name) - 1), last_name = SUBSTRING(full_name, LOCATE(' ', full_name) + 1);",
      "SELECT full_name, split_part(trim(full_name), ' ', 1) AS first_name, trim(substr(trim(full_name), strpos(trim(full_name), ' ') + 1)) AS last_name FROM messy",
      "ALTER TABLE messy ADD COLUMN first_name VARCHAR; ALTER TABLE messy ADD COLUMN last_name VARCHAR; UPDATE messy SET first_name = split_part(trim(full_name), ' ', 1), last_name = trim(substr(trim(full_name), strpos(trim(full_name), ' ') + 1));", True,
      "LOCATE is MySQL; DuckDB uses strpos (or position). The sheet's SET lines are also missing the = sign. A name with no space, or with a middle name, needs a rule: decide it before running."),
    R("std_date", "Standardize date format", "Turns text dates into real dates. try_strptime gives NULL instead of an error on a bad value.",
      "UPDATE table_name SET date_column = STR_TO_DATE(date_column, '%d-%m-%Y');",
      "SELECT id, joined, COALESCE(CAST(try_strptime(joined, '%d-%m-%Y') AS DATE), CAST(try_strptime(joined, '%Y/%m/%d') AS DATE)) AS joined_date FROM messy",
      "CREATE TABLE messy_dates AS SELECT *, COALESCE(CAST(try_strptime(joined, '%d-%m-%Y') AS DATE), CAST(try_strptime(joined, '%Y/%m/%d') AS DATE)) AS joined_date FROM messy;", False,
      "STR_TO_DATE is MySQL; DuckDB uses strptime / try_strptime. Row 5 ('30-02-2024') is not a real date and comes back NULL: that is the check working. Mixed formats are handled by COALESCE over several tries. Never guess day/month order silently: 05-03-2024 is 5 March or 3 May depending on the source."),
    R("special_chars", "Eliminate special characters", "Keeps letters, digits and spaces only.",
      "UPDATE table_name SET column_name = REGEXP_REPLACE(column_name, '[^a-zA-Z0-9 ]', '');",
      "SELECT code, regexp_replace(code, '[^a-zA-Z0-9 ]', '', 'g') AS cleaned FROM messy",
      "UPDATE messy SET code = regexp_replace(code, '[^a-zA-Z0-9 ]', '', 'g');", True,
      "In DuckDB you MUST pass the 'g' flag, otherwise only the FIRST match is removed. MySQL replaces all by default, so the sheet's version silently under-cleans here."),
    R("phone_digits", "Standardize phone number format", "Keeps digits only, so '(555) 123-4567' and '555.123.4567' match.",
      "UPDATE table_name SET phone_number = REGEXP_REPLACE(phone_number, '[^0-9]', '');",
      "SELECT phone, regexp_replace(phone, '[^0-9]', '', 'g') AS digits FROM messy",
      "UPDATE messy SET phone = regexp_replace(phone, '[^0-9]', '', 'g');", True,
      "Same 'g' flag rule. Digits-only drops a leading + (country code): '+1 555 222 3333' becomes 15552223333, 11 digits, not 10. Decide a rule for country codes before comparing."),
    R("outliers_find", "Identify outliers", "Rows outside a lower and an upper limit. Two ways: fixed limits you choose, or the 1.5 x IQR fence.",
      "SELECT * FROM table_name WHERE column_name < lower_threshold OR column_name > upper_threshold;",
      "SELECT id, salary FROM messy, (SELECT quantile_cont(salary, 0.25) AS q1, quantile_cont(salary, 0.75) AS q3 FROM messy) b WHERE salary < q1 - 1.5 * (q3 - q1) OR salary > q3 + 1.5 * (q3 - q1)",
      "", False,
      "Thresholds should come from the business (a salary under 10,000 is impossible) or from a rule like IQR, not from a guess. Look at each flagged row: an outlier can be a real, important event."),
    R("outliers_remove", "Remove outliers", "Shown as a SELECT of the rows that would be KEPT.",
      "DELETE FROM table_name WHERE column_name < lower_threshold OR column_name > upper_threshold;",
      "SELECT id, salary FROM messy WHERE salary IS NULL OR (salary BETWEEN 10000 AND 200000)",
      "CREATE TABLE messy_in_range AS SELECT * FROM messy WHERE salary IS NULL OR salary BETWEEN 10000 AND 200000;", True,
      "Note the IS NULL: without it a comparison with NULL is unknown and those rows would vanish too. In the Data cleaning tab, 'Remove outliers' makes a cleaned COPY and logs it."),
    R("fix_typos", "Fix typos or incorrect values", "Maps known wrong spellings to one correct value.",
      "UPDATE table_name SET column_name = 'Correct_Value' WHERE column_name IN ('Typo_Value', 'Incorrect_Value');",
      "SELECT id, city, CASE WHEN lower(trim(city)) IN ('nwe york', 'nyc', 'new york') THEN 'New York' WHEN lower(trim(city)) = 'boston' THEN 'Boston' ELSE city END AS city_fixed FROM messy",
      "UPDATE messy SET city = 'New York' WHERE lower(trim(city)) IN ('nwe york', 'nyc', 'new york');", True,
      "List the distinct values first (SELECT city, COUNT(*) ... GROUP BY city) and build the map from what is really there. The 'Standardize values' step in the Data cleaning tab does this with a mapping and keeps a log."),
]

# ---------------------------------------------------------------- 2. the 50 interview questions
Q = lambda n, q, concept, sql, note="": dict(n=n, question=q, concept=concept, sql=sql, note=note)  # noqa: E731

INTERVIEW = [
    Q(1, "Find all duplicate rows in a table.", "GROUP BY, HAVING", "SELECT email, COUNT(*) AS copies FROM messy GROUP BY email HAVING COUNT(*) > 1", "Group by every column that defines 'the same row'."),
    Q(2, "Fetch the second highest salary.", "ORDER BY, LIMIT / OFFSET", "SELECT DISTINCT salary FROM employees WHERE salary IS NOT NULL ORDER BY salary DESC LIMIT 1 OFFSET 1", "DISTINCT matters: without it two people on the top salary make the 'second' the same number. SQL Server uses TOP/OFFSET FETCH instead of LIMIT."),
    Q(3, "Fetch the Nth highest salary.", "DENSE_RANK() / ROW_NUMBER()", "SELECT DISTINCT salary FROM (SELECT salary, DENSE_RANK() OVER (ORDER BY salary DESC) AS r FROM employees WHERE salary IS NOT NULL) WHERE r = 3", "Here N = 3. DENSE_RANK has no gaps after ties, so it answers 'Nth distinct'; RANK would skip numbers."),
    Q(4, "Show the running total of sales.", "SUM() OVER()", "SELECT order_id, order_date, amount, SUM(amount) OVER (ORDER BY order_date, order_id) AS running_total FROM orders ORDER BY order_date, order_id", "Add a tie-breaker (order_id) so equal dates have a stable order."),
    Q(5, "Find the moving average of sales (7 days).", "AVG() OVER (ROWS BETWEEN)", "WITH d AS (SELECT order_date, SUM(amount) AS amt FROM orders GROUP BY order_date) SELECT order_date, amt, AVG(amt) OVER (ORDER BY order_date ROWS BETWEEN 6 PRECEDING AND CURRENT ROW) AS avg_7 FROM d ORDER BY order_date", "ROWS counts rows, not days: a missing day shortens the window. For a true 7-day window use RANGE BETWEEN INTERVAL 6 DAY PRECEDING AND CURRENT ROW."),
    Q(6, "Get the previous row value.", "LAG()", "SELECT order_id, order_date, amount, LAG(amount) OVER (ORDER BY order_date, order_id) AS previous_amount FROM orders ORDER BY order_date, order_id", "The first row has no previous: it returns NULL (or give LAG a default as the third argument)."),
    Q(7, "Get the next row value.", "LEAD()", "SELECT order_id, order_date, amount, LEAD(amount) OVER (ORDER BY order_date, order_id) AS next_amount FROM orders ORDER BY order_date, order_id"),
    Q(8, "Get the first order of each customer.", "ROW_NUMBER()", "SELECT * FROM (SELECT *, ROW_NUMBER() OVER (PARTITION BY customer_id ORDER BY order_date, order_id) AS rn FROM orders) WHERE rn = 1 ORDER BY customer_id"),
    Q(9, "Get the last order of each customer.", "ROW_NUMBER()", "SELECT * FROM (SELECT *, ROW_NUMBER() OVER (PARTITION BY customer_id ORDER BY order_date DESC, order_id DESC) AS rn FROM orders) WHERE rn = 1 ORDER BY customer_id"),
    Q(10, "Fetch the top 3 salaries in each department.", "ROW_NUMBER() with PARTITION BY", "SELECT * FROM (SELECT dept_id, name, salary, ROW_NUMBER() OVER (PARTITION BY dept_id ORDER BY salary DESC) AS rn FROM employees WHERE salary IS NOT NULL) WHERE rn <= 3 ORDER BY dept_id, rn", "ROW_NUMBER splits ties arbitrarily; use DENSE_RANK if two people on the same salary must both appear."),
    Q(11, "Count employees in each department.", "GROUP BY, COUNT()", "SELECT d.dept_name, COUNT(e.emp_id) AS employees FROM departments d LEFT JOIN employees e USING (dept_id) GROUP BY d.dept_name ORDER BY d.dept_name", "LEFT JOIN keeps departments with zero people; COUNT(e.emp_id) counts only real matches."),
    Q(12, "Display employees earning more than average.", "Subquery with AVG()", "SELECT name, salary FROM employees WHERE salary > (SELECT AVG(salary) FROM employees) ORDER BY salary DESC"),
    Q(13, "Remove duplicate rows but keep one record.", "ROW_NUMBER() with DELETE", "SELECT id, full_name, email FROM (SELECT *, ROW_NUMBER() OVER (PARTITION BY email ORDER BY id) AS rn FROM messy) WHERE rn = 1 ORDER BY id", "Shown as a SELECT of what survives. The permanent form is DELETE FROM messy WHERE id IN (SELECT id FROM (SELECT id, ROW_NUMBER() OVER (PARTITION BY email ORDER BY id) rn FROM messy) WHERE rn > 1). Back up first."),
    Q(14, "Replace NULL values in salary with 0.", "COALESCE() / IFNULL()", "SELECT name, COALESCE(salary, 0) AS salary FROM employees", "Careful: 0 is a real-looking number. It will pull an average down. Only do this where 0 truly means 'none'."),
    Q(15, "Find employees who joined in the last 30 days.", "WHERE with DATE functions", "SELECT name, join_date FROM employees WHERE join_date >= current_date - INTERVAL 30 DAY ORDER BY join_date"),
    Q(16, "Get total sales per month in the current year.", "GROUP BY, DATE_FORMAT()", "SELECT strftime(order_date, '%Y-%m') AS month, SUM(amount) AS total FROM orders WHERE year(order_date) = year(current_date) GROUP BY 1 ORDER BY 1", "DATE_FORMAT is MySQL; DuckDB uses strftime."),
    Q(17, "Pivot row data into columns (Month vs Sales).", "PIVOT", "PIVOT (SELECT strftime(order_date, '%m') AS m, amount FROM orders) ON m USING SUM(amount)", "DuckDB has a PIVOT statement. Elsewhere, use SUM(CASE WHEN month = 'Jan' THEN amount END) per column."),
    Q(18, "Unpivot columns into rows.", "UNPIVOT / UNION ALL", "UNPIVOT sales_wide ON jan, feb, mar INTO NAME month VALUE sales", "The portable form is one SELECT per column joined with UNION ALL."),
    Q(19, "Find employees not assigned to any department.", "LEFT JOIN / NOT EXISTS", "SELECT e.name FROM employees e LEFT JOIN departments d USING (dept_id) WHERE d.dept_id IS NULL", "NOT EXISTS gives the same answer and is safer than NOT IN when NULLs are about."),
    Q(20, "Find the longest and shortest name.", "LENGTH(), MIN(), MAX()", "SELECT name, length(name) AS len FROM employees WHERE length(name) IN ((SELECT MAX(length(name)) FROM employees), (SELECT MIN(length(name)) FROM employees)) ORDER BY len", "SQL Server spells it LEN()."),
    Q(21, "Concatenate first and last name.", "CONCAT()", "SELECT first_name || ' ' || last_name AS full_name, concat_ws(' ', first_name, last_name) AS same_thing FROM employees", "|| gives NULL if either side is NULL; concat / concat_ws skip NULLs."),
    Q(22, "Extract year, month and day from a date.", "YEAR(), MONTH(), DAY()", "SELECT join_date, year(join_date) AS y, month(join_date) AS m, day(join_date) AS d FROM employees"),
    Q(23, "Find the current date and time.", "CURRENT_DATE, CURRENT_TIME", "SELECT current_date AS today, current_time AS time_now, now() AS timestamp_now", "SQL Server uses GETDATE(); MySQL NOW() and CURDATE()."),
    Q(24, "Find the difference between two dates.", "DATEDIFF()", "SELECT name, date_diff('day', join_date, current_date) AS days_employed FROM employees ORDER BY days_employed DESC", "DuckDB: date_diff(part, start, end). MySQL's DATEDIFF takes (end, start); the argument order is a classic mix-up."),
    Q(25, "Find customers who have never placed an order.", "LEFT JOIN / NOT EXISTS", "SELECT c.name FROM customers c WHERE NOT EXISTS (SELECT 1 FROM orders o WHERE o.customer_id = c.customer_id)", "Customer 5 (Lee) has none."),
    Q(26, "Find common records between two tables.", "INTERSECT", "SELECT x FROM tbl_a INTERSECT SELECT x FROM tbl_b ORDER BY x"),
    Q(27, "Find records present in table A but not in B.", "EXCEPT", "SELECT x FROM tbl_a EXCEPT SELECT x FROM tbl_b ORDER BY x", "Oracle calls it MINUS."),
    Q(28, "Rank customers based on total order amount.", "RANK() / DENSE_RANK()", "SELECT customer_id, SUM(amount) AS total, RANK() OVER (ORDER BY SUM(amount) DESC) AS rnk FROM orders GROUP BY customer_id ORDER BY rnk", "A window function can wrap an aggregate: SUM() is computed first, then ranked."),
    Q(29, "Find the top 5 customers by total sales.", "ORDER BY, LIMIT", "SELECT customer_id, SUM(amount) AS total FROM orders GROUP BY customer_id ORDER BY total DESC LIMIT 5"),
    Q(30, "Find the second most recent record.", "ORDER BY DESC, LIMIT 1 OFFSET 1", "SELECT * FROM orders ORDER BY order_date DESC, order_id DESC LIMIT 1 OFFSET 1"),
    Q(31, "Find customers with more than 1 order.", "GROUP BY, HAVING COUNT(*) > 1", "SELECT customer_id, COUNT(*) AS orders FROM orders GROUP BY customer_id HAVING COUNT(*) > 1 ORDER BY customer_id"),
    Q(32, "Find orders with amount between 100 and 500.", "WHERE amount BETWEEN 100 AND 500", "SELECT * FROM orders WHERE amount BETWEEN 100 AND 500 ORDER BY order_id", "BETWEEN includes both ends."),
    Q(33, "Find customers with name starting with 'A'.", "WHERE name LIKE 'A%'", "SELECT name FROM customers WHERE name LIKE 'A%' ORDER BY name", "LIKE is case-sensitive in DuckDB; use ILIKE to ignore case."),
    Q(34, "Find customers with name ending with 'z'.", "WHERE name LIKE '%z'", "SELECT name FROM customers WHERE name LIKE '%z' ORDER BY name"),
    Q(35, "Find customers who have a gmail email.", "WHERE email LIKE '%@gmail.com'", "SELECT name, email FROM customers WHERE email LIKE '%@gmail.com' ORDER BY name", "The sheet's wording reads 'have email email': read it as a gmail address."),
    Q(36, "Count distinct products.", "COUNT(DISTINCT product_id)", "SELECT COUNT(DISTINCT product_id) AS products FROM orders"),
    Q(37, "Find the cumulative sum of sales.", "SUM() OVER (ORDER BY)", "SELECT order_date, SUM(SUM(amount)) OVER (ORDER BY order_date) AS cumulative FROM orders GROUP BY order_date ORDER BY order_date", "Same idea as #4, but per day."),
    Q(38, "Find the percentage of total sales per product.", "SUM() OVER(), (value / total) * 100", "SELECT product_id, SUM(amount) AS sales, ROUND(SUM(amount) * 100.0 / SUM(SUM(amount)) OVER (), 1) AS pct_of_total FROM orders GROUP BY product_id ORDER BY product_id", "* 100.0 avoids integer division."),
    Q(39, "Find employees whose salary is above their department average.", "JOIN + Subquery with AVG()", "SELECT e.name, e.dept_id, e.salary FROM employees e JOIN (SELECT dept_id, AVG(salary) AS a FROM employees GROUP BY dept_id) d USING (dept_id) WHERE e.salary > d.a ORDER BY e.name"),
    Q(40, "Get the department with the highest average salary.", "GROUP BY, ORDER BY, LIMIT 1", "SELECT dept_id, AVG(salary) AS avg_salary FROM employees WHERE dept_id IS NOT NULL GROUP BY dept_id ORDER BY avg_salary DESC LIMIT 1"),
    Q(41, "Find the employee who earned the max salary.", "ORDER BY salary DESC, LIMIT 1", "SELECT name, salary FROM employees ORDER BY salary DESC NULLS LAST LIMIT 1", "LIMIT 1 hides ties. If two people share the max, use WHERE salary = (SELECT MAX(salary) FROM employees)."),
    Q(42, "Find the employee who joined first.", "ORDER BY join_date ASC, LIMIT 1", "SELECT name, join_date FROM employees ORDER BY join_date ASC LIMIT 1"),
    Q(43, "Find the employee who joined last.", "ORDER BY join_date DESC, LIMIT 1", "SELECT name, join_date FROM employees ORDER BY join_date DESC LIMIT 1"),
    Q(44, "Display hierarchical data (employees and managers).", "Recursive CTE", "WITH RECURSIVE org AS (SELECT emp_id, name, manager_id, 1 AS level, name AS path FROM employees WHERE manager_id IS NULL UNION ALL SELECT e.emp_id, e.name, e.manager_id, o.level + 1, o.path || ' > ' || e.name FROM employees e JOIN org o ON e.manager_id = o.emp_id) SELECT level, path FROM org ORDER BY path", "Anchor member (the top boss) UNION ALL recursive member (people who report to someone already found). Always make sure the data has no loops."),
    Q(45, "Split a comma separated string into rows.", "STRING_SPLIT() / Recursive CTE", "SELECT id, unnest(string_split(tags, ',')) AS tag FROM csv_tags ORDER BY id, tag", "STRING_SPLIT is SQL Server's; DuckDB uses string_split plus unnest."),
    Q(46, "Find the mode (most frequent value).", "GROUP BY, ORDER BY COUNT(*) DESC", "SELECT product_id, COUNT(*) AS n FROM orders GROUP BY product_id ORDER BY n DESC, product_id LIMIT 1", "Ties: LIMIT 1 picks one. Use HAVING COUNT(*) = (max count) to list all modes."),
    Q(47, "Find consecutive login days of users.", "LAG() + date comparison", "SELECT user_id, login_date FROM (SELECT user_id, login_date, login_date - LAG(login_date) OVER (PARTITION BY user_id ORDER BY login_date) AS gap FROM (SELECT DISTINCT user_id, login_date FROM logins)) WHERE gap = 1 ORDER BY user_id, login_date", "For whole streaks, use the 'islands' trick: login_date minus ROW_NUMBER() is constant within a streak; GROUP BY it."),
    Q(48, "Find gaps in a sequence of numbers.", "ROW_NUMBER() + sequence logic", "SELECT n AS gap_after, next_n AS gap_before_next FROM (SELECT n, LEAD(n) OVER (ORDER BY n) AS next_n FROM seq) WHERE next_n - n > 1 ORDER BY n", "Numbers 4, 7 and 8 are missing: the gaps are 3 to 5 and 6 to 9."),
    Q(49, "Check if a string is a palindrome.", "Reverse + Compare", "SELECT word, word = reverse(word) AS is_palindrome FROM (VALUES ('level'), ('radar'), ('sql')) t(word)", "To ignore case and spaces, lower() and replace() first."),
    Q(50, "Explain the performance of a query.", "EXPLAIN / EXPLAIN ANALYZE", "EXPLAIN ANALYZE SELECT customer_id, SUM(amount) FROM orders GROUP BY customer_id", "EXPLAIN shows the plan; EXPLAIN ANALYZE also RUNS the query and reports real timings and row counts. Look for full scans, big joins and where the row count balloons."),
]

# ---------------------------------------------------------------- 3. pandas cleaning cheat sheet
PANDAS = [
    {"section": "Data inspection", "items": [
        ("df.head()", "First rows of the dataframe.", "SELECT * FROM t LIMIT 5"),
        ("df.info()", "Column names, data types and non-null counts.", "DESCRIBE t"),
        ("df.describe()", "Summary statistics of numeric columns.", "SUMMARIZE t")]},
    {"section": "Missing data", "items": [
        ("df.isnull().sum()", "Count of nulls per column.", "SELECT COUNT(*) - COUNT(col) FROM t"),
        ("df.dropna()", "Remove rows with missing values. Use subset=['col'] to look at certain columns only.", "WHERE col IS NOT NULL"),
        ("df.fillna(value)", "Replace missing values. Pass a dict to fill each column differently.", "COALESCE(col, value)")]},
    {"section": "Cleaning and transformation", "items": [
        ("df.drop_duplicates()", "Remove duplicate rows. subset=[...] chooses what counts as the same; keep='first' or 'last'.", "SELECT DISTINCT * ... / ROW_NUMBER() = 1"),
        ("df.rename(columns={'old': 'new'})", "Rename columns by dictionary.", "SELECT old AS new"),
        ("df.astype({'col': 'type'})", "Convert column types. For dates use pd.to_datetime(df['col'], errors='coerce'); for numbers pd.to_numeric(..., errors='coerce').", "CAST / TRY_CAST"),
        ("df.replace(['old'], ['new'])", "Replace values anywhere in the dataframe. Also df['c'].str.replace('x', '', regex=False).", "replace() / CASE WHEN"),
        ("df.reset_index()", "Back to a 0..n numeric index. Add drop=True to not keep the old index as a column. Do this after filtering or dropping rows.", "(SQL tables have no index)"),
        ("df.drop(['col'], axis=1)", "Remove columns. Same as df.drop(columns=['col']), which reads more clearly.", "leave the column out of SELECT")]},
    {"section": "Selection and filtering", "items": [
        ("df.loc['label', 'col']", "Select by labels or by a True/False condition.", "WHERE / SELECT cols"),
        ("df.iloc[]", "Select by integer position.", "LIMIT / OFFSET"),
        ("df[df['col'] > value]", "Filter rows on a condition. Combine with & and |, each condition in its own brackets.", "WHERE col > value")]},
    {"section": "Aggregation and analysis", "items": [
        ("df.groupby('col').agg(['mean'])", "Group and apply an aggregation. Named form: .agg(avg=('x', 'mean')).", "GROUP BY col"),
        ("df.sort_values('col', ascending=False)", "Order by column values.", "ORDER BY col DESC"),
        ("df['col'].value_counts()", "Count of each unique value (a Series method, not a whole-dataframe one).", "GROUP BY col, COUNT(*)"),
        ("df.apply(func)", "Apply a function along rows or columns. Slow on large data: prefer built-in vector methods (df['c'].str.lower()).", "a scalar function"),
        ("df.pivot_table(values, index, columns)", "Pivot table from data; aggfunc='sum' etc.", "PIVOT")]},
    {"section": "Combining and merging", "items": [
        ("pd.concat([df1, df2])", "Stack dataframes (rows). ignore_index=True renumbers.", "UNION ALL"),
        ("pd.merge(df1, df2, on='key')", "Join on a key column. how='left' | 'inner' | 'outer'.", "JOIN ... ON"),
        ("df1.join(df2)", "Join on the index.", "JOIN on the key"),
        ("pd.concat([df1, df2])  # instead of df1.append(df2)", "df.append was REMOVED in pandas 2.0, so the cheat sheet's last line raises an AttributeError on current pandas. Use pd.concat.", "UNION ALL")]},
]

# ---------------------------------------------------------------- 4. learning websites (as printed on the poster)
SITES = [
    {"category": "Search and general information", "sites": [
        ("Google", "www.google.com", "Search anything"), ("Bing", "www.bing.com", "Search with AI"), ("Wikipedia", "www.wikipedia.org", "General knowledge"),
        ("Quora", "www.quora.com", "Ask and learn"), ("Wolfram Alpha", "www.wolframalpha.com", "Compute and learn"), ("Google Books", "books.google.com", "E-books and study material"),
        ("Internet Archive", "archive.org", "Old books, software, web pages"), ("MDN Web Docs", "developer.mozilla.org", "Web development docs"),
        ("Stack Overflow", "stackoverflow.com", "Programming Q&A"), ("Reddit", "www.reddit.com", "Discussions and communities")]},
    {"category": "Microsoft and official resources", "sites": [
        ("Microsoft", "www.microsoft.com", "Official home page"), ("Microsoft Learn", "learn.microsoft.com", "Free learning paths"), ("Office Templates", "templates.office.com", "Free templates"),
        ("Windows Support", "support.microsoft.com", "Help and troubleshooting"), ("Office Support", "support.microsoft.com/office", "Learn Office apps"), ("OneDrive", "www.onedrive.live.com", "Cloud storage (free)"),
        ("Outlook", "outlook.com", "Email and calendar"), ("Excel Help", "support.microsoft.com/excel", "Excel guides"), ("PowerPoint Help", "support.microsoft.com/powerpoint", "Presentation guides"), ("Word Help", "support.microsoft.com/word", "Word guides")]},
    {"category": "Learn computer skills (free)", "sites": [
        ("Google Digital Garage", "learndigital.withgoogle.com", "Free digital skills courses"), ("Microsoft Learn", "learn.microsoft.com", "IT and software skills"), ("Alison", "www.alison.com", "Free online courses"),
        ("Coursera", "www.coursera.org", "Courses from top universities"), ("edX", "www.edx.org", "Free courses (Harvard, MIT etc.)"), ("Udemy (free)", "www.udemy.com", "Free courses (many available)"),
        ("Khan Academy", "www.khanacademy.org", "Computer and IT basics"), ("Great Learning", "www.greatlearning.in", "IT and tech courses"), ("NPTEL", "nptel.ac.in", "Engineering and computer courses (India)"), ("SWAYAM", "swayam.gov.in", "Govt. free online courses (India)")]},
    {"category": "Programming and development", "sites": [
        ("freeCodeCamp", "www.freecodecamp.org", "Learn to code (free)"), ("W3Schools", "www.w3schools.com", "Web development tutorials"), ("GeeksforGeeks", "www.geeksforgeeks.org", "Programming and CS concepts"),
        ("HackerRank", "www.hackerrank.com", "Practice coding"), ("LeetCode", "leetcode.com", "Coding interview practice (the poster prints lectcode.com, which is a typo)"), ("CodeChef", "www.codechef.com", "Competitive programming"),
        ("Replit", "www.replit.com", "Online code editor"), ("GitHub", "www.github.com", "Host and share code"), ("Python.org", "www.python.org", "Official Python resources"), ("Java.com", "www.java.com", "Official Java resources")]},
    {"category": "Tools and utilities", "sites": [
        ("Canva", "www.canva.com", "Design posters, resumes"), ("Smallpdf", "www.smallpdf.com", "PDF tools (merge, convert)"), ("Remove.bg", "www.remove.bg", "Remove image background"),
        ("TinEye", "www.tineye.com", "Reverse image search"), ("Online-Convert", "www.online-convert.com", "Convert files"), ("iLovePDF", "www.ilovepdf.com", "PDF editing tools"),
        ("WallpapersCraft", "wallpaperscraft.com", "Free wallpapers"), ("VirusTotal", "www.virustotal.com", "Check files for viruses and malware"), ("Speedtest", "www.speedtest.net", "Check internet speed"), ("7-Zip", "www.7-zip.org", "Free file compression software")]},
    {"category": "Jobs, careers and practice", "sites": [
        ("Naukri", "www.naukri.com", "Jobs in India"), ("LinkedIn", "www.linkedin.com", "Professional networking"), ("Indeed", "www.indeed.com", "Job search (global)"), ("Glassdoor", "www.glassdoor.com", "Company reviews and jobs"),
        ("Internshala", "www.internshala.com", "Internships and entry-level jobs"), ("Apna", "www.apna.co", "Jobs for freshers (India)"), ("Shine", "www.shine.com", "Jobs in India"), ("Monster India", "www.monsterindia.com", "Career opportunities"),
        ("TimesJobs", "www.timesjobs.com", "IT and non-IT jobs"), ("InterviewBit", "www.interviewbit.com", "Interview preparation")]},
    {"category": "Computer news and updates", "sites": [
        ("TechCrunch", "techcrunch.com", "Tech and startup news"), ("The Verge", "www.theverge.com", "Technology news and reviews"), ("CNET", "www.cnet.com", "Gadgets and tech news"),
        ("ZDNet", "www.zdnet.com", "IT news for professionals"), ("Google News", "news.google.com", "Latest news from trusted sources")]},
    {"category": "Cyber security and safety", "sites": [
        ("Cyber Awareness", "www.cyberaware.gov.in", "Govt. cyber security portal (India)"), ("Stay Safe Online", "www.staysafeonline.in", "Online safety tips"), ("Have I Been Pwned", "haveibeenpwned.com", "Check data breaches"),
        ("Kaspersky", "www.kaspersky.com", "Security news and resources"), ("CERT-In", "www.cert-in.org.in", "Indian cyber security alerts")]},
]
SITES_NOTE = ("Copied from a poster. The app cannot open or check these sites from here, and sites change: confirm the address before you trust or sign in to anything. "
              "Several are for India. Free tiers and course prices change.")


# ---------------------------------------------------------------- running
def _json(v):
    import datetime as dt
    import decimal
    if v is None or isinstance(v, (bool, int, str)):
        return v
    if isinstance(v, float):
        return v if v == v and abs(v) != float("inf") else None
    if isinstance(v, decimal.Decimal):
        return float(v)
    if isinstance(v, (dt.date, dt.datetime, dt.time)):
        return v.isoformat()
    return str(v)


def _run(sql: str) -> dict:
    con = _sample()
    try:
        cur = con.execute(sql)
        cols = [d[0] for d in cur.description]
        rows = cur.fetchmany(MAX_ROWS)
        return {"columns": cols, "rows": [[_json(v) for v in r] for r in rows], "row_count": len(rows)}
    except Exception as e:
        raise CookError(str(e)[:600]) from None
    finally:
        con.close()


def sample_preview(table: str) -> dict:
    if table not in SAMPLE_TABLES:
        raise CookError("Unknown sample table.")
    return _run(f'SELECT * FROM "{table}"')


def run(kind: str, item_id) -> dict:
    if kind == "recipe":
        it = next((r for r in RECIPES if r["id"] == item_id), None)
        if not it:
            raise CookError("Unknown recipe.")
        return {"id": item_id, "sql": it["sql"], "before": sample_preview("messy"), "after": _run(it["sql"])}
    if kind == "interview":
        it = next((r for r in INTERVIEW if str(r["n"]) == str(item_id)), None)
        if not it:
            raise CookError("Unknown question.")
        return {"id": item_id, "sql": it["sql"], "result": _run(it["sql"])}
    raise CookError("kind must be recipe or interview.")


def catalog() -> dict:
    return {
        "recipes": RECIPES, "interview": INTERVIEW, "pandas": [{"section": s["section"], "items": [{"code": c, "what": w, "sql": q} for c, w, q in s["items"]]} for s in PANDAS],
        "sites": [{"category": c["category"], "sites": [{"name": n, "url": u, "what": w} for n, u, w in c["sites"]]} for c in SITES], "sites_note": SITES_NOTE,
        "sample_tables": SAMPLE_TABLES,
        "warning": "UPDATE and DELETE change data for good. Every recipe here runs as a SELECT on a built-in sample so you can see the result first. To apply one to your own data, use the Data cleaning tab (it makes a cleaned COPY and logs each step), or write the result to a new table, and try it in the Practice workspace before Real.",
    }
