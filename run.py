"""Non-interactive CLI for TradingAgents.

A flat parameter-driven entrypoint that bypasses the interactive prompts in
``cli/main.py``. Lives at the repo root as a new file (rather than editing
``cli/main.py``) so upstream merges stay conflict-free.

The interactive CLI is still the right tool for exploration; this script is
for scripted runs, schedulers, and shell aliases.

Example
-------
    uv run python run.py \\
        --ticker QQQ --date 2026-04-29 \\
        --provider claude_bridge \\
        --quick-model haiku --deep-model opus \\
        --analysts all

Reports land in ``./reports/<TICKER>_<YYYYMMDD>_<HHMMSS>/`` (override the
parent with ``--report-dir``), using the same layered structure the
interactive CLI produces (``1_analysts/``, ``2_research/``, ...,
``complete_report.md``). We reuse ``cli.main.save_report_to_disk`` so the
layout never drifts from the interactive CLI.

The graph itself also writes the full state JSON under
``<results_dir>/<TICKER>/TradingAgentsStrategy_logs/full_states_log_<DATE>.json``
(``results_dir`` defaults to ``~/.tradingagents/logs``).
"""

from __future__ import annotations

import argparse
import datetime as dt
import logging
import sys
from pathlib import Path
from typing import List

from dotenv import load_dotenv

ALL_ANALYSTS = ["market", "social", "news", "fundamentals"]


def parse_analysts(raw: str) -> List[str]:
    if raw.strip().lower() == "all":
        return list(ALL_ANALYSTS)
    items = [a.strip().lower() for a in raw.split(",") if a.strip()]
    unknown = [a for a in items if a not in ALL_ANALYSTS]
    if unknown:
        raise argparse.ArgumentTypeError(
            f"Unknown analysts: {unknown}. Valid: {ALL_ANALYSTS} or 'all'."
        )
    return items


def parse_date(raw: str) -> str:
    """Validate YYYY-MM-DD and return as string (graph expects a string)."""
    try:
        dt.datetime.strptime(raw, "%Y-%m-%d")
    except ValueError as e:
        raise argparse.ArgumentTypeError(f"Date must be YYYY-MM-DD: {e}") from e
    return raw


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="run.py",
        description="Run a TradingAgents analysis non-interactively.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument("--ticker", required=True, help="Stock ticker, e.g. QQQ.")
    p.add_argument(
        "--date",
        type=parse_date,
        default=dt.date.today().isoformat(),
        help="Analysis date (YYYY-MM-DD).",
    )
    p.add_argument(
        "--analysts",
        type=parse_analysts,
        default=list(ALL_ANALYSTS),
        help="Comma-separated subset of {market,social,news,fundamentals} or 'all'.",
    )
    p.add_argument(
        "--provider",
        default="claude_bridge",
        help="LLM provider key (claude_bridge, openai, anthropic, google, ...).",
    )
    p.add_argument(
        "--quick-model",
        default="haiku",
        help="Model id for quick-thinking agents.",
    )
    p.add_argument(
        "--deep-model",
        default="opus",
        help="Model id for deep-thinking agents.",
    )
    p.add_argument(
        "--depth",
        type=int,
        default=1,
        help="Research depth (max debate and risk-discussion rounds).",
    )
    p.add_argument(
        "--language",
        default="English",
        help="Output language for analyst reports and final decision.",
    )
    p.add_argument(
        "--backend-url",
        default=None,
        help="Override base URL for the LLM provider (rarely needed; "
        "claude_bridge uses CLAUDE_BRIDGE_URL or its hardcoded default).",
    )
    p.add_argument(
        "--checkpoint",
        action="store_true",
        help="Enable LangGraph checkpoint/resume.",
    )
    p.add_argument(
        "--clear-checkpoints",
        action="store_true",
        help="Delete saved checkpoints before running.",
    )
    p.add_argument(
        "--report-dir",
        default="reports",
        help="Parent directory for the per-run report folder. The folder name "
        "is <TICKER>_<YYYYMMDD>_<HHMMSS>.",
    )
    p.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress per-step debug output from the graph.",
    )
    return p


def main(argv: List[str] | None = None) -> int:
    load_dotenv()
    load_dotenv(".env.enterprise", override=False)

    args = build_parser().parse_args(argv)

    # Imports deferred until after dotenv so env-driven config is honored.
    from tradingagents.default_config import DEFAULT_CONFIG
    from tradingagents.graph.trading_graph import TradingAgentsGraph
    from cli.main import save_report_to_disk

    if args.clear_checkpoints:
        from tradingagents.graph.checkpointer import clear_all_checkpoints

        n = clear_all_checkpoints(DEFAULT_CONFIG["data_cache_dir"])
        print(f"Cleared {n} checkpoint(s).", file=sys.stderr)

    config = DEFAULT_CONFIG.copy()
    config["llm_provider"] = args.provider.lower()
    config["quick_think_llm"] = args.quick_model
    config["deep_think_llm"] = args.deep_model
    config["max_debate_rounds"] = args.depth
    config["max_risk_discuss_rounds"] = args.depth
    config["output_language"] = args.language
    config["checkpoint_enabled"] = args.checkpoint
    if args.backend_url is not None:
        config["backend_url"] = args.backend_url

    logging.basicConfig(
        level=logging.WARNING if args.quiet else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    graph = TradingAgentsGraph(
        selected_analysts=args.analysts,
        config=config,
        debug=not args.quiet,
    )

    print(
        f"Running analysis: ticker={args.ticker} date={args.date} "
        f"provider={args.provider} quick={args.quick_model} deep={args.deep_model} "
        f"analysts={','.join(args.analysts)} depth={args.depth}",
        file=sys.stderr,
    )

    final_state, decision = graph.propagate(args.ticker, args.date)

    timestamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    report_path = Path(args.report_dir) / f"{args.ticker}_{timestamp}"
    report_file = save_report_to_disk(final_state, args.ticker, report_path)

    print(f"\nReport saved to:  {report_path.resolve()}", file=sys.stderr)
    print(f"Complete report:  {report_file.name}", file=sys.stderr)
    print(f"Full state JSON:  "
          f"{Path(config['results_dir']) / args.ticker / 'TradingAgentsStrategy_logs'}",
          file=sys.stderr)
    print(f"\nFinal decision: {decision}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
