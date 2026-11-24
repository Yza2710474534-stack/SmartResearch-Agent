import json

import httpx
import pytest
from openai import OpenAI

from smartresearch.pipeline import run_research
from smartresearch.providers import OpenAIProvider
from smartresearch.schemas import Extraction
from smartresearch.sources import ResearchError


def response_body(payload=None, *, refusal=False, status="completed"):
    content = (
        {"type": "refusal", "refusal": "无法回答"}
        if refusal
        else {"type": "output_text", "text": json.dumps(payload), "annotations": []}
    )
    return {
        "id": "resp_test",
        "object": "response",
        "created_at": 1,
        "status": status,
        "model": "test-model",
        "output": [
            {
                "id": "msg_test",
                "type": "message",
                "role": "assistant",
                "status": "completed",
                "content": [content],
            }
        ],
        "usage": {
            "input_tokens": 20,
            "output_tokens": 10,
            "total_tokens": 30,
            "input_tokens_details": {"cached_tokens": 0},
            "output_tokens_details": {"reasoning_tokens": 0},
        },
    }


def make_provider(handler):
    client = OpenAI(
        api_key="test-placeholder",
        base_url="https://unit.test/v1",
        max_retries=0,
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    )
    return OpenAIProvider(api_key="test-placeholder", model="test-model", client=client)


def test_real_sdk_serializes_schema_parses_responses_and_runs_pipeline(tmp_path, local_manifest):
    requests = []
    payloads = [
        {
            "items": [{"source_id": "S1", "quote": "检索先于生成。", "finding": "先检索，再生成"}],
            "gaps": ["没有准确率实验"],
        },
        {
            "title": "RAG 流程",
            "sections": [
                {
                    "title": "流程",
                    "claims": [{"text": "检索在生成之前进行。", "evidence_ids": ["E1"]}],
                }
            ],
            "gaps": [],
        },
    ]

    def handler(request):
        assert request.url.path == "/v1/responses"
        data = json.loads(request.content)
        requests.append(data)
        assert data["text"]["format"]["type"] == "json_schema"
        assert data["text"]["format"]["strict"] is True
        assert data["store"] is False
        assert data["input"][0]["role"] == "system"
        return httpx.Response(200, json=response_body(payloads[len(requests) - 1]))

    provider = make_provider(handler)
    try:
        run = run_research("RAG 流程", local_manifest, tmp_path / "runs", provider)
    finally:
        provider.client.close()
    assert len(requests) == 2
    report = json.loads((run / "report.json").read_text())
    assert "没有准确率实验" in report["gaps"]
    assert "[E1](#e1)" in (run / "report.md").read_text()
    metadata = json.loads((run / "run.json").read_text())
    assert metadata["usage"] == {"input_tokens": 40, "output_tokens": 20, "requests": 2}
    assert metadata["status"] == "completed"
    assert "test-placeholder" not in (run / "run.json").read_text()


@pytest.mark.parametrize(
    "failure", ["refusal", "schema", "incomplete", "unauthorized", "rate_limit"]
)
def test_provider_failures_are_actionable_and_do_not_leak_response_text(failure):
    def handler(request):
        if failure in {"unauthorized", "rate_limit"}:
            code = 401 if failure == "unauthorized" else 429
            return httpx.Response(code, json={"error": {"message": "SECRET_SHOULD_NOT_LEAK"}})
        if failure == "refusal":
            return httpx.Response(200, json=response_body(refusal=True))
        if failure == "incomplete":
            return httpx.Response(
                200, json=response_body({"items": [], "gaps": []}, status="incomplete")
            )
        return httpx.Response(200, json=response_body({"items": "SECRET_SHOULD_NOT_LEAK"}))

    provider = make_provider(handler)
    try:
        with pytest.raises(ResearchError) as exc:
            provider._parse("提取", {}, Extraction)
        assert "SECRET_SHOULD_NOT_LEAK" not in str(exc.value)
    finally:
        provider.client.close()
