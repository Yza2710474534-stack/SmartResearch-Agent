import re

from .schemas import Evidence, Extraction, Report, Source
from .sources import ResearchError


def validate_extraction(extraction: Extraction, sources: list[Source]) -> list[Evidence]:
    """Reject invented source IDs and quotes before they can reach the writer."""
    source_map = {source.id: source for source in sources}
    evidence = []
    for index, item in enumerate(extraction.items, start=1):
        source = source_map.get(item.source_id)
        if source is None:
            raise ResearchError(f"证据 {index} 引用了不存在的资料 {item.source_id}。")
        offset = source.content.find(item.quote)
        if offset == -1:
            raise ResearchError(f"证据 {index} 的摘录在 {item.source_id} 原文中不存在。")
        start_line = source.content.count("\n", 0, offset) + 1
        evidence.append(
            Evidence(
                **item.model_dump(),
                id=f"E{index}",
                start_line=start_line,
                end_line=start_line + item.quote.count("\n"),
            )
        )
    return evidence


def validate_report(report: Report, evidence: list[Evidence]) -> dict:
    known = {item.id for item in evidence}
    claims = [claim for section in report.sections for claim in section.claims]
    if evidence and not claims:
        raise ResearchError("已有证据但报告没有任何结论，请检查写作输出。")
    for claim in claims:
        unknown = set(claim.evidence_ids) - known
        if unknown:
            raise ResearchError(f"报告引用了不存在的证据：{', '.join(sorted(unknown))}。")
        if re.search(r"\[(?:E|S)\d+\]", claim.text):
            raise ResearchError("报告正文包含手写引用，请通过 evidence_ids 提供引用。")
    return {
        "passed": True,
        "evidence_count": len(evidence),
        "claim_count": len(claims),
        "quote_substrings_verified": True,
        "citation_ids_verified": True,
        "semantic_support_verified": False,
        "note": "仅校验摘录存在和引用关联；原文是否支持推论仍需人工复核。",
    }
