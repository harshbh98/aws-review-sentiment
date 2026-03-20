# 🛒 AWS Customer Review Sentiment Analysis Pipeline

[![CI/CD](https://github.com/YOUR_USERNAME/aws-review-sentiment/actions/workflows/ci.yml/badge.svg)](https://github.com/YOUR_USERNAME/aws-review-sentiment/actions)
[![Python 3.12](https://img.shields.io/badge/python-3.12-blue.svg)](https://www.python.org/)
[![Terraform](https://img.shields.io/badge/terraform-1.7-purple.svg)](https://www.terraform.io/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

A fully serverless, event-driven pipeline that automatically analyses the sentiment of customer reviews using **Amazon Comprehend**, **AWS Lambda**, **S3**, and **Amazon Athena**.

---

## Architecture

```
amazon.com reviews
        |
        v  (upload)
+-------------------+
|  S3 Input Bucket  |  <-- reviews/*.txt
|  (raw reviews)    |
+--------+----------+
         |  S3 Event Trigger (ObjectCreated)
         v
+-------------------+        +--------------------------+
|  AWS Lambda       +------->+  Amazon Comprehend       |
|  (Python 3.12)    +<-------+  DetectSentiment API     |
+--------+----------+        +--------------------------+
         |  writes JSON result
         v
+-------------------+
|  S3 Output Bucket |  <-- sentiment-results/*.json
|  (sentiment data) |
+--------+----------+
         |
         v
+-------------------+
|  Amazon Athena    |  <-- Interactive SQL queries
|  (analytics)     |
+-------------------+
```

---

## Project Structure

```
aws-review-sentiment/
├── src/
│   └── lambda_function.py       # Lambda handler + business logic
├── tests/
│   └── test_lambda_function.py  # Unit tests (pytest)
├── terraform/
│   ├── main.tf                  # All AWS resources
│   ├── variables.tf             # Input variables
│   └── outputs.tf               # Resource outputs
├── scripts/
│   └── upload_reviews.py        # Helper: upload test reviews & poll results
├── docs/
│   └── athena_queries.sql       # Ready-to-run Athena SQL queries
├── .github/
│   └── workflows/
│       └── ci.yml               # GitHub Actions CI/CD pipeline
├── requirements.txt             # Runtime dependencies
├── requirements-dev.txt         # Dev/test dependencies
└── README.md
```

---

## Prerequisites

| Tool | Version | Install |
|------|---------|---------|
| Python | 3.12+ | python.org |
| AWS CLI | v2 | docs.aws.amazon.com |
| Terraform | 1.5+ | terraform.io |
| Git | any | git-scm.com |

Configure AWS credentials:
```bash
aws configure
```

---

## Quick Start

### 1. Clone

```bash
git clone https://github.com/YOUR_USERNAME/aws-review-sentiment.git
cd aws-review-sentiment
```

### 2. Install Python Dependencies

```bash
python -m venv .venv
source .venv/bin/activate       # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt
```

### 3. Run Unit Tests

```bash
pytest tests/ -v
```

All tests pass without AWS credentials (they use mocks).

### 4. Deploy with Terraform

```bash
cd terraform
terraform init
terraform plan  -var="environment=dev"
terraform apply -var="environment=dev"
```

Note the output values (bucket names, Lambda name, Athena database).

### 5. Upload Test Reviews and Verify

```bash
cd ..
python scripts/upload_reviews.py \
  --bucket      review-sentiment-reviews-raw-dev \
  --output-bucket review-sentiment-reviews-sentiment-dev \
  --region us-east-1
```

Expected output:
```
Uploading sample reviews ...
  Uploading s3://.../reviews/review-positive-001.txt  ok
  Uploading s3://.../reviews/review-negative-001.txt  ok

Polling for results ...
  ok  sentiment-results/review-positive-001.txt.json
      sentiment=POSITIVE  pos=0.9987  neg=0.0002
  ok  sentiment-results/review-negative-001.txt.json
      sentiment=NEGATIVE  pos=0.0003  neg=0.9981

All sentiment results received successfully!
```

### 6. Query with Athena

Open the Athena Console and run queries from `docs/athena_queries.sql`.

```sql
SELECT sentiment, COUNT(*) AS total
FROM review_sentiment_dev.sentiment_results
GROUP BY sentiment;
```

---

## Running Tests

```bash
# All tests with coverage report
pytest tests/ -v --cov=src --cov-report=term-missing

# One test class only
pytest tests/ -v -k "TestBuildPayload"
```

---

## Configuration

Lambda environment variables (set by Terraform):

| Variable | Default | Description |
|----------|---------|-------------|
| `OUTPUT_BUCKET` | `review-sentiment-reviews-sentiment-dev` | Destination S3 bucket |
| `OUTPUT_PREFIX` | `sentiment-results/` | Key prefix for result files |
| `LANGUAGE_CODE` | `en` | BCP-47 language code for Comprehend |

---

## CI/CD with GitHub Actions

| Job | Trigger | What it does |
|-----|---------|--------------|
| Lint & Test | All branches | flake8, pytest, coverage |
| Terraform Validate | All branches | init, validate, fmt check |
| Deploy to dev | Push to `main` | package Lambda + terraform apply |

### Required GitHub Secrets

| Secret | Value |
|--------|-------|
| `AWS_DEPLOY_ROLE_ARN` | IAM role ARN for deployments (OIDC) |
| `AWS_REGION` | e.g. `us-east-1` |

---

## Cost Estimate

| Service | Free Tier | Beyond Free Tier |
|---------|-----------|-----------------|
| Amazon Comprehend | 50K units/month (12 months) | $0.0001 per unit |
| AWS Lambda | 1M requests/month | $0.20 per 1M requests |
| S3 | 5 GB storage | $0.023/GB |
| Athena | — | $5 per TB scanned |

For dev/test usage, monthly cost is effectively $0.

---

## Teardown

```bash
cd terraform
terraform destroy -var="environment=dev"
```

---

## License

MIT License.
