-- ============================================================
-- Athena SQL Queries for Customer Review Sentiment Analysis
-- ============================================================
-- Run these in the AWS Athena Console or via AWS CLI.
-- Replace <DATABASE> with your actual Athena database name.
-- ============================================================


-- -------------------------------------------------------
-- STEP 1 – Create the external table
--          (Run once after first sentiment results appear)
-- -------------------------------------------------------
CREATE EXTERNAL TABLE IF NOT EXISTS <DATABASE>.sentiment_results (
  source_key    STRING,
  sentiment     STRING,
  scores        STRUCT<
    positive: DOUBLE,
    negative: DOUBLE,
    neutral:  DOUBLE,
    mixed:    DOUBLE
  >,
  char_count    INT,
  analysed_at   STRING,
  language_code STRING
)
ROW FORMAT SERDE 'org.openx.data.jsonserde.JsonSerDe'
WITH SERDEPROPERTIES (
  'ignore.malformed.json' = 'true'
)
LOCATION 's3://<OUTPUT_BUCKET>/sentiment-results/'
TBLPROPERTIES ('has_encrypted_data' = 'false');


-- -------------------------------------------------------
-- STEP 2 – Verify table
-- -------------------------------------------------------
SELECT * FROM <DATABASE>.sentiment_results LIMIT 10;


-- -------------------------------------------------------
-- ANALYSIS QUERIES
-- -------------------------------------------------------

-- Overall sentiment distribution
SELECT
  sentiment,
  COUNT(*) AS total_reviews,
  ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER (), 2) AS pct
FROM <DATABASE>.sentiment_results
GROUP BY sentiment
ORDER BY total_reviews DESC;


-- Average confidence scores per sentiment label
SELECT
  sentiment,
  ROUND(AVG(scores.positive), 4) AS avg_positive,
  ROUND(AVG(scores.negative), 4) AS avg_negative,
  ROUND(AVG(scores.neutral),  4) AS avg_neutral,
  ROUND(AVG(scores.mixed),    4) AS avg_mixed,
  COUNT(*) AS review_count
FROM <DATABASE>.sentiment_results
GROUP BY sentiment
ORDER BY review_count DESC;


-- Daily review volume and positive rate
SELECT
  DATE(from_iso8601_timestamp(analysed_at)) AS analysis_date,
  COUNT(*) AS total,
  SUM(CASE WHEN sentiment = 'POSITIVE' THEN 1 ELSE 0 END) AS positive_count,
  ROUND(
    SUM(CASE WHEN sentiment = 'POSITIVE' THEN 1 ELSE 0 END) * 100.0 / COUNT(*),
    2
  ) AS positive_pct
FROM <DATABASE>.sentiment_results
GROUP BY DATE(from_iso8601_timestamp(analysed_at))
ORDER BY analysis_date DESC;


-- Top 20 most negative reviews (for manual triage)
SELECT
  source_key,
  sentiment,
  ROUND(scores.negative, 4) AS negative_score,
  analysed_at
FROM <DATABASE>.sentiment_results
WHERE sentiment = 'NEGATIVE'
ORDER BY scores.negative DESC
LIMIT 20;


-- Mixed-sentiment reviews (nuanced feedback worth reading)
SELECT
  source_key,
  ROUND(scores.mixed, 4)    AS mixed_score,
  ROUND(scores.positive, 4) AS positive_score,
  ROUND(scores.negative, 4) AS negative_score,
  analysed_at
FROM <DATABASE>.sentiment_results
WHERE sentiment = 'MIXED'
ORDER BY scores.mixed DESC
LIMIT 20;
