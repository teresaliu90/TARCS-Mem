from __future__ import annotations

import argparse
import json
import os
from datetime import date
from pathlib import Path

from .agent import LocalAgentConfig
from .api import create_app
from .confluence import ConfluenceConnector
from .evaluation import run_evaluation
from .models import SourceType
from .public_evaluation import download_fiqa_evaluation_pool, run_fiqa_public_evaluation
from .service import TARCSMemoryService
from .ui import launch_ui


def main() -> None:
    parser = argparse.ArgumentParser(prog="tarcsmem")
    subcommands = parser.add_subparsers(dest="command", required=True)

    seed = subcommands.add_parser("seed")
    seed.add_argument("--db", default="./data/tarcsmem.db")
    seed.add_argument("--if-empty", action="store_true")

    ask = subcommands.add_parser("ask")
    ask.add_argument("--db", default="./data/tarcsmem.db")
    ask.add_argument("--question", required=True)
    ask.add_argument("--as-of", required=True)

    evaluate = subcommands.add_parser("evaluate")
    evaluate.add_argument("--db", default="./data/tarcsmem.db")

    evaluate_public = subcommands.add_parser("evaluate-public")
    evaluate_public.add_argument("--pool", default=None)
    evaluate_public.add_argument("--queries", default=120, type=int)
    evaluate_public.add_argument("--distractors", default=150, type=int)
    evaluate_public.add_argument("--output", default=None)

    confluence = subcommands.add_parser("sync-confluence")
    confluence.add_argument("--db", default="./data/tarcsmem.db")
    confluence.add_argument("--checkpoint", default="./data/confluence-checkpoint.json")
    confluence.add_argument("--base-url", default=None)
    confluence.add_argument("--email", default=None)
    confluence.add_argument("--space-id", default=None)
    confluence.add_argument(
        "--source-type",
        choices=[SourceType.MEETING_NOTE.value, SourceType.OFFICIAL_POLICY.value],
        default=SourceType.MEETING_NOTE.value,
    )
    confluence.add_argument("--authority", type=float, default=0.70)
    confluence.add_argument("--tenant-id", default="default")
    confluence.add_argument("--classification", default="internal")
    confluence.add_argument("--role", action="append", default=[])
    confluence.add_argument("--expire-missing", action="store_true")

    serve = subcommands.add_parser("serve")
    serve.add_argument("--db", default="./data/tarcsmem.db")
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", default=8000, type=int)

    ui = subcommands.add_parser("ui")
    ui.add_argument("--db", default="./data/tarcsmem.db")
    ui.add_argument("--host", default="127.0.0.1")
    ui.add_argument("--port", default=7860, type=int)
    ui.add_argument("--qdrant-url", default=None)
    ui.add_argument("--ollama-url", default=None)
    ui.add_argument("--model", default=None)

    args = parser.parse_args()
    if args.command == "seed":
        service = TARCSMemoryService(args.db)
        print(json.dumps({"seeded": service.seed(if_empty=args.if_empty)}, ensure_ascii=False))
        service.close()
    elif args.command == "ask":
        service = TARCSMemoryService(args.db)
        print(
            json.dumps(
                service.query(args.question, date.fromisoformat(args.as_of)).to_dict(),
                ensure_ascii=False,
                indent=2,
            )
        )
        service.close()
    elif args.command == "evaluate":
        print(json.dumps(run_evaluation(args.db), ensure_ascii=False, indent=2))
    elif args.command == "evaluate-public":
        pool = (
            Path(args.pool)
            if args.pool
            else download_fiqa_evaluation_pool(args.queries, args.distractors)
        )
        report = run_fiqa_public_evaluation(pool)
        rendered = json.dumps(report, ensure_ascii=False, indent=2)
        if args.output:
            output = Path(args.output)
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(rendered + "\n", encoding="utf-8")
        print(rendered)
    elif args.command == "sync-confluence":
        base_url = args.base_url or os.getenv("TARCSMEM_CONFLUENCE_BASE_URL", "")
        email = args.email or os.getenv("TARCSMEM_CONFLUENCE_EMAIL", "")
        space_id = args.space_id or os.getenv("TARCSMEM_CONFLUENCE_SPACE_ID", "")
        token = os.getenv("TARCSMEM_CONFLUENCE_API_TOKEN", "")
        if not all((base_url, email, space_id, token)):
            raise SystemExit(
                "Set TARCSMEM_CONFLUENCE_BASE_URL, TARCSMEM_CONFLUENCE_EMAIL, "
                "TARCSMEM_CONFLUENCE_SPACE_ID and TARCSMEM_CONFLUENCE_API_TOKEN"
            )
        service = TARCSMemoryService(args.db)
        try:
            report = ConfluenceConnector(base_url, email, token, space_id).sync(
                service,
                args.checkpoint,
                tenant_id=args.tenant_id,
                classification=args.classification,
                source_type=SourceType(args.source_type),
                authority=args.authority,
                allowed_roles=args.role,
                expire_missing=args.expire_missing,
            )
            print(json.dumps(report.to_dict(), ensure_ascii=False, indent=2))
        finally:
            service.close()
    elif args.command == "serve":
        try:
            import uvicorn
        except ImportError as exc:  # pragma: no cover
            raise SystemExit("Install API extras: pip install -e '.[api]'") from exc
        uvicorn.run(create_app(args.db), host=args.host, port=args.port)
    elif args.command == "ui":
        config = LocalAgentConfig.from_environment(args.db)
        if args.qdrant_url:
            config.qdrant_url = args.qdrant_url
        if args.ollama_url:
            config.ollama_url = args.ollama_url
        if args.model:
            config.ollama_model = args.model
        launch_ui(config, args.host, args.port)


if __name__ == "__main__":
    main()
