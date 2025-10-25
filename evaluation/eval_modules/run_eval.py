from __future__ import annotations
import argparse, csv, re
from pathlib import Path
from typing import Optional

from src.disambiguation import load_fst_parser, disambiguate

def _norm_join(chunks: list[str]) -> str:
    return "\n\n".join(ch.strip("\n").rstrip() for x in chunks for ch in [x]) + "\n"

def write_sys_from_tsv(
    tsv_path: Path,
    out_path: Path,
    cg3_grammar: Path,
    fst_path: Path,
    text_col: str = "Ojibwe",
    id_col: Optional[str] = "sent_id",
    eng_col: Optional[str] = "eng",
):
    # Load FST once
    fst = load_fst_parser(str(fst_path))

    rows_out = []
    with tsv_path.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f, delimiter="\t")
        header_map = {h.lower(): h for h in (reader.fieldnames or [])}

        def get(row, want):
            if want is None:
                return None
            if want in row:
                return row[want]
            lw = want.lower()
            return row.get(header_map.get(lw, ""), None)

        sid_auto = 1
        for row in reader:
            text = get(row, text_col)
            if not text or not text.strip():
                continue
            sid = get(row, id_col) or str(sid_auto)
            eng = get(row, eng_col)

            raw = disambiguate(
                sentence=text.strip(),
                cg3_grammar_filepath=str(cg3_grammar),
                fst=fst,
                verbose=False,
            )

            # remove any blank lines inside a sent_id block
            body = raw.strip("\n")
            body = re.sub(r"\n{2,}", "\n", body)  # collapse doubles to single
            body += "\n" # block ends with exactly one newline

            headers = [f"# sent_id = {sid}", f"# text = {text.strip()}"]
            if eng:
                headers.append(f"# eng = {eng.strip()}")
            rows_out.append("\n".join(headers + [body]).strip())
            sid_auto += 1

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(_norm_join(rows_out), encoding="utf-8")
    print(f"Wrote {len(rows_out)} sentences to {out_path}")
