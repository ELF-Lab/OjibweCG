from __future__ import annotations
import argparse
import sys
from pathlib import Path
from typing import Optional, List

from src.booklets import build_disambig_booklet, build_dep_booklet

def make_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="booklets-renderer",
        description="Render HTML booklets for CG3 disambiguation and dependency trees."
    )
    sub = p.add_subparsers(dest="cmd", required=True)

    # disambig
    d = sub.add_parser("build-disambig", help="Build disambiguation before/after booklet")
    d.add_argument("--oj", required=True, type=Path, help="Ojibwe sentences .txt")
    d.add_argument("--en", required=True, type=Path, help="English sentences .txt")
    d.add_argument("--cg3", required=True, type=Path, help="CG3 disambiguation grammar .cg3")
    d.add_argument("--fst", required=True, type=Path, help="FST binary (.att/.fomabin)")
    d.add_argument("--out", required=True, type=Path, help="Output HTML path")
    d.add_argument("--title", required=True, type=str, help="HTML title")

    # dep
    dep = sub.add_parser("build-dep", help="Build dependency SVG booklet")
    dep.add_argument("--treebank", required=True, type=Path, help="CONLL-U file (read or write)")
    dep.add_argument("--oj", required=True, type=Path, help="Ojibwe sentences .txt")
    dep.add_argument("--en", required=True, type=Path, help="English sentences .txt")
    dep.add_argument("--out", required=True, type=Path, help="Output HTML path")
    dep.add_argument("--title", required=True, type=str, help="HTML title")

    dep.add_argument("--reparse", action="store_true",
                     help="Re-run CG3 on Ojibwe lines and regenerate treebank before rendering")
    dep.add_argument("--cg3", type=Path, help="CG3 dependency grammar .cg3 (required if --reparse)")
    dep.add_argument("--fst", type=Path, help="FST binary (.att/.fomabin) (required if --reparse)")

    return p

def main(argv: Optional[List[str]] = None) -> int:
    args = make_parser().parse_args(argv)

    if args.cmd == "build-disambig":
        build_disambig_booklet(
            ojibwe_path=args.oj,
            english_path=args.en,
            cg3_grammar_path=args.cg3,
            fst_path=args.fst,
            out_html_path=args.out,
            html_title=args.title,
        )
        return 0

    if args.cmd == "build-dep":
        build_dep_booklet(
            treebank_path=args.treebank,
            ojibwe_path=args.oj,
            english_path=args.en,
            out_html_path=args.out,
            html_title=args.title,
            reparse_with_cg3=bool(args.reparse),
            cg3_grammar_path=args.cg3,
            fst_path=args.fst,
        )
        return 0

    return 1

if __name__ == "__main__":
    sys.exit(main())
