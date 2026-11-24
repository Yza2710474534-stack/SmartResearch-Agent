"""Rebuild the committed, deterministic demo using only bundled public notes."""

import shutil
import tempfile
from pathlib import Path

from smartresearch.cli import DEFAULT_TOPIC
from smartresearch.pipeline import run_research
from smartresearch.providers import DemoProvider


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    target = root / "examples" / "demo"
    target.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="smartresearch-demo-") as temporary:
        run = run_research(
            DEFAULT_TOPIC,
            root / "examples" / "sources.json",
            Path(temporary),
            DemoProvider(),
        )
        for name in ("report.md", "evidence.json", "validation.json"):
            shutil.copyfile(run / name, target / name)
        shutil.copytree(run / "sources", target / "sources", dirs_exist_ok=True)
    print(f"演示输出已更新：{target}")


if __name__ == "__main__":
    main()
