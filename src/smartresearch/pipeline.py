import hashlib
import json
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Optional

from . import __version__
from .providers import Provider
from .report import render_report
from .schemas import Report
from .sources import ResearchError, load_sources
from .validation import validate_extraction, validate_report


def save_json(path: Path, data) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def run_research(
    topic: str,
    manifest: Path,
    output_root: Path,
    provider: Provider,
    progress: Optional[Callable[[str], None]] = None,
) -> Path:
    if not topic.strip() or len(topic) > 2000:
        raise ResearchError("研究主题必须为 1–2,000 个字符。")
    started = time.monotonic()
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid.uuid4().hex[:8]
    run_dir = output_root.resolve() / run_id
    run_dir.mkdir(parents=True, exist_ok=False)
    metadata = {
        "run_id": run_id,
        "version": __version__,
        "topic": topic.strip(),
        "mode": provider.name,
        "model": provider.model,
        "started_at": datetime.now(timezone.utc).isoformat(),
        "status": "running",
        "semantic_support_verified": False,
    }
    save_json(run_dir / "run.json", metadata)
    stage = "load"

    def emit(message: str) -> None:
        event = {
            "stage": stage,
            "message": message,
            "elapsed_seconds": round(time.monotonic() - started, 3),
        }
        with (run_dir / "events.jsonl").open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(event, ensure_ascii=False) + "\n")
        if progress:
            progress(message)

    try:
        emit("1/4 读取本地资料")
        sources = load_sources(manifest)
        snapshot_dir = run_dir / "sources"
        snapshot_dir.mkdir()
        for source in sources:
            (snapshot_dir / f"{source.id}.txt").write_text(source.content, encoding="utf-8")
        save_json(
            run_dir / "sources.json",
            [source.model_dump(exclude={"content"}) for source in sources],
        )
        metadata["source_count"] = len(sources)
        metadata["input_sha256"] = hashlib.sha256(
            json.dumps(
                [source.model_dump() for source in sources], ensure_ascii=False, sort_keys=True
            ).encode("utf-8")
        ).hexdigest()
        stage = "extract"
        emit("2/4 提取证据并校验原文摘录")
        extraction = provider.extract(topic, sources)
        save_json(run_dir / "extraction.json", extraction.model_dump())
        evidence = validate_extraction(extraction, sources)
        save_json(run_dir / "evidence.json", [item.model_dump() for item in evidence])
        stage = "write"
        emit("3/4 根据有效证据组织报告")
        if evidence:
            report = provider.write(topic, evidence, extraction.gaps)
        else:
            report = Report(
                title=topic, sections=[], gaps=["未提取到与主题相关的证据。", *extraction.gaps]
            )
        report.gaps = list(dict.fromkeys([*extraction.gaps, *report.gaps]))
        stage = "validate"
        emit("4/4 校验引用并保存报告")
        checks = validate_report(report, evidence)
        save_json(run_dir / "validation.json", checks)
        save_json(run_dir / "report.json", report.model_dump())
        (run_dir / "report.md").write_text(
            render_report(report, evidence, sources, provider.name), encoding="utf-8"
        )
        metadata["status"] = "completed"
        emit("报告已生成")
    except Exception as exc:
        metadata["status"] = "failed"
        metadata["failed_stage"] = stage
        metadata["error"] = str(exc) if isinstance(exc, ResearchError) else type(exc).__name__
        if isinstance(exc, ResearchError):
            raise ResearchError(f"{exc} 运行记录：{run_dir}") from exc
        raise
    finally:
        metadata["elapsed_seconds"] = round(time.monotonic() - started, 3)
        metadata["usage"] = provider.usage.model_dump()
        metadata["usage_note"] = "Token 仅统计成功读取到的 API usage；失败请求可能产生未记录用量。"
        save_json(run_dir / "run.json", metadata)
    return run_dir
