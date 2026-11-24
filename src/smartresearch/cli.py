import argparse
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

from .pipeline import run_research
from .providers import DemoProvider, OpenAIProvider
from .sources import ResearchError

DEFAULT_TOPIC = "比较基础 RAG、混合检索和重排序方案，并给出可追溯的资料依据"


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="SmartResearch-Agent：从本地资料生成带引用的研究报告。",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--topic", default=DEFAULT_TOPIC, help="研究主题")
    parser.add_argument(
        "--sources", type=Path, default=Path("examples/sources.json"), help="资料清单"
    )
    parser.add_argument("--output", type=Path, default=Path("runs"), help="运行记录根目录")
    parser.add_argument(
        "--provider",
        choices=["demo", "openai"],
        default="demo",
        help="demo 为离线规则摘录；openai 为真实模型调用",
    )
    parser.add_argument("--model", help="OpenAI 模型 ID，优先于 OPENAI_MODEL")
    args = parser.parse_args(argv)
    load_dotenv(Path.cwd() / ".env", override=False)
    try:
        if args.provider == "openai":
            api_key = os.getenv("OPENAI_API_KEY", "").strip()
            model = (args.model or os.getenv("OPENAI_MODEL", "")).strip()
            if not api_key or not model:
                raise ResearchError(
                    "缺少 OPENAI_API_KEY 或 OPENAI_MODEL。"
                    "请复制 .env.example 为 .env 并在本地填写，再用 --provider openai 运行。"
                )
            provider = OpenAIProvider(api_key=api_key, model=model)
        else:
            provider = DemoProvider()
            print("离线演示模式：规则摘录，不调用大模型。", flush=True)
        run_dir = run_research(
            args.topic, args.sources, args.output, provider, progress=lambda s: print(s, flush=True)
        )
    except ResearchError as exc:
        print(f"错误：{exc}", file=sys.stderr)
        return 1
    except OSError:
        print("错误：文件读写失败，请检查资料和输出目录权限。", file=sys.stderr)
        return 1
    print(f"报告：{run_dir / 'report.md'}")
    print(f"运行记录：{run_dir / 'run.json'}")
    return 0
