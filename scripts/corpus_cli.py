from __future__ import annotations
import argparse
from pathlib import Path
from src.treebank_modules.corpus import (
    append_sentence, cg3_to_conllu_batch, validate_ud,
    delete_sentence
)

def main():
    p = argparse.ArgumentParser(prog="corpus", description="Ojibwe CoNLL-U corpus tools")
    sub = p.add_subparsers(dest="cmd", required=True)

    # 1) Add/convert
    p_add = sub.add_parser("add", help="Convert CG3 text and append as a new sentence")
    p_add.add_argument("--cg3-file", required=True, help="Path to CG3 output text to convert")
    p_add.add_argument("--corpus", default="data/results/ojibwe_treebank.conllu")
    p_add.add_argument("--lang", default="ud", help="UD language code for validator")
    p_add.add_argument("--validator", default="third_party/ud-tools/validate.py")
    p_add.add_argument("--no-validate", action="store_true",
                       help="Skip UD validation after appending")

    # 2) Validate existing file
    p_val = sub.add_parser("validate", help="Run UD validate.py on a .conllu file")
    p_val.add_argument("--corpus", required=True)
    p_val.add_argument("--lang", default="ud")
    p_val.add_argument("--validator", default="third_party/ud-tools/validate.py")


    # 3) Delete a sentence by sent_id
    p_del = sub.add_parser("delete", help="Delete a sentence by sent_id and renumber")
    p_del.add_argument("--corpus", required=True)
    p_del.add_argument("--id", required=True)

    args = p.parse_args()

    if args.cmd == "add":
        cg3_text = Path(args.cg3_file).read_text(encoding="utf-8")
        # Convert & append (your function auto-assigns sent_id and appends)
        cg3_to_conllu_batch(cg3_text, corpus_path=args.corpus, lang=args.lang)
        # Validate (default ON)
        if not args.no_validate:
            ok = validate_ud(args.corpus, lang=args.lang, validator=args.validator)
            if not ok:
                raise SystemExit(1)

    elif args.cmd == "validate":
        ok = validate_ud(args.corpus, lang=args.lang, validator=args.validator)
        if not ok:
            raise SystemExit(1)

    elif args.cmd == "delete":
        if not delete_sentence(args.corpus, args.id):
            raise SystemExit(1)

if __name__ == "__main__":
    main()
