"""Persists deliberation transcripts to Alibaba Cloud OSS (Object Storage
Service).

This file is the hackathon submission's "Proof of Alibaba Cloud Deployment"
artifact: it is real usage of an Alibaba Cloud SDK against a real Alibaba
Cloud service, not just a hosting location claim. Link this file directly
in the submission's proof-of-deployment field, alongside the ECS deployment
described in deploy/README.md.
"""

import os

import oss2

from quorumqa.schemas import QuestionResult

_bucket: oss2.Bucket | None = None


def _get_bucket() -> oss2.Bucket:
    global _bucket
    if _bucket is not None:
        return _bucket
    access_key_id = os.environ["OSS_ACCESS_KEY_ID"]
    access_key_secret = os.environ["OSS_ACCESS_KEY_SECRET"]
    endpoint = os.environ.get("OSS_ENDPOINT", "https://oss-ap-southeast-1.aliyuncs.com")
    bucket_name = os.environ.get("OSS_BUCKET", "quorumqa-transcripts")
    auth = oss2.Auth(access_key_id, access_key_secret)
    _bucket = oss2.Bucket(auth, endpoint, bucket_name)
    return _bucket


def upload_question_result(result: QuestionResult, run_id: str) -> str:
    """Uploads one question's full transcript + Verdict Card data as JSON.
    Returns the OSS object key."""
    bucket = _get_bucket()
    key = f"runs/{run_id}/{result.item.question_id}.json"
    bucket.put_object(key, result.model_dump_json(indent=2))
    return key


def upload_run_summary(summary_markdown: str, run_id: str) -> str:
    bucket = _get_bucket()
    key = f"runs/{run_id}/summary.md"
    bucket.put_object(key, summary_markdown)
    return key


def object_url(key: str) -> str:
    bucket = _get_bucket()
    return f"https://{bucket.bucket_name}.{bucket.endpoint.replace('https://', '')}/{key}"
