"""Typed boundaries between loading, extraction, writing and validation."""

from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class SourceEntry(StrictModel):
    id: str = Field(pattern=r"^S[1-9]\d*$")
    title: str = Field(min_length=1)
    path: str = Field(min_length=1)
    url: Optional[str] = None
    note: str = ""


class SourceManifest(StrictModel):
    sources: list[SourceEntry] = Field(min_length=1, max_length=20)


class Source(SourceEntry):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=False)
    content: str = Field(min_length=1)
    sha256: str


class EvidenceCandidate(StrictModel):
    source_id: str
    quote: str = Field(min_length=1)
    finding: str = Field(min_length=1)


class Extraction(StrictModel):
    items: list[EvidenceCandidate] = Field(max_length=30)
    gaps: list[str]


class Evidence(EvidenceCandidate):
    id: str
    start_line: int
    end_line: int


class Claim(StrictModel):
    text: str = Field(min_length=1)
    evidence_ids: list[str] = Field(min_length=1)


class Section(StrictModel):
    title: str = Field(min_length=1)
    claims: list[Claim] = Field(min_length=1)


class Report(StrictModel):
    title: str = Field(min_length=1)
    sections: list[Section]
    gaps: list[str]


class Usage(StrictModel):
    input_tokens: int = 0
    output_tokens: int = 0
    requests: int = 0
