"""
Unit tests for the Review Sentiment Lambda function.
Run with: pytest tests/ -v
"""

import json
import sys
import os
import pytest
from unittest.mock import MagicMock, patch

# ---------------------------------------------------------------------------
# Ensure src/ is importable without installing
# ---------------------------------------------------------------------------
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))


# ---------------------------------------------------------------------------
# Shared fixtures / helpers
# ---------------------------------------------------------------------------

SAMPLE_REVIEW = "This product is absolutely amazing! Best purchase I have ever made."
SAMPLE_KEY = "reviews/review-001.txt"
INPUT_BUCKET = "customer-reviews-raw"
OUTPUT_BUCKET = "customer-reviews-sentiment"

MOCK_COMPREHEND_RESPONSE = {
    "Sentiment": "POSITIVE",
    "SentimentScore": {
        "Positive": 0.9987,
        "Negative": 0.0002,
        "Neutral":  0.0010,
        "Mixed":    0.0001,
    },
    "ResponseMetadata": {},
}


def make_s3_event(bucket=INPUT_BUCKET, key=SAMPLE_KEY):
    """Build a minimal S3 PUT event."""
    return {
        "Records": [
            {
                "s3": {
                    "bucket": {"name": bucket},
                    "object": {"key": key},
                }
            }
        ]
    }


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestLambdaHandler:
    """Tests for the top-level lambda_handler entry point."""

    @patch("lambda_function.process_record")
    def test_handler_calls_process_for_each_record(self, mock_process):
        import lambda_function
        mock_process.return_value = {"status": "ok"}

        event = {"Records": [make_s3_event()["Records"][0]] * 3}
        result = lambda_function.lambda_handler(event, None)

        assert result["processed"] == 3
        assert mock_process.call_count == 3

    @patch("lambda_function.process_record", side_effect=Exception("boom"))
    def test_handler_captures_per_record_errors(self, _mock):
        import lambda_function
        result = lambda_function.lambda_handler(make_s3_event(), None)

        assert result["statusCode"] == 200
        assert result["results"][0]["status"] == "error"
        assert "boom" in result["results"][0]["error"]


class TestProcessRecord:
    """Tests for process_record."""

    def _make_record(self, bucket=INPUT_BUCKET, key=SAMPLE_KEY):
        return make_s3_event(bucket, key)["Records"][0]

    @patch("lambda_function.save_result", return_value="sentiment-results/review-001.txt.json")
    @patch("lambda_function.analyse_sentiment", return_value=MOCK_COMPREHEND_RESPONSE)
    @patch("lambda_function.read_s3_object", return_value=SAMPLE_REVIEW)
    def test_happy_path(self, _read, _analyse, _save):
        import lambda_function
        result = lambda_function.process_record(self._make_record())

        assert result["status"] == "ok"
        assert result["sentiment"] == "POSITIVE"

    @patch("lambda_function.read_s3_object", return_value="   ")
    def test_empty_content_skipped(self, _read):
        import lambda_function
        result = lambda_function.process_record(self._make_record())

        assert result["status"] == "skipped"

    @patch("lambda_function.read_s3_object", return_value=SAMPLE_REVIEW)
    def test_url_encoded_key_decoded(self, mock_read):
        import lambda_function
        record = self._make_record(key="reviews/my%20review.txt")
        with patch("lambda_function.analyse_sentiment", return_value=MOCK_COMPREHEND_RESPONSE), \
             patch("lambda_function.save_result", return_value="out.json"):
            lambda_function.process_record(record)

        # read_s3_object should receive the decoded key
        actual_key = mock_read.call_args[0][1]
        assert actual_key == "reviews/my review.txt"


class TestTruncateText:
    def test_short_text_unchanged(self):
        import lambda_function
        text = "hello world"
        assert lambda_function.truncate_text(text) == text

    def test_long_text_truncated(self):
        import lambda_function
        long_text = "a" * 6000
        result = lambda_function.truncate_text(long_text)
        assert len(result.encode("utf-8")) <= lambda_function.MAX_TEXT_BYTES


class TestBuildPayload:
    def test_payload_structure(self):
        import lambda_function
        payload = lambda_function.build_payload(
            SAMPLE_KEY, SAMPLE_REVIEW, MOCK_COMPREHEND_RESPONSE
        )
        assert payload["sentiment"] == "POSITIVE"
        assert payload["source_key"] == SAMPLE_KEY
        assert set(payload["scores"].keys()) == {"positive", "negative", "neutral", "mixed"}
        assert payload["char_count"] == len(SAMPLE_REVIEW)
        assert "analysed_at" in payload

    def test_scores_rounded(self):
        import lambda_function
        payload = lambda_function.build_payload(
            SAMPLE_KEY, SAMPLE_REVIEW, MOCK_COMPREHEND_RESPONSE
        )
        for val in payload["scores"].values():
            # Should have at most 6 decimal places
            assert len(str(val).split(".")[-1]) <= 6


class TestSaveResult:
    @patch("lambda_function.s3_client")
    def test_saves_to_correct_bucket_and_key(self, mock_s3):
        import lambda_function
        lambda_function.OUTPUT_BUCKET = OUTPUT_BUCKET
        lambda_function.OUTPUT_PREFIX = "sentiment-results/"

        payload = {"sentiment": "POSITIVE", "scores": {}}
        output_key = lambda_function.save_result(payload, "reviews/test.txt")

        assert output_key == "sentiment-results/test.txt.json"
        mock_s3.put_object.assert_called_once()
        call_kwargs = mock_s3.put_object.call_args[1]
        assert call_kwargs["Bucket"] == OUTPUT_BUCKET
        assert call_kwargs["ContentType"] == "application/json"


class TestAnalyseSentiment:
    @patch("lambda_function.comprehend_client")
    def test_calls_detect_sentiment(self, mock_comprehend):
        import lambda_function
        mock_comprehend.detect_sentiment.return_value = MOCK_COMPREHEND_RESPONSE
        lambda_function.LANGUAGE_CODE = "en"

        result = lambda_function.analyse_sentiment(SAMPLE_REVIEW)

        mock_comprehend.detect_sentiment.assert_called_once_with(
            Text=SAMPLE_REVIEW,
            LanguageCode="en",
        )
        assert result["Sentiment"] == "POSITIVE"


class TestReadS3Object:
    @patch("lambda_function.s3_client")
    def test_reads_and_decodes(self, mock_s3):
        import lambda_function
        body_mock = MagicMock()
        body_mock.read.return_value = SAMPLE_REVIEW.encode("utf-8")
        mock_s3.get_object.return_value = {"Body": body_mock}

        text = lambda_function.read_s3_object(INPUT_BUCKET, SAMPLE_KEY)
        assert text == SAMPLE_REVIEW
        mock_s3.get_object.assert_called_once_with(Bucket=INPUT_BUCKET, Key=SAMPLE_KEY)
