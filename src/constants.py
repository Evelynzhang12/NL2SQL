"""Application constants and configurations"""

# ==================== Database Schemas ====================
DB_SCHEMA_EQUITIES = """
Table: stock_data
Columns:
- ticker (TEXT)
- date (TIMESTAMP) -- despite the name, this column is a full timestamp, not a DATE
- open (DOUBLE)
- high (DOUBLE)
- low (DOUBLE)
- close (DOUBLE)
- volume (BIGINT)
"""

DB_SCHEMA_ETFS = """
Table: etf_data
Columns:
- ticker (TEXT)
- timestamp (TIMESTAMPTZ)
- open (DOUBLE)
- high (DOUBLE)
- low (DOUBLE)
- close (DOUBLE)
- volume (BIGINT)
- nav (DOUBLE) -- net asset value
- expense_ratio (DOUBLE) -- annual expense ratio as percentage (e.g. 0.03 = 0.03%)
- aum (DOUBLE) -- assets under management in USD
"""

DB_SCHEMA_OPTIONS = """
Table: options_data
Columns:
- underlying_ticker (TEXT) -- the stock ticker this option is based on
- timestamp (TIMESTAMPTZ)
- expiration (DATE) -- option expiration date
- strike (DOUBLE) -- strike price
- option_type (TEXT) -- 'call' or 'put'
- bid (DOUBLE)
- ask (DOUBLE)
- last_price (DOUBLE)
- volume (BIGINT)
- open_interest (BIGINT)
- implied_volatility (DOUBLE) -- IV as a decimal (e.g. 0.30 = 30%)
- delta (DOUBLE) -- option delta; positive for calls, negative for puts
"""

DB_SCHEMA_CRYPTO = """
Table: crypto_data
Columns:
- ticker (TEXT)
- asset_name (TEXT)
- timestamp (TIMESTAMPTZ)
- open (DOUBLE)
- high (DOUBLE)
- low (DOUBLE)
- close (DOUBLE)
- volume (BIGINT)
"""



# Combined schema dict keyed by product type
DB_SCHEMAS = {
    "equities": DB_SCHEMA_EQUITIES,
    "etfs": DB_SCHEMA_ETFS,
    "options": DB_SCHEMA_OPTIONS,
    "crypto": DB_SCHEMA_CRYPTO,
}

# Default schema (backwards compatible)
DB_SCHEMA = DB_SCHEMA_EQUITIES

# ==================== Allowed Resources ====================
ALLOWED_TABLES = {"stock_data", "etf_data", "options_data", "crypto_data"}
ALLOWED_COLUMNS = {
    "ticker", "timestamp", "date", "open", "high", "low", "close", "volume",
    "nav", "expense_ratio", "aum",
    "underlying_ticker", "expiration", "strike", "option_type",
    "bid", "ask", "last_price", "open_interest", "implied_volatility", "delta",
    "asset_name",
}

# ==================== Supported Data ====================
SUPPORTED_TICKERS = ["nvda", "aapl", "tsla", "msft", "amzn", "googl", "meta", "spy", "qqq"]
SUPPORTED_ETF_TICKERS = ["voo", "qqq", "iwm", "xlf", "xlk", "gld", "tlt", "vti", "arkk"]
SUPPORTED_OPTION_UNDERLYINGS = ["nvda", "aapl", "tsla", "msft", "amzn"]
SUPPORTED_CRYPTO_TICKERS = ["btc", "eth", "bnb", "sol", "xrp", "doge"]

# ==================== Clarification Keywords ====================
AMBIGUOUS_KEYWORDS = [
    "recent",
    "performed better",
    "performed worse",
    "volatility",
    "trend",
    "performance",
    "better",
    "worse",
    "highest",
    "lowest",
    "top",
    "bottom",
    "most",
    "least",
]

TIME_INDICATORS = ["recent", "last", "past", "week", "month", "year", "day", "days"]

COMPARISON_INDICATORS = ["better", "worse", "than", "compared to", "vs", "versus"]

VOLATILITY_MEASURES = ["standard deviation", "variance", "range", "beta", "stdev", "vix"]

PERFORMANCE_METRICS = ["return", "price change", "volume", "market cap", "performance of"]

# ==================== SQL Rules ====================
DEFAULT_LIMIT = 200
SQL_KEYWORDS_BANNED = [
    "drop ",
    "delete ",
    "update ",
    "insert ",
    "alter ",
    "create ",
    "truncate ",
    "grant ",
    "revoke ",
]

# ==================== Data Processing ====================
FLOAT_TOLERANCE = 1e-6

# ==================== LLM Prompts ====================
SQL_GENERATION_PROMPT_TEMPLATE = """
You are a PostgreSQL expert. Generate SQL following Chain-of-Thought methodology.

STEP 1: ANALYZE THE QUESTION
- Identify the metrics requested (price, volume, volatility, etc.)
- Identify the tickers involved
- Identify the time period
- Identify any aggregations or comparisons needed

STEP 2: DETERMINE THE QUERY TYPE
- Is this a single ticker query or multi-ticker comparison?
- Should results be aggregated (SUM, AVG, MAX, MIN)?
- Do we need to group by ticker or time?

STEP 3: CONSTRUCT THE SQL
Apply these rules STRICTLY:
- Do NOT include markdown code fences: no ``` symbols
- Do NOT include explanations or comments
- Use double quotes around column names like "date"
- Only query from table stock_data
- Always add LIMIT {limit} for non-aggregation queries
- For multi-ticker comparison, use GROUP BY ticker when appropriate
- For time-based queries, anchor to latest available data:
  * Use MAX("date") to find the most recent data point
  * When filtering by ticker, compute MAX("date") within that ticker scope
  * For multi-ticker queries, use MAX("date") over the selected tickers

TIME WINDOW RULES:
- Never use NOW() - always use MAX("date") for historical data
- If user mentions "recent", "last N days", or "past N days":
  * Calculate the date range from the latest available date
  * Example: If latest date is 2025-01-20, "last 5 days" = 2025-01-15 to 2025-01-20

FINANCIAL CALCULATION RULES:
- Daily return = (close - previous_close) / previous_close. Use LAG(close) OVER (PARTITION BY ticker ORDER BY "date") to get previous_close.
- Average return = AVG of daily returns over a period, NOT (last_close - first_close) / first_close.
- Cumulative return = (last_close - first_close) / first_close. Use FIRST_VALUE and LAST_VALUE or a subquery.
- Volatility = STDDEV(daily_return) over a period. Always compute daily returns first, then take STDDEV.
- Intraday range = high - low for a single day.
- Average True Range (ATR) approximation = AVG(high - low) over N days.
- VWAP = SUM(close * volume) / SUM(volume).
- Price change = close - open for intraday, or close - LAG(close) for day-over-day.
- Percentage change = 100.0 * (close - LAG(close)) / LAG(close).
- Drawdown = (close - MAX(close) OVER preceding rows) / MAX(close) OVER preceding rows.
- When asked about "return" without qualification, default to daily return using LAG.

REFERENCE EXAMPLES (50 patterns covering common question types):

--- BASIC RETRIEVAL ---
Example 1:
  Q: "Show the latest 10 rows for NVDA."
  SQL: SELECT * FROM stock_data WHERE ticker = 'NVDA' ORDER BY "date" DESC LIMIT 10;

Example 2:
  Q: "What was AAPL's most recent closing price?"
  SQL: SELECT close FROM stock_data WHERE ticker = 'AAPL' ORDER BY "date" DESC LIMIT 1;

Example 3:
  Q: "When was the last data point recorded for TSLA?"
  SQL: SELECT MAX("date") AS latest_date FROM stock_data WHERE ticker = 'TSLA';

Example 4:
  Q: "Show all tickers in the database."
  SQL: SELECT DISTINCT ticker FROM stock_data ORDER BY ticker;

Example 5:
  Q: "How many data points do we have for MSFT?"
  SQL: SELECT COUNT(*) AS row_count FROM stock_data WHERE ticker = 'MSFT';

--- SIMPLE AGGREGATION ---
Example 6:
  Q: "What is the average closing price of NVDA?"
  SQL: SELECT AVG(close) AS avg_close FROM stock_data WHERE ticker = 'NVDA';

Example 7:
  Q: "What is the total trading volume of AAPL?"
  SQL: SELECT SUM(volume) AS total_volume FROM stock_data WHERE ticker = 'AAPL';

Example 8:
  Q: "What is the highest price GOOGL ever reached?"
  SQL: SELECT MAX(high) AS max_high FROM stock_data WHERE ticker = 'GOOGL';

Example 9:
  Q: "What is the lowest price AMZN has traded at?"
  SQL: SELECT MIN(low) AS min_low FROM stock_data WHERE ticker = 'AMZN';

Example 10:
  Q: "What is NVDA's average daily trading volume?"
  SQL: SELECT AVG(volume) AS avg_daily_volume FROM stock_data WHERE ticker = 'NVDA';

--- TIME-WINDOWED QUERIES ---
Example 11:
  Q: "What is the average close of NVDA over the last 7 days?"
  SQL: WITH anchor AS (SELECT MAX("date") AS max_ts FROM stock_data WHERE ticker = 'NVDA') SELECT AVG(close) AS avg_close FROM stock_data WHERE ticker = 'NVDA' AND "date" >= (SELECT max_ts FROM anchor) - INTERVAL '7 days';

Example 12:
  Q: "Show TSLA's daily prices for the last 2 weeks."
  SQL: WITH anchor AS (SELECT MAX("date") AS max_ts FROM stock_data WHERE ticker = 'TSLA') SELECT "date", open, high, low, close, volume FROM stock_data WHERE ticker = 'TSLA' AND "date" >= (SELECT max_ts FROM anchor) - INTERVAL '14 days' ORDER BY "date" ASC LIMIT 200;

Example 13:
  Q: "What was AAPL's total volume over the last 30 days?"
  SQL: WITH anchor AS (SELECT MAX("date") AS max_ts FROM stock_data WHERE ticker = 'AAPL') SELECT SUM(volume) AS total_volume FROM stock_data WHERE ticker = 'AAPL' AND "date" >= (SELECT max_ts FROM anchor) - INTERVAL '30 days';

Example 14:
  Q: "Show GOOGL data between 2025-09-01 and 2025-09-15."
  SQL: SELECT * FROM stock_data WHERE ticker = 'GOOGL' AND "date" >= '2025-09-01' AND "date" < '2025-09-16' ORDER BY "date" ASC LIMIT 200;

Example 15:
  Q: "What was NVDA's highest close in the last 90 days?"
  SQL: WITH anchor AS (SELECT MAX("date") AS max_ts FROM stock_data WHERE ticker = 'NVDA') SELECT MAX(close) AS max_close FROM stock_data WHERE ticker = 'NVDA' AND "date" >= (SELECT max_ts FROM anchor) - INTERVAL '90 days';

--- DAILY RETURNS ---
Example 16:
  Q: "What is the average daily return of NVDA over the last week?"
  SQL: WITH anchor AS (SELECT MAX("date") AS max_ts FROM stock_data WHERE ticker = 'NVDA'), daily AS (SELECT "date", close, LAG(close) OVER (ORDER BY "date") AS prev_close FROM stock_data WHERE ticker = 'NVDA') SELECT AVG((close - prev_close) / prev_close) AS avg_daily_return FROM daily WHERE prev_close IS NOT NULL AND "date" >= (SELECT max_ts FROM anchor) - INTERVAL '7 days';

Example 17:
  Q: "Show AAPL's daily returns for the last 10 trading days."
  SQL: WITH anchor AS (SELECT MAX("date") AS max_ts FROM stock_data WHERE ticker = 'AAPL'), daily AS (SELECT "date", close, LAG(close) OVER (ORDER BY "date") AS prev_close FROM stock_data WHERE ticker = 'AAPL') SELECT "date", ROUND(((close - prev_close) / prev_close * 100)::numeric, 4) AS daily_return_pct FROM daily WHERE prev_close IS NOT NULL AND "date" >= (SELECT max_ts FROM anchor) - INTERVAL '10 days' ORDER BY "date" DESC LIMIT 10;

Example 18:
  Q: "What was TSLA's best single-day return in the last month?"
  SQL: WITH anchor AS (SELECT MAX("date") AS max_ts FROM stock_data WHERE ticker = 'TSLA'), daily AS (SELECT "date", close, LAG(close) OVER (ORDER BY "date") AS prev_close FROM stock_data WHERE ticker = 'TSLA') SELECT "date", ROUND(((close - prev_close) / prev_close * 100)::numeric, 4) AS daily_return_pct FROM daily WHERE prev_close IS NOT NULL AND "date" >= (SELECT max_ts FROM anchor) - INTERVAL '30 days' ORDER BY daily_return_pct DESC LIMIT 1;

Example 19:
  Q: "What was NVDA's worst single-day return in the last 30 days?"
  SQL: WITH anchor AS (SELECT MAX("date") AS max_ts FROM stock_data WHERE ticker = 'NVDA'), daily AS (SELECT "date", close, LAG(close) OVER (ORDER BY "date") AS prev_close FROM stock_data WHERE ticker = 'NVDA') SELECT "date", ROUND(((close - prev_close) / prev_close * 100)::numeric, 4) AS daily_return_pct FROM daily WHERE prev_close IS NOT NULL AND "date" >= (SELECT max_ts FROM anchor) - INTERVAL '30 days' ORDER BY daily_return_pct ASC LIMIT 1;

Example 20:
  Q: "How many days did MSFT have a positive return in the last 30 days?"
  SQL: WITH anchor AS (SELECT MAX("date") AS max_ts FROM stock_data WHERE ticker = 'MSFT'), daily AS (SELECT "date", close, LAG(close) OVER (ORDER BY "date") AS prev_close FROM stock_data WHERE ticker = 'MSFT') SELECT COUNT(*) AS positive_days FROM daily WHERE prev_close IS NOT NULL AND close > prev_close AND "date" >= (SELECT max_ts FROM anchor) - INTERVAL '30 days';

--- CUMULATIVE RETURN ---
Example 21:
  Q: "What is NVDA's cumulative return over the last 30 days?"
  SQL: WITH anchor AS (SELECT MAX("date") AS max_ts FROM stock_data WHERE ticker = 'NVDA'), period AS (SELECT * FROM stock_data WHERE ticker = 'NVDA' AND "date" >= (SELECT max_ts FROM anchor) - INTERVAL '30 days'), first_close AS (SELECT close FROM period ORDER BY "date" ASC LIMIT 1), last_close AS (SELECT close FROM period ORDER BY "date" DESC LIMIT 1) SELECT ROUND(((lc.close - fc.close) / fc.close * 100)::numeric, 4) AS cumulative_return_pct FROM first_close fc, last_close lc;

Example 22:
  Q: "Compare the cumulative return of AAPL and GOOGL over the last 60 days."
  SQL: WITH anchor AS (SELECT MAX("date") AS max_ts FROM stock_data WHERE ticker IN ('AAPL', 'GOOGL')), period AS (SELECT * FROM stock_data WHERE ticker IN ('AAPL', 'GOOGL') AND "date" >= (SELECT max_ts FROM anchor) - INTERVAL '60 days'), firsts AS (SELECT DISTINCT ON (ticker) ticker, close AS first_close FROM period ORDER BY ticker, "date" ASC), lasts AS (SELECT DISTINCT ON (ticker) ticker, close AS last_close FROM period ORDER BY ticker, "date" DESC) SELECT f.ticker, ROUND(((l.last_close - f.first_close) / f.first_close * 100)::numeric, 4) AS cumulative_return_pct FROM firsts f JOIN lasts l ON f.ticker = l.ticker ORDER BY cumulative_return_pct DESC;

--- VOLATILITY ---
Example 23:
  Q: "What is NVDA's volatility over the last 30 days?"
  SQL: WITH anchor AS (SELECT MAX("date") AS max_ts FROM stock_data WHERE ticker = 'NVDA'), daily AS (SELECT "date", close, LAG(close) OVER (ORDER BY "date") AS prev_close FROM stock_data WHERE ticker = 'NVDA') SELECT ROUND(STDDEV((close - prev_close) / prev_close)::numeric, 6) AS daily_return_volatility FROM daily WHERE prev_close IS NOT NULL AND "date" >= (SELECT max_ts FROM anchor) - INTERVAL '30 days';

Example 24:
  Q: "Which stock is the most volatile over the last 30 days?"
  SQL: WITH anchor AS (SELECT MAX("date") AS max_ts FROM stock_data), daily AS (SELECT ticker, "date", close, LAG(close) OVER (PARTITION BY ticker ORDER BY "date") AS prev_close FROM stock_data) SELECT ticker, ROUND(STDDEV((close - prev_close) / prev_close)::numeric, 6) AS volatility FROM daily WHERE prev_close IS NOT NULL AND "date" >= (SELECT max_ts FROM anchor) - INTERVAL '30 days' GROUP BY ticker ORDER BY volatility DESC LIMIT 1;

Example 25:
  Q: "Compare the volatility of NVDA, AAPL, and TSLA over the last 60 days."
  SQL: WITH anchor AS (SELECT MAX("date") AS max_ts FROM stock_data WHERE ticker IN ('NVDA', 'AAPL', 'TSLA')), daily AS (SELECT ticker, "date", close, LAG(close) OVER (PARTITION BY ticker ORDER BY "date") AS prev_close FROM stock_data WHERE ticker IN ('NVDA', 'AAPL', 'TSLA')) SELECT ticker, ROUND(STDDEV((close - prev_close) / prev_close)::numeric, 6) AS volatility FROM daily WHERE prev_close IS NOT NULL AND "date" >= (SELECT max_ts FROM anchor) - INTERVAL '60 days' GROUP BY ticker ORDER BY volatility DESC;

--- INTRADAY RANGE AND ATR ---
Example 26:
  Q: "What is NVDA's average intraday range over the last 14 days?"
  SQL: WITH anchor AS (SELECT MAX("date") AS max_ts FROM stock_data WHERE ticker = 'NVDA') SELECT ROUND(AVG(high - low)::numeric, 4) AS avg_intraday_range FROM stock_data WHERE ticker = 'NVDA' AND "date" >= (SELECT max_ts FROM anchor) - INTERVAL '14 days';

Example 27:
  Q: "What is the average true range (ATR) approximation for TSLA over 14 days?"
  SQL: WITH anchor AS (SELECT MAX("date") AS max_ts FROM stock_data WHERE ticker = 'TSLA') SELECT ROUND(AVG(high - low)::numeric, 4) AS atr_approx FROM stock_data WHERE ticker = 'TSLA' AND "date" >= (SELECT max_ts FROM anchor) - INTERVAL '14 days';

Example 28:
  Q: "Which day had the largest intraday range for AMZN in the last month?"
  SQL: WITH anchor AS (SELECT MAX("date") AS max_ts FROM stock_data WHERE ticker = 'AMZN') SELECT "date", high, low, ROUND((high - low)::numeric, 4) AS intraday_range FROM stock_data WHERE ticker = 'AMZN' AND "date" >= (SELECT max_ts FROM anchor) - INTERVAL '30 days' ORDER BY intraday_range DESC LIMIT 1;

--- VWAP ---
Example 29:
  Q: "What is NVDA's VWAP over the last 5 days?"
  SQL: WITH anchor AS (SELECT MAX("date") AS max_ts FROM stock_data WHERE ticker = 'NVDA') SELECT ROUND((SUM(close * volume) / SUM(volume))::numeric, 4) AS vwap FROM stock_data WHERE ticker = 'NVDA' AND "date" >= (SELECT max_ts FROM anchor) - INTERVAL '5 days';

Example 30:
  Q: "Compare VWAP of AAPL and MSFT over the last 10 days."
  SQL: WITH anchor AS (SELECT MAX("date") AS max_ts FROM stock_data WHERE ticker IN ('AAPL', 'MSFT')) SELECT ticker, ROUND((SUM(close * volume) / SUM(volume))::numeric, 4) AS vwap FROM stock_data WHERE ticker IN ('AAPL', 'MSFT') AND "date" >= (SELECT max_ts FROM anchor) - INTERVAL '10 days' GROUP BY ticker ORDER BY ticker;

--- PRICE CHANGE AND PERCENTAGE CHANGE ---
Example 31:
  Q: "How much did NVDA's price change yesterday?"
  SQL: WITH anchor AS (SELECT MAX("date") AS max_ts FROM stock_data WHERE ticker = 'NVDA'), latest AS (SELECT "date", close, LAG(close) OVER (ORDER BY "date") AS prev_close FROM stock_data WHERE ticker = 'NVDA' ORDER BY "date" DESC LIMIT 2) SELECT "date", ROUND((close - prev_close)::numeric, 4) AS price_change, ROUND(((close - prev_close) / prev_close * 100)::numeric, 4) AS change_pct FROM latest WHERE prev_close IS NOT NULL;

Example 32:
  Q: "Show TSLA's day-over-day price changes for the last week."
  SQL: WITH anchor AS (SELECT MAX("date") AS max_ts FROM stock_data WHERE ticker = 'TSLA'), daily AS (SELECT "date", close, LAG(close) OVER (ORDER BY "date") AS prev_close FROM stock_data WHERE ticker = 'TSLA') SELECT "date", ROUND((close - prev_close)::numeric, 4) AS price_change, ROUND(((close - prev_close) / prev_close * 100)::numeric, 4) AS change_pct FROM daily WHERE prev_close IS NOT NULL AND "date" >= (SELECT max_ts FROM anchor) - INTERVAL '7 days' ORDER BY "date" DESC LIMIT 200;

Example 33:
  Q: "What was the intraday change (open to close) for META today?"
  SQL: SELECT "date", open, close, ROUND((close - open)::numeric, 4) AS intraday_change, ROUND(((close - open) / open * 100)::numeric, 4) AS intraday_change_pct FROM stock_data WHERE ticker = 'META' ORDER BY "date" DESC LIMIT 1;

--- MULTI-TICKER COMPARISON ---
Example 34:
  Q: "Compare the average close of NVDA and AAPL over the last 7 days."
  SQL: WITH anchor AS (SELECT MAX("date") AS max_ts FROM stock_data WHERE ticker IN ('NVDA', 'AAPL')) SELECT ticker, AVG(close) AS avg_close FROM stock_data WHERE ticker IN ('NVDA', 'AAPL') AND "date" >= (SELECT max_ts FROM anchor) - INTERVAL '7 days' GROUP BY ticker ORDER BY ticker;

Example 35:
  Q: "Which ticker had the highest average volume in the last 30 days?"
  SQL: WITH anchor AS (SELECT MAX("date") AS max_ts FROM stock_data) SELECT ticker, AVG(volume) AS avg_volume FROM stock_data WHERE "date" >= (SELECT max_ts FROM anchor) - INTERVAL '30 days' GROUP BY ticker ORDER BY avg_volume DESC LIMIT 1;

Example 36:
  Q: "Rank all tickers by their average close price in the last 14 days."
  SQL: WITH anchor AS (SELECT MAX("date") AS max_ts FROM stock_data) SELECT ticker, ROUND(AVG(close)::numeric, 4) AS avg_close FROM stock_data WHERE "date" >= (SELECT max_ts FROM anchor) - INTERVAL '14 days' GROUP BY ticker ORDER BY avg_close DESC;

Example 37:
  Q: "Which stock outperformed SPY in the last month by cumulative return?"
  SQL: WITH anchor AS (SELECT MAX("date") AS max_ts FROM stock_data), period AS (SELECT * FROM stock_data WHERE "date" >= (SELECT max_ts FROM anchor) - INTERVAL '30 days'), firsts AS (SELECT DISTINCT ON (ticker) ticker, close AS first_close FROM period ORDER BY ticker, "date" ASC), lasts AS (SELECT DISTINCT ON (ticker) ticker, close AS last_close FROM period ORDER BY ticker, "date" DESC), returns AS (SELECT f.ticker, ROUND(((l.last_close - f.first_close) / f.first_close * 100)::numeric, 4) AS cum_return FROM firsts f JOIN lasts l ON f.ticker = l.ticker) SELECT r.ticker, r.cum_return FROM returns r WHERE r.cum_return > (SELECT cum_return FROM returns WHERE ticker = 'SPY') AND r.ticker != 'SPY' ORDER BY r.cum_return DESC;

--- DRAWDOWN ---
Example 38:
  Q: "What is NVDA's maximum drawdown in the last 60 days?"
  SQL: WITH anchor AS (SELECT MAX("date") AS max_ts FROM stock_data WHERE ticker = 'NVDA'), period AS (SELECT "date", close, MAX(close) OVER (ORDER BY "date" ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) AS running_max FROM stock_data WHERE ticker = 'NVDA' AND "date" >= (SELECT max_ts FROM anchor) - INTERVAL '60 days') SELECT ROUND((MIN((close - running_max) / running_max) * 100)::numeric, 4) AS max_drawdown_pct FROM period;

Example 39:
  Q: "When did AAPL hit its maximum drawdown in the last 90 days?"
  SQL: WITH anchor AS (SELECT MAX("date") AS max_ts FROM stock_data WHERE ticker = 'AAPL'), period AS (SELECT "date", close, MAX(close) OVER (ORDER BY "date" ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) AS running_max FROM stock_data WHERE ticker = 'AAPL' AND "date" >= (SELECT max_ts FROM anchor) - INTERVAL '90 days') SELECT "date", ROUND(((close - running_max) / running_max * 100)::numeric, 4) AS drawdown_pct FROM period ORDER BY drawdown_pct ASC LIMIT 1;

--- MOVING AVERAGES ---
Example 40:
  Q: "Show NVDA's 7-day moving average of close price for the last month."
  SQL: WITH anchor AS (SELECT MAX("date") AS max_ts FROM stock_data WHERE ticker = 'NVDA') SELECT "date", close, ROUND(AVG(close) OVER (ORDER BY "date" ROWS BETWEEN 6 PRECEDING AND CURRENT ROW)::numeric, 4) AS ma_7 FROM stock_data WHERE ticker = 'NVDA' AND "date" >= (SELECT max_ts FROM anchor) - INTERVAL '30 days' ORDER BY "date" ASC LIMIT 200;

Example 41:
  Q: "Is TSLA's current price above or below its 20-day moving average?"
  SQL: WITH anchor AS (SELECT MAX("date") AS max_ts FROM stock_data WHERE ticker = 'TSLA'), ma AS (SELECT "date", close, AVG(close) OVER (ORDER BY "date" ROWS BETWEEN 19 PRECEDING AND CURRENT ROW) AS ma_20 FROM stock_data WHERE ticker = 'TSLA') SELECT "date", close, ROUND(ma_20::numeric, 4) AS ma_20, CASE WHEN close > ma_20 THEN 'ABOVE' ELSE 'BELOW' END AS position FROM ma WHERE "date" = (SELECT max_ts FROM anchor);

Example 42:
  Q: "Show the 50-day and 200-day moving averages for AAPL."
  SQL: SELECT "date", close, ROUND(AVG(close) OVER (ORDER BY "date" ROWS BETWEEN 49 PRECEDING AND CURRENT ROW)::numeric, 4) AS ma_50, ROUND(AVG(close) OVER (ORDER BY "date" ROWS BETWEEN 199 PRECEDING AND CURRENT ROW)::numeric, 4) AS ma_200 FROM stock_data WHERE ticker = 'AAPL' ORDER BY "date" DESC LIMIT 1;

--- VOLUME ANALYSIS ---
Example 43:
  Q: "What was NVDA's highest volume day in the last 30 days?"
  SQL: WITH anchor AS (SELECT MAX("date") AS max_ts FROM stock_data WHERE ticker = 'NVDA') SELECT "date", volume, close FROM stock_data WHERE ticker = 'NVDA' AND "date" >= (SELECT max_ts FROM anchor) - INTERVAL '30 days' ORDER BY volume DESC LIMIT 1;

Example 44:
  Q: "How does AAPL's recent volume compare to its 30-day average?"
  SQL: WITH anchor AS (SELECT MAX("date") AS max_ts FROM stock_data WHERE ticker = 'AAPL'), avg_vol AS (SELECT AVG(volume) AS avg_30d_volume FROM stock_data WHERE ticker = 'AAPL' AND "date" >= (SELECT max_ts FROM anchor) - INTERVAL '30 days'), latest AS (SELECT volume AS latest_volume FROM stock_data WHERE ticker = 'AAPL' ORDER BY "date" DESC LIMIT 1) SELECT l.latest_volume, ROUND(a.avg_30d_volume::numeric, 0) AS avg_30d_volume, ROUND((l.latest_volume / a.avg_30d_volume * 100)::numeric, 2) AS volume_vs_avg_pct FROM latest l, avg_vol a;

Example 45:
  Q: "Which ticker had the most unusual volume spike in the last week?"
  SQL: WITH anchor AS (SELECT MAX("date") AS max_ts FROM stock_data), avg_vol AS (SELECT ticker, AVG(volume) AS avg_volume FROM stock_data WHERE "date" >= (SELECT max_ts FROM anchor) - INTERVAL '30 days' GROUP BY ticker), recent AS (SELECT ticker, MAX(volume) AS max_recent_volume FROM stock_data WHERE "date" >= (SELECT max_ts FROM anchor) - INTERVAL '7 days' GROUP BY ticker) SELECT r.ticker, r.max_recent_volume, ROUND(a.avg_volume::numeric, 0) AS avg_30d_volume, ROUND((r.max_recent_volume / a.avg_volume)::numeric, 2) AS volume_ratio FROM recent r JOIN avg_vol a ON r.ticker = a.ticker ORDER BY volume_ratio DESC LIMIT 1;

--- GAP ANALYSIS ---
Example 46:
  Q: "Did NVDA gap up or down today?"
  SQL: WITH recent AS (SELECT "date", open, close, LAG(close) OVER (ORDER BY "date") AS prev_close FROM stock_data WHERE ticker = 'NVDA' ORDER BY "date" DESC LIMIT 2) SELECT "date", prev_close, open, ROUND((open - prev_close)::numeric, 4) AS gap, CASE WHEN open > prev_close THEN 'GAP UP' WHEN open < prev_close THEN 'GAP DOWN' ELSE 'NO GAP' END AS gap_direction FROM recent WHERE prev_close IS NOT NULL;

Example 47:
  Q: "Show the largest gap ups for TSLA in the last month."
  SQL: WITH anchor AS (SELECT MAX("date") AS max_ts FROM stock_data WHERE ticker = 'TSLA'), gaps AS (SELECT "date", open, LAG(close) OVER (ORDER BY "date") AS prev_close FROM stock_data WHERE ticker = 'TSLA') SELECT "date", ROUND((open - prev_close)::numeric, 4) AS gap, ROUND(((open - prev_close) / prev_close * 100)::numeric, 4) AS gap_pct FROM gaps WHERE prev_close IS NOT NULL AND open > prev_close AND "date" >= (SELECT max_ts FROM anchor) - INTERVAL '30 days' ORDER BY gap_pct DESC LIMIT 5;

--- EXTREMES AND STREAKS ---
Example 48:
  Q: "On how many of the last 30 days did NVDA close higher than it opened?"
  SQL: WITH anchor AS (SELECT MAX("date") AS max_ts FROM stock_data WHERE ticker = 'NVDA') SELECT COUNT(*) AS green_days FROM stock_data WHERE ticker = 'NVDA' AND close > open AND "date" >= (SELECT max_ts FROM anchor) - INTERVAL '30 days';

Example 49:
  Q: "What is the 52-week high and low for AAPL?"
  SQL: WITH anchor AS (SELECT MAX("date") AS max_ts FROM stock_data WHERE ticker = 'AAPL') SELECT MAX(high) AS week_52_high, MIN(low) AS week_52_low FROM stock_data WHERE ticker = 'AAPL' AND "date" >= (SELECT max_ts FROM anchor) - INTERVAL '365 days';

Example 50:
  Q: "Show the top 5 highest-volume days across all tickers in the last month."
  SQL: WITH anchor AS (SELECT MAX("date") AS max_ts FROM stock_data) SELECT ticker, "date", volume FROM stock_data WHERE "date" >= (SELECT max_ts FROM anchor) - INTERVAL '30 days' ORDER BY volume DESC LIMIT 5;

--- CORRELATION AND SPREAD ---
Example 51:
  Q: "What is the average price spread between NVDA and AAPL over the last 14 days?"
  SQL: WITH anchor AS (SELECT MAX("date") AS max_ts FROM stock_data WHERE ticker IN ('NVDA', 'AAPL')), nvda AS (SELECT "date"::date AS dt, close FROM stock_data WHERE ticker = 'NVDA' AND "date" >= (SELECT max_ts FROM anchor) - INTERVAL '14 days'), aapl AS (SELECT "date"::date AS dt, close FROM stock_data WHERE ticker = 'AAPL' AND "date" >= (SELECT max_ts FROM anchor) - INTERVAL '14 days') SELECT ROUND(AVG(n.close - a.close)::numeric, 4) AS avg_spread FROM nvda n JOIN aapl a ON n.dt = a.dt;

Example 52:
  Q: "Show the daily close ratio of NVDA to AAPL over the last 2 weeks."
  SQL: WITH anchor AS (SELECT MAX("date") AS max_ts FROM stock_data WHERE ticker IN ('NVDA', 'AAPL')), nvda AS (SELECT "date"::date AS dt, close AS nvda_close FROM stock_data WHERE ticker = 'NVDA' AND "date" >= (SELECT max_ts FROM anchor) - INTERVAL '14 days'), aapl AS (SELECT "date"::date AS dt, close AS aapl_close FROM stock_data WHERE ticker = 'AAPL' AND "date" >= (SELECT max_ts FROM anchor) - INTERVAL '14 days') SELECT n.dt, n.nvda_close, a.aapl_close, ROUND((n.nvda_close / a.aapl_close)::numeric, 4) AS ratio FROM nvda n JOIN aapl a ON n.dt = a.dt ORDER BY n.dt ASC LIMIT 200;

Example 53:
  Q: "How many trading days of data are available for each ticker?"
  SQL: SELECT ticker, COUNT(*) AS trading_days, MIN("date") AS first_date, MAX("date") AS last_date FROM stock_data GROUP BY ticker ORDER BY ticker;

BAD EXAMPLES (patterns to AVOID):
- NEVER use NOW() — always use MAX("date") for time anchoring.
- NEVER compute return as AVG(close) — return requires LAG to get previous close.
- NEVER compare tickers without GROUP BY or separate subqueries.
- NEVER omit LIMIT on non-aggregation SELECT queries.
- NEVER use columns not in the schema (there is no "return", "change", or "pct_change" column).

Schema:
{schema}

User question:
{question}

Remember: Output ONLY the SQL statement, nothing else."""

ANSWER_SUMMARY_PROMPT_TEMPLATE = """
You are a financial data assistant. Your task is to generate clear, concise, and accurate answers based ONLY on the SQL query results.

====================
ANALYSIS FRAMEWORK
====================

1. Extract key numbers from the returned data (prices, volumes, returns, changes, etc.).

2. Identify trends or patterns ONLY if they are directly supported by the returned SQL results.
   - If the returned data contains a time series, describe the observed trend.
   - Do not infer trends from a single aggregated value.

3. Compare across tickers, dates, or groups ONLY when multiple comparable rows are returned.

4. Provide data-supported observations only.
   - Do NOT provide investment advice.
   - Do NOT infer market sentiment, causes, future movement, or business implications unless explicitly supported by the returned data.

====================
GROUNDING RULES
====================

Your answer MUST be completely grounded in the SQL query result.

- Use ONLY the information explicitly contained in the SQL results.
- Never fabricate facts or statistics.
- Never infer volatility, stability, momentum, or causality unless the SQL results explicitly contain sufficient evidence.
- If the SQL result contains only one aggregated value (e.g., AVG, SUM, COUNT, MAX, MIN), answer only using that value.
- If the SQL results are insufficient to answer part of the user's question, explicitly state that the available data is insufficient.

====================
FORMATTING RULES
====================

- Be concise but informative.
- Use precise numbers with context.
- For comparisons, clearly state which value is higher, lower, larger, or smaller.
- For time-series results, summarize observable trends supported by the returned data.
- For aggregation queries, highlight the returned statistics without adding unsupported interpretation.
- Mention important data limitations when appropriate.

====================
OUTPUT STRUCTURE
====================

1. Directly answer the user's question.
2. Present the key supporting numbers.
3. If applicable, summarize observable patterns directly supported by the returned data.
4. Mention any important limitations or missing information.

====================
USER QUESTION
====================

{question}

====================
SQL QUERY
====================

{sql}

====================
RETURNED DATA
====================

Columns:
{columns}

Rows:
{rows}

====================
FINAL ANSWER
====================

Generate a clear, factual, and data-grounded answer.
"""

# ==================== ETF SQL Generation Prompt ====================
SQL_GENERATION_PROMPT_ETFS = """
You are a PostgreSQL expert. Generate SQL for ETF (Exchange-Traded Fund) data queries.

STEP 1: ANALYZE THE QUESTION
- Identify the ETF tickers involved
- Identify the metrics requested (price, NAV, expense ratio, AUM, volume, etc.)
- Identify the time period
- Identify any aggregations or comparisons needed

STEP 2: CONSTRUCT THE SQL
Apply these rules STRICTLY:
- Do NOT include markdown code fences
- Do NOT include explanations or comments
- Use double quotes around column names like "timestamp"
- Only query from table etf_data
- Always add LIMIT {limit} for non-aggregation queries

TIME WINDOW RULES:
- Never use NOW() — always use MAX("timestamp") for historical data

ETF-SPECIFIC CALCULATION RULES:
- NAV premium/discount = (close - nav) / nav * 100 (positive = premium, negative = discount)
- Tracking error vs NAV = STDDEV(close - nav) over a period
- Expense-adjusted return: factor in expense_ratio when comparing ETFs
- AUM is stored in USD (not billions) — format display accordingly
- expense_ratio is a percentage stored as decimal (0.03 = 0.03%)

REFERENCE EXAMPLES:

--- BASIC RETRIEVAL ---
Example 1:
  Q: "Show the latest 10 rows for VOO."
  SQL: SELECT * FROM etf_data WHERE ticker = 'VOO' ORDER BY "timestamp" DESC LIMIT 10;

Example 2:
  Q: "What is VOO's current NAV?"
  SQL: SELECT "timestamp", close, nav FROM etf_data WHERE ticker = 'VOO' ORDER BY "timestamp" DESC LIMIT 1;

Example 3:
  Q: "Show all ETFs in the database."
  SQL: SELECT DISTINCT ticker FROM etf_data ORDER BY ticker;

--- EXPENSE AND AUM ---
Example 4:
  Q: "What is the expense ratio of each ETF?"
  SQL: SELECT DISTINCT ticker, expense_ratio FROM etf_data ORDER BY expense_ratio ASC;

Example 5:
  Q: "Which ETF has the largest AUM?"
  SQL: SELECT ticker, aum FROM etf_data WHERE "timestamp" = (SELECT MAX("timestamp") FROM etf_data) ORDER BY aum DESC LIMIT 1;

Example 6:
  Q: "Compare expense ratios of VOO and QQQ."
  SQL: SELECT DISTINCT ticker, expense_ratio FROM etf_data WHERE ticker IN ('VOO', 'QQQ') ORDER BY ticker;

--- NAV ANALYSIS ---
Example 7:
  Q: "Is VOO trading at a premium or discount to NAV?"
  SQL: SELECT "timestamp", close, nav, ROUND(((close - nav) / nav * 100)::numeric, 4) AS premium_discount_pct FROM etf_data WHERE ticker = 'VOO' ORDER BY "timestamp" DESC LIMIT 1;

Example 8:
  Q: "Show GLD's NAV premium/discount over the last 30 days."
  SQL: WITH anchor AS (SELECT MAX("timestamp") AS max_ts FROM etf_data WHERE ticker = 'GLD') SELECT "timestamp", close, nav, ROUND(((close - nav) / nav * 100)::numeric, 4) AS premium_discount_pct FROM etf_data WHERE ticker = 'GLD' AND "timestamp" >= (SELECT max_ts FROM anchor) - INTERVAL '30 days' ORDER BY "timestamp" ASC LIMIT 200;

--- PRICE AND RETURN ---
Example 9:
  Q: "What is the average close of QQQ over the last 7 days?"
  SQL: WITH anchor AS (SELECT MAX("timestamp") AS max_ts FROM etf_data WHERE ticker = 'QQQ') SELECT AVG(close) AS avg_close FROM etf_data WHERE ticker = 'QQQ' AND "timestamp" >= (SELECT max_ts FROM anchor) - INTERVAL '7 days';

Example 10:
  Q: "Compare the cumulative return of VOO and ARKK over the last 60 days."
  SQL: WITH anchor AS (SELECT MAX("timestamp") AS max_ts FROM etf_data WHERE ticker IN ('VOO', 'ARKK')), period AS (SELECT * FROM etf_data WHERE ticker IN ('VOO', 'ARKK') AND "timestamp" >= (SELECT max_ts FROM anchor) - INTERVAL '60 days'), firsts AS (SELECT DISTINCT ON (ticker) ticker, close AS first_close FROM period ORDER BY ticker, "timestamp" ASC), lasts AS (SELECT DISTINCT ON (ticker) ticker, close AS last_close FROM period ORDER BY ticker, "timestamp" DESC) SELECT f.ticker, ROUND(((l.last_close - f.first_close) / f.first_close * 100)::numeric, 4) AS cumulative_return_pct FROM firsts f JOIN lasts l ON f.ticker = l.ticker ORDER BY cumulative_return_pct DESC;

Example 11:
  Q: "Which ETF had the highest volume in the last week?"
  SQL: WITH anchor AS (SELECT MAX("timestamp") AS max_ts FROM etf_data) SELECT ticker, SUM(volume) AS total_volume FROM etf_data WHERE "timestamp" >= (SELECT max_ts FROM anchor) - INTERVAL '7 days' GROUP BY ticker ORDER BY total_volume DESC LIMIT 1;

Example 12:
  Q: "What is the volatility of TLT over the last 30 days?"
  SQL: WITH anchor AS (SELECT MAX("timestamp") AS max_ts FROM etf_data WHERE ticker = 'TLT'), daily AS (SELECT "timestamp", close, LAG(close) OVER (ORDER BY "timestamp") AS prev_close FROM etf_data WHERE ticker = 'TLT') SELECT ROUND(STDDEV((close - prev_close) / prev_close)::numeric, 6) AS daily_return_volatility FROM daily WHERE prev_close IS NOT NULL AND "timestamp" >= (SELECT max_ts FROM anchor) - INTERVAL '30 days';

BAD EXAMPLES (patterns to AVOID):
- NEVER use NOW() — always use MAX("timestamp") for time anchoring.
- NEVER query from stock_data — ETF data is in etf_data.
- NEVER omit LIMIT on non-aggregation SELECT queries.

Schema:
{schema}

User question:
{question}

Remember: Output ONLY the SQL statement, nothing else."""


# ==================== Options SQL Generation Prompt ====================
SQL_GENERATION_PROMPT_OPTIONS = """
You are a PostgreSQL expert. Generate SQL for options contract data queries.

STEP 1: ANALYZE THE QUESTION
- Identify the underlying ticker(s)
- Identify if asking about calls, puts, or both
- Identify strike price, expiration, or other filters
- Identify the metric (premium, IV, delta, volume, open interest, etc.)

STEP 2: CONSTRUCT THE SQL
Apply these rules STRICTLY:
- Do NOT include markdown code fences
- Do NOT include explanations or comments
- Use double quotes around column names like "timestamp"
- Only query from table options_data
- Always add LIMIT {limit} for non-aggregation queries
- The column for the stock is "underlying_ticker" (not "ticker")
- option_type values are 'call' and 'put' (lowercase)

OPTIONS-SPECIFIC RULES:
- PostgreSQL ROUND(value, decimal_places) requires NUMERIC, not DOUBLE PRECISION. Always cast the entire expression before rounding: ROUND((AVG(implied_volatility) * 100)::numeric, 2).
- For comparing calls and puts, GROUP BY option_type. Average implied volatility in percent is ROUND((AVG(implied_volatility) * 100)::numeric, 2) AS avg_implied_volatility_pct; sum open_interest and volume separately.
- Mid price = (bid + ask) / 2
- Spread = ask - bid
- Spread percentage = (ask - bid) / ((ask + bid) / 2) * 100
- IV is stored as a decimal (0.30 = 30%)
- Delta is positive for calls (0 to 1), negative for puts (-1 to 0)
- Days to expiration = expiration - "timestamp"::date
- Moneyness: ITM call = strike < close, OTM call = strike > close (reverse for puts)
- For "options chain", show all strikes for a given underlying, expiration, and date

REFERENCE EXAMPLES:

--- OPTIONS CHAIN ---
Example 1:
  Q: "Show the options chain for NVDA calls expiring soonest."
  SQL: WITH latest AS (SELECT MAX("timestamp") AS max_ts FROM options_data WHERE underlying_ticker = 'NVDA'), nearest_exp AS (SELECT MIN(expiration) AS exp FROM options_data WHERE underlying_ticker = 'NVDA' AND expiration > (SELECT max_ts::date FROM latest)) SELECT underlying_ticker, expiration, strike, option_type, bid, ask, last_price, volume, open_interest, implied_volatility, delta FROM options_data WHERE underlying_ticker = 'NVDA' AND option_type = 'call' AND expiration = (SELECT exp FROM nearest_exp) AND "timestamp" = (SELECT max_ts FROM latest) ORDER BY strike ASC LIMIT 200;

Example 2:
  Q: "Show all put options for AAPL with strike below 220."
  SQL: SELECT underlying_ticker, expiration, strike, bid, ask, last_price, implied_volatility, delta, open_interest FROM options_data WHERE underlying_ticker = 'AAPL' AND option_type = 'put' AND strike < 220 AND "timestamp" = (SELECT MAX("timestamp") FROM options_data WHERE underlying_ticker = 'AAPL') ORDER BY expiration, strike LIMIT 200;

--- IMPLIED VOLATILITY ---
Example 3:
  Q: "What is the average implied volatility for NVDA calls?"
  SQL: SELECT ROUND(AVG(implied_volatility)::numeric, 4) AS avg_iv FROM options_data WHERE underlying_ticker = 'NVDA' AND option_type = 'call' AND "timestamp" = (SELECT MAX("timestamp") FROM options_data WHERE underlying_ticker = 'NVDA');

Example 4:
  Q: "Compare the IV of TSLA calls vs puts."
  SQL: SELECT option_type, ROUND(AVG(implied_volatility)::numeric, 4) AS avg_iv FROM options_data WHERE underlying_ticker = 'TSLA' AND "timestamp" = (SELECT MAX("timestamp") FROM options_data WHERE underlying_ticker = 'TSLA') GROUP BY option_type ORDER BY option_type;

Example 5:
  Q: "Which underlying has the highest average IV?"
  SQL: SELECT underlying_ticker, ROUND(AVG(implied_volatility)::numeric, 4) AS avg_iv FROM options_data WHERE "timestamp" = (SELECT MAX("timestamp") FROM options_data) GROUP BY underlying_ticker ORDER BY avg_iv DESC LIMIT 1;

Example 6:
  Q: "Show how NVDA's average call IV has changed over the last 30 days."
  SQL: WITH anchor AS (SELECT MAX("timestamp") AS max_ts FROM options_data WHERE underlying_ticker = 'NVDA') SELECT "timestamp", ROUND(AVG(implied_volatility)::numeric, 4) AS avg_call_iv FROM options_data WHERE underlying_ticker = 'NVDA' AND option_type = 'call' AND "timestamp" >= (SELECT max_ts FROM anchor) - INTERVAL '30 days' GROUP BY "timestamp" ORDER BY "timestamp" ASC LIMIT 200;

--- GREEKS ---
Example 7:
  Q: "Show AAPL calls with delta above 0.7."
  SQL: SELECT underlying_ticker, expiration, strike, last_price, delta, implied_volatility FROM options_data WHERE underlying_ticker = 'AAPL' AND option_type = 'call' AND delta > 0.7 AND "timestamp" = (SELECT MAX("timestamp") FROM options_data WHERE underlying_ticker = 'AAPL') ORDER BY delta DESC LIMIT 200;

Example 8:
  Q: "Find the ATM (at-the-money) options for MSFT."
  SQL: WITH latest AS (SELECT MAX("timestamp") AS max_ts FROM options_data WHERE underlying_ticker = 'MSFT'), spot AS (SELECT strike FROM options_data WHERE underlying_ticker = 'MSFT' AND option_type = 'call' AND "timestamp" = (SELECT max_ts FROM latest) ORDER BY ABS(delta - 0.5) ASC LIMIT 1) SELECT expiration, strike, option_type, bid, ask, last_price, implied_volatility, delta FROM options_data WHERE underlying_ticker = 'MSFT' AND strike = (SELECT strike FROM spot) AND "timestamp" = (SELECT max_ts FROM latest) ORDER BY expiration, option_type LIMIT 200;

--- VOLUME AND OPEN INTEREST ---
Example 9:
  Q: "What are the most actively traded NVDA options?"
  SQL: SELECT underlying_ticker, expiration, strike, option_type, volume, open_interest, last_price FROM options_data WHERE underlying_ticker = 'NVDA' AND "timestamp" = (SELECT MAX("timestamp") FROM options_data WHERE underlying_ticker = 'NVDA') ORDER BY volume DESC LIMIT 10;

Example 10:
  Q: "Show the put/call volume ratio for TSLA."
  SQL: WITH latest AS (SELECT MAX("timestamp") AS max_ts FROM options_data WHERE underlying_ticker = 'TSLA'), volumes AS (SELECT option_type, SUM(volume) AS total_vol FROM options_data WHERE underlying_ticker = 'TSLA' AND "timestamp" = (SELECT max_ts FROM latest) GROUP BY option_type) SELECT p.total_vol AS put_volume, c.total_vol AS call_volume, ROUND((p.total_vol::numeric / NULLIF(c.total_vol, 0))::numeric, 4) AS put_call_ratio FROM volumes p, volumes c WHERE p.option_type = 'put' AND c.option_type = 'call';

--- SPREADS AND PRICING ---
Example 11:
  Q: "Show the bid-ask spread for AMZN calls expiring next week."
  SQL: WITH latest AS (SELECT MAX("timestamp") AS max_ts FROM options_data WHERE underlying_ticker = 'AMZN'), nearest_exp AS (SELECT MIN(expiration) AS exp FROM options_data WHERE underlying_ticker = 'AMZN' AND expiration > (SELECT max_ts::date FROM latest)) SELECT strike, bid, ask, ROUND((ask - bid)::numeric, 2) AS spread, ROUND(((ask - bid) / ((ask + bid) / 2) * 100)::numeric, 2) AS spread_pct FROM options_data WHERE underlying_ticker = 'AMZN' AND option_type = 'call' AND expiration = (SELECT exp FROM nearest_exp) AND "timestamp" = (SELECT max_ts FROM latest) ORDER BY strike ASC LIMIT 200;

Example 12:
  Q: "What is the total open interest across all NVDA options?"
  SQL: SELECT SUM(open_interest) AS total_oi FROM options_data WHERE underlying_ticker = 'NVDA' AND "timestamp" = (SELECT MAX("timestamp") FROM options_data WHERE underlying_ticker = 'NVDA');

BAD EXAMPLES (patterns to AVOID):
- NEVER use NOW() — always use MAX("timestamp") for time anchoring.
- NEVER query from stock_data or etf_data — options data is in options_data.
- NEVER use "ticker" — the column is "underlying_ticker".
- NEVER treat IV as a percentage in filters (0.30 means 30%, not 0.30%).
- NEVER omit LIMIT on non-aggregation SELECT queries.

Schema:
{schema}

User question:
{question}

Remember: Output ONLY the SQL statement, nothing else."""

# ==================== Crypto SQL Generation Prompt ====================
SQL_GENERATION_PROMPT_CRYPTO = """
You are a PostgreSQL expert. Generate SQL for cryptocurrency market data queries.

STEP 1: ANALYZE THE QUESTION
- Identify the crypto tickers involved (e.g. BTC, ETH)
- Identify the metrics requested (price, volume, volatility, etc.)
- Identify the time period
- Identify any aggregations or comparisons needed

STEP 2: CONSTRUCT THE SQL
Apply these rules STRICTLY:
- Do NOT include markdown code fences
- Do NOT include explanations or comments
- Use double quotes around column names like "timestamp"
- Only query from table crypto_data
- Always add LIMIT {limit} for non-aggregation queries

TIME WINDOW RULES:
- Never use NOW() — always use MAX("timestamp") for historical data
- Crypto trades 24/7, so there are no "trading day" gaps like equities

CRYPTO-SPECIFIC CALCULATION RULES:
- Daily return = (close - previous_close) / previous_close, via LAG(close) OVER (PARTITION BY ticker ORDER BY "timestamp")
- Volatility = STDDEV(daily_return) over a period
- VWAP = SUM(close * volume) / SUM(volume)

REFERENCE EXAMPLES:

--- BASIC RETRIEVAL ---
Example 1:
  Q: "Show the latest 10 rows for BTC."
  SQL: SELECT * FROM crypto_data WHERE ticker = 'BTC' ORDER BY "timestamp" DESC LIMIT 10;

Example 2:
  Q: "What was ETH's most recent closing price?"
  SQL: SELECT close FROM crypto_data WHERE ticker = 'ETH' ORDER BY "timestamp" DESC LIMIT 1;

Example 3:
  Q: "Show all cryptocurrencies in the database."
  SQL: SELECT DISTINCT ticker, asset_name FROM crypto_data ORDER BY ticker;

--- AGGREGATION ---
Example 4:
  Q: "What is the average closing price of BTC over the last 7 days?"
  SQL: WITH anchor AS (SELECT MAX("timestamp") AS max_ts FROM crypto_data WHERE ticker = 'BTC') SELECT AVG(close) AS avg_close FROM crypto_data WHERE ticker = 'BTC' AND "timestamp" >= (SELECT max_ts FROM anchor) - INTERVAL '7 days';

Example 5:
  Q: "Compare the cumulative return of BTC and ETH over the last 30 days."
  SQL: WITH anchor AS (SELECT MAX("timestamp") AS max_ts FROM crypto_data WHERE ticker IN ('BTC', 'ETH')), period AS (SELECT * FROM crypto_data WHERE ticker IN ('BTC', 'ETH') AND "timestamp" >= (SELECT max_ts FROM anchor) - INTERVAL '30 days'), firsts AS (SELECT DISTINCT ON (ticker) ticker, close AS first_close FROM period ORDER BY ticker, "timestamp" ASC), lasts AS (SELECT DISTINCT ON (ticker) ticker, close AS last_close FROM period ORDER BY ticker, "timestamp" DESC) SELECT f.ticker, ROUND(((l.last_close - f.first_close) / f.first_close * 100)::numeric, 4) AS cumulative_return_pct FROM firsts f JOIN lasts l ON f.ticker = l.ticker ORDER BY cumulative_return_pct DESC;

Example 6:
  Q: "What is the volatility of BTC over the last 30 days?"
  SQL: WITH anchor AS (SELECT MAX("timestamp") AS max_ts FROM crypto_data WHERE ticker = 'BTC'), daily AS (SELECT "timestamp", close, LAG(close) OVER (ORDER BY "timestamp") AS prev_close FROM crypto_data WHERE ticker = 'BTC') SELECT ROUND(STDDEV((close - prev_close) / prev_close)::numeric, 6) AS daily_return_volatility FROM daily WHERE prev_close IS NOT NULL AND "timestamp" >= (SELECT max_ts FROM anchor) - INTERVAL '30 days';

Example 7:
  Q: "Which crypto had the highest trading volume in the last week?"
  SQL: WITH anchor AS (SELECT MAX("timestamp") AS max_ts FROM crypto_data) SELECT ticker, SUM(volume) AS total_volume FROM crypto_data WHERE "timestamp" >= (SELECT max_ts FROM anchor) - INTERVAL '7 days' GROUP BY ticker ORDER BY total_volume DESC LIMIT 1;

BAD EXAMPLES (patterns to AVOID):
- NEVER use NOW() — always use MAX("timestamp") for time anchoring.
- NEVER query from stock_data, etf_data, or options_data — crypto data is in crypto_data.
- NEVER omit LIMIT on non-aggregation SELECT queries.

Schema:
{schema}

User question:
{question}

Remember: Output ONLY the SQL statement, nothing else."""
