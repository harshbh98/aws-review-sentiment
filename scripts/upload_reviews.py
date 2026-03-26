#!/usr/bin/env python3
"""
upload_reviews.py
-----------------
Utility script to upload sample review files to S3 and poll for sentiment results.

Usage:
    python scripts/upload_reviews.py --bucket <INPUT_BUCKET> [--output-bucket <OUTPUT_BUCKET>]

Requirements:
    pip install boto3
    AWS credentials configured via ~/.aws/credentials or environment variables.
"""

import argparse
import json
import os
import sys
import time
import boto3
from botocore.exceptions import ClientError

# -------------------------------------------------------
# Sample review data
# -------------------------------------------------------
SAMPLE_REVIEWS = [
    ("review-positive-001.txt",
     "This product is absolutely outstanding! The quality exceeded all expectations. "
     "Delivery was fast, packaging was perfect, and the item works flawlessly. "
     "I will definitely purchase again and recommend to everyone."),

    ("review-negative-001.txt",
     "Terrible experience from start to finish. The product arrived broken and the "
     "customer service was completely unhelpful. I waited three weeks only to receive "
     "a damaged item. Avoid this seller at all costs."),

    ("review-neutral-001.txt",
     "The product arrived on time and matches the description. It does what it says "
     "it does. Nothing particularly impressive or disappointing. Average quality "
     "for the price point."),

    ("review-mixed-001.txt",
     "The design is beautiful and feels premium, but the battery life is disappointing. "
     "Setup was easy which I appreciated, however the app crashes frequently. "
     "Great potential but needs improvement."),
]


def upload_reviews(s3_client, bucket: str, prefix: str = "reviews/"):
    """Upload sample reviews to S3 and return the list of keys."""
    keys = []
    for filename, text in SAMPLE_REVIEWS:
        key = f"{prefix}{filename}"
        print(f"  Uploading s3://{bucket}/{key} …", end=" ")
        try:
            s3_client.put_object(
                Bucket=bucket,
                Key=key,
                Body=text.encode("utf-8"),
                ContentType="text/plain",
            )
            print("✓")
            keys.append(key)
        except ClientError as exc:
            print(f"✗  {exc}")
    return keys


def poll_results(s3_client, output_bucket: str, input_keys: list, timeout: int = 60):
    """Poll the output bucket until all results appear (or timeout)."""
    expected = {
        f"sentiment-results/{k.split('/')[-1]}.json"
        for k in input_keys
    }
    found = {}
    deadline = time.time() + timeout

    print(f"\nPolling s3://{output_bucket} for results (up to {timeout}s) …")

    while time.time() < deadline and len(found) < len(expected):
        for key in list(expected - found.keys()):
            try:
                resp = s3_client.get_object(Bucket=output_bucket, Key=key)
                payload = json.loads(resp["Body"].read())
                found[key] = payload
                sentiment = payload.get("sentiment", "?")
                scores    = payload.get("scores", {})
                print(f"  ✓ {key}")
                print(f"    sentiment={sentiment}  "
                      f"pos={scores.get('positive', 0):.4f}  "
                      f"neg={scores.get('negative', 0):.4f}")
            except ClientError:
                pass  # Not ready yet
        if len(found) < len(expected):
            time.sleep(3)

    missing = expected - found.keys()
    if missing:
        print(f"\n⚠  Timed out. Missing results for: {missing}")
    else:
        print("\n✅  All sentiment results received successfully!")

    return found


def main():
    parser = argparse.ArgumentParser(description="Upload test reviews and verify sentiment results")
    parser.add_argument("--bucket",        required=True, help="Input S3 bucket name")
    parser.add_argument("--output-bucket", default=None,  help="Output S3 bucket name (optional, for result polling)")
    parser.add_argument("--region",        default="us-east-1")
    parser.add_argument("--timeout",       type=int, default=60, help="Seconds to wait for results")
    parser.add_argument("--prefix",        default="reviews/", help="S3 key prefix for uploads")
    args = parser.parse_args()

    s3 = boto3.client("s3", region_name=args.region)

    print(f"\n{'='*55}")
    print("  AWS Customer Review Sentiment – Test Upload Script")
    print(f"{'='*55}")
    print(f"  Input bucket : {args.bucket}")
    if args.output_bucket:
        print(f"  Output bucket: {args.output_bucket}")
    print()

    print("Uploading sample reviews …")
    uploaded_keys = upload_reviews(s3, args.bucket, args.prefix)

    if not uploaded_keys:
        print("No files uploaded. Check your bucket name and AWS credentials.")
        sys.exit(1)

    if args.output_bucket:
        poll_results(s3, args.output_bucket, uploaded_keys, timeout=args.timeout)
    else:
        print("\nSkipping result polling (--output-bucket not provided).")
        print("Upload complete. Monitor the Lambda function in the AWS Console.")


if __name__ == "__main__":
    main()
