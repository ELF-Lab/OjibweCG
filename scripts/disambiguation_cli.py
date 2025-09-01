#!/usr/bin/env python3
import sys, argparse, pathlib
from fst_runtime.fst import Fst
from src.disambiguation import (
    load_fst_parser, ojibwe_sentence_to_cg3_format,
    cg3_process_text, is_cg3_available
)

def read_text(path: str | None) -> str:
    if not path or path == "-":
        return sys.stdin.read()
    return pathlib.Path(path).read_text(encoding="utf-8")

def main():
    ap = argparse.ArgumentParser(
        description="Disambiguate Ojibwe text using FST + CG3."
    )
    ap.add_argument("--fst-bin", required=True, help="Path to FST binary (.att or compiled).")
    ap.add_argument("--grammar", required=True, help="CG3 grammar file (e.g., grammar/disambiguation.cg3).")
    ap.add_argument("--input", default="-", help="Input text file (raw Ojibwe). Use '-' for stdin.")
    ap.add_argument("--cg3-name", default="vislcg3", help="CG3 binary name (default: vislcg3).")
    ap.add_argument("--sent-split", action="store_true", help="Split on newlines as sentences.")
    args = ap.parse_args()

    # allow override
    from src import disambiguation as D
    D.CG3_NAME = args.cg3_name

    if not is_cg3_available():
        ap.error(f"CG3 not found as '{args.cg3_name}'. Install vislcg3 or pass --cg3-name.")

    fst: Fst = load_fst_parser(args.fst_bin)
    raw = read_text(args.input)

    # Treat each line as one sentence if requested; otherwise as one block
    units = raw.splitlines() if args.sent_split else [raw.strip()]
    outputs = []
    for sent in units:
        if not sent.strip():
            continue
        cg3_in = D.ojibwe_sentence_to_cg3_format(sent, fst=fst)
        out = D.cg3_process_text(cg3_in, cg3_grammar_filepath=args.grammar)
        outputs.append(out.rstrip("\n"))

    sys.stdout.write("\n\n".join(outputs) + ("\n" if outputs else ""))

if __name__ == "__main__":
    main()
