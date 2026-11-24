import hashlib
from pathlib import Path
from urllib.parse import urlparse

from pydantic import ValidationError

from .schemas import Source, SourceManifest

MAX_FILE_BYTES = 100_000
MAX_TOTAL_CHARS = 60_000


class ResearchError(Exception):
    """An actionable error safe to show and save without provider credentials."""


def load_sources(manifest_path: Path) -> list[Source]:
    manifest_path = manifest_path.resolve()
    try:
        manifest = SourceManifest.model_validate_json(manifest_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, ValidationError) as exc:
        raise ResearchError(
            "资料清单无法读取或格式错误，请检查 UTF-8 JSON 与 sources 字段。"
        ) from exc

    base = manifest_path.parent
    seen = set()
    sources = []
    for entry in manifest.sources:
        if entry.id in seen:
            raise ResearchError(f"资料编号重复：{entry.id}。请为每份资料分配独立编号。")
        seen.add(entry.id)
        path = (base / entry.path).resolve()
        if base not in path.parents or path.suffix.lower() not in {".md", ".txt"}:
            raise ResearchError(f"{entry.id}：path 必须指向清单目录内的 .md 或 .txt 文件。")
        if entry.url:
            url = urlparse(entry.url)
            if url.scheme not in {"http", "https"} or not url.netloc:
                raise ResearchError(f"{entry.id}：来源 URL 必须是完整的 HTTP/HTTPS 地址。")
        try:
            if path.stat().st_size > MAX_FILE_BYTES:
                raise ResearchError(f"{entry.id}：资料超过 100 KB，请拆分后再运行。")
            content = path.read_text(encoding="utf-8")
        except (OSError, UnicodeError) as exc:
            raise ResearchError(f"{entry.id}：无法读取 UTF-8 文本，请检查文件路径和编码。") from exc
        if not content.strip():
            raise ResearchError(f"{entry.id}：资料内容为空。")
        sources.append(
            Source(
                **entry.model_dump(exclude={"path"}),
                path=path.relative_to(base).as_posix(),
                content=content,
                sha256=hashlib.sha256(content.encode("utf-8")).hexdigest(),
            )
        )
    if sum(len(source.content) for source in sources) > MAX_TOTAL_CHARS:
        raise ResearchError("资料总长度超过 60,000 字符，请缩小资料范围或拆分运行。")
    return sources
