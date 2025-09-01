from __future__ import annotations
import sys
import argparse
from pathlib import Path
from typing import List

from fst_runtime.fst import Fst
from src import disambiguation as D
from src.disambiguation import is_cg3_available, load_fst_parser
from src.disambiguation_stats import disambiguate_with_stats, format_stats_report

def _read_text(path: str | None, *, sent_split: bool) -> str:
    """Return a single string. If sent_split=True, join lines with '\n' (keeps units)."""
    if not path or path == "-":
        raw = sys.stdin.read()
    else:
        raw = Path(path).read_text(encoding="utf-8")
    if sent_split:
        return "\n".join(ln for ln in raw.splitlines() if ln.strip())
    return raw.strip()

def make_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Compute disambiguation stats (FST + CG3).")
    p.add_argument("--fst-bin", required=True, help="Path to FST binary (.att or compiled).")
    p.add_argument("--grammar", required=True, help="CG3 disambiguation grammar (.cg3).")
    p.add_argument("--input", default="-", help="Input text file; '-' = stdin.")
    p.add_argument("--output", help="Write report to this file (Markdown). If omitted, prints to stdout.")
    p.add_argument("--cg3-name", default="vislcg3", help="CG3 binary name/path (default: vislcg3).")
    p.add_argument("--sent-split", action="store_true",
                   help="Treat each input line as one unit (common when text is one sentence per line).")
    p.add_argument("--top", type=int, default=50, help="How many top ambiguous tokens to list (default 50).")
    p.add_argument("--quiet", action="store_true", help="Do not print the report to stdout (still writes --output).")
    return p

def main(argv: List[str] | None = None) -> int:
    args = make_parser().parse_args(argv)

    # Configure CG3 binary and check availability
    D.CG3_NAME = args.cg3_name
    if not is_cg3_available():
        print(f"Error: CG3 not found as '{args.cg3_name}'. Install vislcg3 or pass --cg3-name.", file=sys.stderr)
        return 2

    # Load FST
    fst: Fst = load_fst_parser(args.fst_bin)

    # Read text
    corpus = _read_text(args.input, sent_split=args.sent_split)

    # Run stats
    _after, stats = disambiguate_with_stats(
        text=corpus,
        grammar=args.grammar,
        fst=fst,
        verbose=False,
        top_n=args.top,
    )

    # Render report
    report = format_stats_report(stats)

    # Output
    if args.output:
        out_path = Path(args.output)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(report, encoding="utf-8")
        print(f"Report written to {out_path.resolve()}")
        if not args.quiet:
            print()
            print(report)
    else:
        print(report)

    return 0

if __name__ == "__main__":
    raise SystemExit(main())
