#!/usr/bin/env python3
import sys, argparse, subprocess, tempfile, pathlib
from src import disambiguation as D
from fst_runtime.fst import Fst
from src.dependency import parse_cg3_block, tokens_to_conllu

def main():
    ap = argparse.ArgumentParser(description="Run FST → CG3 disamb → CG3 dep → CoNLL-U")
    ap.add_argument("--fst-bin", required=True)
    ap.add_argument("--dep-grammar", required=True)
    ap.add_argument("--input", required=True, help="Raw text; one sentence per line recommended.")
    ap.add_argument("--output", required=True, help="Output .conllu file")
    ap.add_argument("--cg3-name", default="vislcg3")
    args = ap.parse_args()

    D.CG3_NAME = args.cg3_name
    if not D.is_cg3_available():
        ap.error(f"CG3 not found as '{args.cg3_name}'.")

    fst: Fst = D.load_fst_parser(args.fst_bin)
    text = pathlib.Path(args.input).read_text(encoding="utf-8")
    sentences = [s for s in text.splitlines() if s.strip()]

    conllu_chunks = []
    sent_id = 1
    for s in sentences:
        cg3_in = D.ojibwe_sentence_to_cg3_format(s, fst=fst)
        dep = D.cg3_process_text(cg3_in, args.dep_grammar)
        toks = parse_cg3_block(dep)
        conllu_chunks.append(tokens_to_conllu(toks, sent_id))
        sent_id += 1

    pathlib.Path(args.output).write_text("".join(conllu_chunks), encoding="utf-8")

if __name__ == "__main__":
    main()
