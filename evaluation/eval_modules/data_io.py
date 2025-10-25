from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from typing import List, Dict, Tuple
import csv, random

from src.disambiguation import (
    load_fst_parser,
    tokenize,
    fst_parse_sentence,
    ojibwe_sentence_to_cg3_format,
    PUNCTUATIONS,
    PRESERVE_TOKEN,
)

# OPDRow model

@dataclass(frozen=True)
class OPDRow:
    Ojibwe: str
    English: str
    Speaker: str = ""
    Link: str = ""

# ---------------- I/O ----------------

def read_opd_tsv(tsv_path: Path) -> List[OPDRow]:
    rows: List[OPDRow] = []
    with open(tsv_path, newline="", encoding="utf-8") as f:
        r = csv.reader(f, delimiter="\t")
        header = next(r, None)
        header_is_names = header and all(h.lower() in ("ojibwe","english","speaker","link") for h in header)

        def to_row(cells: List[str]) -> OPDRow:
            c = (cells + ["", "", "", ""])[:4]
            return OPDRow(Ojibwe=c[0].strip(), English=c[1].strip(),
                          Speaker=c[2].strip(), Link=c[3].strip())

        if header and not header_is_names:
            rows.append(to_row(header))

        for line in r:
            if not line or all(not x.strip() for x in line):
                continue
            rows.append(to_row(line))
    return rows


def write_tsv(rows: List[OPDRow], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, delimiter="\t")
        w.writerow(["sent_id", "Ojibwe", "English", "Speaker", "Link"])
        for i, r in enumerate(rows, 1):
            w.writerow([i, r.Ojibwe, r.English, r.Speaker, r.Link])


def write_cg3(rows: List[OPDRow], fst, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        for i, r in enumerate(rows, 1):
            cg3 = ojibwe_sentence_to_cg3_format(r.Ojibwe, fst)
            f.write(f"# sent_id = {i}\n# text = {r.Ojibwe}\n# eng = {r.English}\n")
            f.write(cg3)

# ---------------- filtering / sampling ----------------

def is_word_token(tok: str) -> bool:
    """Everything other than punctuation and ellipsis is a word token."""
    return tok not in set(PUNCTUATIONS) and tok != PRESERVE_TOKEN


def all_nonpunct_tokens_parsed(oj: str, fst) -> bool:
    """True iff every non-punctuation token has >= FST analysis."""
    toks = tokenize(oj)
    analyses = fst_parse_sentence(toks, fst)
    for item in analyses:
        tok = item["word_form"]
        if not is_word_token(tok):
            continue
        if len(item["fst_analyses"]) == 0:
            return False
    return True


def build_eval_sample(
    opd_rows: List[OPDRow],
    fst_binary: Path,
    sample_size: int = 300,
    seed: int = 421,
) -> List[OPDRow]:
    """Shuffle deterministically and keep rows whose non-punct tokens are all parsed by the FST."""
    fst = load_fst_parser(str(fst_binary))
    rng = random.Random(seed)
    pool = opd_rows[:]  # do not mutate input
    rng.shuffle(pool)

    keep: List[OPDRow] = []
    for r in pool:
        oj = (r.Ojibwe or "").strip()
        if not oj:
            continue
        try:
            if all_nonpunct_tokens_parsed(oj, fst):
                keep.append(r)
                if len(keep) >= sample_size:
                    break
        except Exception:
            # Skip on errors to keep the pipeline robust
            continue
    return keep


def write_eval_artifacts(
    rows: List[OPDRow],
    fst_binary: Path,
    outdir: Path,
    write_100: bool = True,
) -> None:
    """Write TSV + CG3 for the full set, and optionally a 100-sample subset."""
    outdir.mkdir(parents=True, exist_ok=True)
    fst = load_fst_parser(str(fst_binary))

    # full
    write_tsv(rows, outdir / "sample_300.tsv")
    write_cg3(rows, fst, outdir / "sample_300.txt")

    # optional 100
    if write_100:
        subset = rows[:100]
        write_tsv(subset, outdir / "sample_100.tsv")
        write_cg3(subset, fst, outdir / "sample_100.txt")

def parse_conllu(path: Path) -> Dict[str, List[Tuple[str,str]]]:
    """
    Return mapping sent_id -> list of (form, deprel).
    Skips MWT/empty nodes.
    """
    blocks = {}
    cur_id, cur_tokens = None, []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.rstrip("\n")
        if not line:
            if cur_id is not None:
                blocks[cur_id] = cur_tokens
            cur_id, cur_tokens = None, []
            continue
        if line.startswith("# sent_id"):
            cur_id = line.split("=",1)[1].strip()
            continue
        if line.startswith("#"):
            continue
        cols = line.split("\t")
        if not cols or "-" in cols[0] or "." in cols[0]:
            continue
        form, deprel = cols[1], cols[7]
        cur_tokens.append((form, deprel))
    if cur_id and cur_tokens:
        blocks[cur_id] = cur_tokens
    return blocks