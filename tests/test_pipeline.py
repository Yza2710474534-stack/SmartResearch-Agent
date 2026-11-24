import hashlib
import json
from pathlib import Path

import pytest

from smartresearch.cli import main
from smartresearch.pipeline import run_research
from smartresearch.providers import DemoProvider
from smartresearch.schemas import Claim, EvidenceCandidate, Extraction, Report, Section
from smartresearch.sources import ResearchError, load_sources

EXAMPLE = Path(__file__).resolve().parents[1] / "examples" / "sources.json"


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def test_demo_is_repeatable_and_every_quote_resolves(tmp_path):
    first = run_research("RAG 方案比较", EXAMPLE, tmp_path, DemoProvider())
    second = run_research("RAG 方案比较", EXAMPLE, tmp_path, DemoProvider())
    assert first != second
    assert (first / "report.md").read_bytes() == (second / "report.md").read_bytes()
    report = (first / "report.md").read_text(encoding="utf-8")
    assert "未调用大模型" in report
    for evidence in read_json(first / "evidence.json"):
        source = (first / "sources" / f"{evidence['source_id']}.txt").read_text(encoding="utf-8")
        assert evidence["quote"] in source
        lines = source.splitlines()[evidence["start_line"] - 1 : evidence["end_line"]]
        assert evidence["quote"] in "\n".join(lines)
        assert f"[{evidence['id']}](#{evidence['id'].lower()})" in report
    for source in read_json(first / "sources.json"):
        snapshot = (first / "sources" / f"{source['id']}.txt").read_bytes()
        assert hashlib.sha256(snapshot).hexdigest() == source["sha256"]
    checks = read_json(first / "validation.json")
    assert checks["evidence_count"] == 6
    assert checks["semantic_support_verified"] is False
    assert read_json(first / "run.json")["usage"]["requests"] == 0


@pytest.mark.parametrize(
    "source_id,quote",
    [("S999", "检索先于生成。"), ("S1", "实验准确率达到 99%。")],
)
def test_invalid_evidence_stops_writer_and_preserves_failure(
    tmp_path, local_manifest, source_id, quote
):
    class InvalidExtractor(DemoProvider):
        def extract(self, topic, sources):
            return Extraction(
                items=[EvidenceCandidate(source_id=source_id, quote=quote, finding="结论")],
                gaps=[],
            )

        def write(self, *args):
            pytest.fail("Invalid evidence must never reach the writer")

    root = tmp_path / "runs"
    with pytest.raises(ResearchError):
        run_research("主题", local_manifest, root, InvalidExtractor())
    run = next(root.iterdir())
    metadata = read_json(run / "run.json")
    assert metadata["status"] == "failed"
    assert metadata["failed_stage"] == "extract"
    assert (run / "extraction.json").exists()
    assert not (run / "report.md").exists()


def test_no_evidence_skips_writer_and_produces_gap_report(tmp_path, local_manifest):
    class NoEvidence(DemoProvider):
        def extract(self, *args):
            return Extraction(items=[], gaps=["缺少所需实验数据"])

        def write(self, *args):
            pytest.fail("No evidence must not trigger unsupported generation")

    run = run_research("哪种方案准确率最高", local_manifest, tmp_path / "runs", NoEvidence())
    report = read_json(run / "report.json")
    assert report["sections"] == []
    assert "缺少所需实验数据" in report["gaps"]
    assert "资料不足" in (run / "report.md").read_text(encoding="utf-8")


def test_writer_cannot_cite_invented_evidence(tmp_path, local_manifest):
    class BadWriter(DemoProvider):
        def write(self, *args):
            return Report(
                title="报告",
                sections=[
                    Section(
                        title="结论", claims=[Claim(text="没有依据的结论", evidence_ids=["E99"])]
                    )
                ],
                gaps=[],
            )

    root = tmp_path / "runs"
    with pytest.raises(ResearchError, match="E99"):
        run_research("主题", local_manifest, root, BadWriter())
    run = next(root.iterdir())
    assert read_json(run / "run.json")["failed_stage"] == "validate"
    assert not (run / "report.md").exists()


def test_line_numbers_preserve_original_leading_blank_line(local_manifest):
    source = load_sources(local_manifest)[0]
    assert source.content.startswith("\n# 测试资料")
    from smartresearch.validation import validate_extraction

    evidence = validate_extraction(
        Extraction(
            items=[
                EvidenceCandidate(
                    source_id="S1",
                    quote="检索先于生成。\n本资料没有准确率实验。",
                    finding="仅有流程描述",
                )
            ],
            gaps=[],
        ),
        [source],
    )
    assert (evidence[0].start_line, evidence[0].end_line) == (4, 5)


@pytest.mark.parametrize("change", ["duplicate", "escape", "empty", "encoding", "too_large"])
def test_invalid_input_is_rejected(local_manifest, change):
    data = read_json(local_manifest)
    source = local_manifest.parent / "source.txt"
    if change == "duplicate":
        data["sources"].append(data["sources"][0])
    elif change == "escape":
        data["sources"][0]["path"] = "../outside.txt"
    elif change == "empty":
        source.write_text(" \n ", encoding="utf-8")
    elif change == "encoding":
        source.write_bytes(b"\xff")
    else:
        source.write_text("a" * 100_001, encoding="utf-8")
    local_manifest.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(ResearchError):
        load_sources(local_manifest)


def test_openai_without_configuration_fails_instead_of_using_demo(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_MODEL", raising=False)
    assert main(["--provider", "openai"]) == 1
    captured = capsys.readouterr()
    assert "OPENAI_API_KEY" in captured.err
    assert "离线演示模式" not in captured.out
    assert not (tmp_path / "runs").exists()
