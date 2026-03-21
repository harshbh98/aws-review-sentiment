"""
AWS Lambda function for Customer Review Sentiment Analysis.
Triggered by S3 PUT events, calls Amazon Comprehend, and stores results.
"""

import boto3
import json
import logging
import os
import urllib.parse
from datetime import datetime, timezone

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# AWS clients (initialized outside handler for Lambda reuse)
s3_client = boto3.client("s3")
comprehend_client = boto3.client(
    "comprehend",
    region_name=os.environ.get("AWS_REGION", "us-east-1")
)

# Config from environment variables
OUTPUT_BUCKET = os.environ.get("OUTPUT_BUCKET", "customer-reviews-sentiment")
OUTPUT_PREFIX = os.environ.get("OUTPUT_PREFIX", "sentiment-results/")
LANGUAGE_CODE = os.environ.get("LANGUAGE_CODE", "en")
MAX_TEXT_BYTES = 4900  # Comprehend limit is 5000 bytes; keep buffer


def lambda_handler(event, context):
    """
    Main Lambda handler. Processes S3 event records.

    Args:
        event (dict): S3 event notification
        context: Lambda context object

    Returns:
        dict: Summary of processed records
    """
    logger.info("Received event: %s", json.dumps(event))
    results = []

    for record in event.get("Records", []):
        try:
            result = process_record(record)
            results.append(result)
        except Exception as exc:
            logger.error("Failed to process record %s: %s", record, exc, exc_info=True)
            results.append({"status": "error", "error": str(exc)})

    return {
        "statusCode": 200,
        "processed": len(results),
        "results": results,
    }


def process_record(record):
    """Process a single S3 event record."""
    bucket = record["s3"]["bucket"]["name"]
    key = urllib.parse.unquote_plus(record["s3"]["object"]["key"])

    logger.info("Processing s3://%s/%s", bucket, key)

    # Read review text
    review_text = read_s3_object(bucket, key)
    if not review_text.strip():
        logger.warning("Empty review text for key: %s", key)
        return {"key": key, "status": "skipped", "reason": "empty content"}

    # Truncate if needed
    truncated_text = truncate_text(review_text)

    # Analyse sentiment
    sentiment_response = analyse_sentiment(truncated_text)

    # Build result payload
    payload = build_payload(key, review_text, sentiment_response)

    # Save to output bucket
    output_key = save_result(payload, key)

    logger.info(
        "Saved sentiment result for '%s' → s3://%s/%s | sentiment=%s",
        key, OUTPUT_BUCKET, output_key, payload["sentiment"]
    )

    return {
        "status": "ok",
        "input_key": key,
        "output_key": output_key,
        "sentiment": payload["sentiment"],
    }


def read_s3_object(bucket: str, key: str) -> str:
    """Read and decode an S3 object as UTF-8 text."""
    response = s3_client.get_object(Bucket=bucket, Key=key)
    return response["Body"].read().decode("utf-8", errors="replace")


def truncate_text(text: str) -> str:
    """Truncate text to stay within Comprehend byte limit."""
    encoded = text.encode("utf-8")
    if len(encoded) <= MAX_TEXT_BYTES:
        return text
    logger.warning("Text truncated from %d to %d bytes", len(encoded), MAX_TEXT_BYTES)
    return encoded[:MAX_TEXT_BYTES].decode("utf-8", errors="ignore")


def analyse_sentiment(text: str) -> dict:
    """Call Amazon Comprehend DetectSentiment."""
    response = comprehend_client.detect_sentiment(
        Text=text,
        LanguageCode=LANGUAGE_CODE,
    )
    return response


def build_payload(key: str, original_text: str, comprehend_response: dict) -> dict:
    """Construct the result JSON to be persisted."""
    scores = comprehend_response["SentimentScore"]
    return {
        "source_key": key,
        "sentiment": comprehend_response["Sentiment"],
        "scores": {
            "positive": round(scores["Positive"], 6),
            "negative": round(scores["Negative"], 6),
            "neutral":  round(scores["Neutral"],  6),
            "mixed":    round(scores["Mixed"],    6),
        },
        "char_count": len(original_text),
        "analysed_at": datetime.now(timezone.utc).isoformat(),
        "language_code": LANGUAGE_CODE,
    }


def save_result(payload: dict, source_key: str) -> str:
    """Save JSON payload to the output S3 bucket. Returns the output key."""
    filename = source_key.split("/")[-1]  # strip any folder prefix
    output_key = f"{OUTPUT_PREFIX}{filename}.json"

    s3_client.put_object(
        Bucket=OUTPUT_BUCKET,
        Key=output_key,
        Body=json.dumps(payload, indent=2),
        ContentType="application/json",
    )
    return output_key
