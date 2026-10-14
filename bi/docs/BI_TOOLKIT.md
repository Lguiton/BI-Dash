# BI toolkit (Data Analyst and Data Scientist tracks)

Track page > **BI toolkit** (below the track panels). Built from the infographic set on DAX, forecasting, Power BI workflow, distributions, management decision support and OCR. Practice tools with the working shown; nothing leaves your machine.

| Part | What it does | Limit |
|---|---|---|
| DAX lab | Runs measures against a built-in 360-row Sales table or your pasted CSV (table `Data`). SUM, AVERAGE, MIN, MAX, COUNT, COUNTROWS, DISTINCTCOUNT, DIVIDE, CALCULATE with `=`, `<`, `>`, `IN {}`, `YEAR()`/`MONTH()` filters, IF, ROUND, ABS and `[measure]` references, with the SQL equivalent. CALCULATE replaces the group's filter on the same column, as DAX does, and says so. | One table. No relationships, date table, iterators (SUMX), VAR/RETURN or time intelligence; each unsupported function names its SQL way. |
| Forecast methods | Hides the last points and ranks eight methods (naive, average, moving average, exponential smoothing, Holt, linear trend, growth rate, seasonal naive) by MAE, RMSE, MAPE and bias. "Use infographic sample" loads the poster's 20,000 to 38,000 series. | No ARIMA or Prophet. A backtest is not a promise. |
| Variance | Budget vs actual per line, favourable/unfavourable by line kind, profit and margin, flags beyond a threshold. | Says how far, not why. |
| Scenarios | Best, base and worst, break-even units, one-at-a-time sensitivity. | One product, straight-line costs, no price elasticity. |
| Distribution finder | Skew, kurtosis, bimodality, Shapiro-Wilk and KS tests, candidate shapes and what that means for the statistics you use; probability calculator for normal, uniform, exponential, log-normal, binomial and Poisson. | Advice, not proof; look at the histogram too. |
| Document reader | Reads vendor, number, dates, lines, subtotal, tax and total from pasted invoice, receipt or bank-statement text; checks totals, line sums, qty x price, running balances; flags ambiguous dates, OCR digit confusion and duplicates; exports CSV with formula injection neutralised. | No OCR engine and no images: run Tesseract or a cloud OCR, then paste. |

## Not built
Power BI itself, Microsoft Fabric, Copilot in Excel, NotebookLM, AWS analytics services and anything that needs a cloud account or GPU. The ideas are covered in the lessons; the tool map says which parts are partial or not embedded.

## Slips found in the source posters
1. The DAX function box lists "YTD" under time intelligence. There is no function called YTD; use TOTALYTD or DATESYTD.
2. SELECTEDVALUE is grouped with table functions. It returns a single value, not a table.
3. "Calculated table: used for complex logic" is loose. A calculated table is for building a table (a calendar, a helper list).
4. The distributions poster lists "Bimodal" and "Skewed (right)" as distributions. They are shapes; a bimodal sample is usually two groups mixed.
5. "Mean > median > mode" for right skew is a rule of thumb, not a law.
6. Poisson is called right-skewed; that is only true for a small lambda.
7. Exponential and log-normal are drawn almost identically; exponential is highest at zero, log-normal is zero at zero and peaks later.
8. Vendor-page accuracy figures for OCR are measured on the vendor's test set; measure on your own documents.
9. The Statistical Data Analysis poster is an advertisement; no contact details are stored here.

## Subject to your own check
The infographic sales series (20,000 to 38,000) rises by exactly 2,000 each period, so trend methods score zero error. Real data is never that clean.
