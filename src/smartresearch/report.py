import html
import re
from urllib.parse import quote

from .schemas import Evidence, Report, Source


def plain(text: str) -> str:
    """Render model/source text as text; links and citation anchors belong to us."""
    text = html.escape(text, quote=False)
    return re.sub(r"([\\\x60*_{}\[\]()#+.!|>~-])", r"\\\1", " ".join(text.split()))


def render_report(
    report: Report, evidence: list[Evidence], sources: list[Source], mode: str
) -> str:
    lines = [f"# {plain(report.title)}", ""]
    if mode == "demo":
        lines += ["> 离线演示：规则摘录生成，未调用大模型。", ""]
    else:
        lines += ["> 本地资料研究报告：由模型提取证据并组织内容。", ""]
    lines += ["> 引用编号与摘录已校验；结论是否得到原文支持仍需人工复核。", ""]
    for section in report.sections:
        lines += [f"## {plain(section.title)}", ""]
        for claim in section.claims:
            citations = " ".join(
                f"[{item_id}](#{item_id.lower()})" for item_id in dict.fromkeys(claim.evidence_ids)
            )
            lines += [f"- {plain(claim.text)} {citations}"]
        lines.append("")
    if not evidence:
        lines += ["## 资料不足", "", "当前资料中没有找到可用于回答主题的有效证据。", ""]
    lines += ["## 信息缺口", ""]
    lines += [f"- {plain(gap)}" for gap in report.gaps] or [
        "- 模型未列出额外缺口，这不代表资料已全面覆盖研究主题。"
    ]
    lines += ["", "## 证据与原文", ""]
    for item in evidence:
        lines += [
            f'<a id="{item.id.lower()}"></a>',
            f"### {item.id}",
            "",
            f"来源：[{item.source_id}](sources/{item.source_id}.txt)，"
            f"第 {item.start_line}–{item.end_line} 行。",
            "",
            f"> {plain(item.quote)}",
            "",
        ]
    lines += ["## 来源列表", ""]
    for source in sources:
        lines += [
            f"- **{source.id}** [{plain(source.title)}](sources/{source.id}.txt)"
            + (f" · [原始网址](<{quote(source.url, safe=':/?=&%#')}>)" if source.url else ""),
        ]
        if source.note:
            lines.append(f"  说明：{plain(source.note)}")
    return "\n".join(lines) + "\n"
