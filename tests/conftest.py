import json

import pytest


@pytest.fixture
def local_manifest(tmp_path):
    folder = tmp_path / "input"
    folder.mkdir()
    (folder / "source.txt").write_text(
        "\n# 测试资料\n\n检索先于生成。\n本资料没有准确率实验。\n", encoding="utf-8"
    )
    manifest = folder / "sources.json"
    manifest.write_text(
        json.dumps({"sources": [{"id": "S1", "title": "测试资料", "path": "source.txt"}]}),
        encoding="utf-8",
    )
    return manifest
