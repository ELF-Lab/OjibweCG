from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from typing import List, Dict, Tuple
from conllu import parse
import csv, random

from grammar_modules.disambiguation import tokenize, ojibwe_sentence_to_cg3_format, PUNCTUATIONS, PRESERVE_TOKEN

from grammar_modules.fst import load_fst_parser, fst_parse_sentence

# OPDRow model

@dataclass(frozen=True)
class OPDRow:
    Ojibwe: str
    English: str
    Speaker: str = ""
    Link: str = ""

# ---------------- I/O ----------------

def read_opd_tsv(tsv_path: Path, has_id_col: bool = False) -> List[OPDRow]:
    rows: List[OPDRow] = []
    with open(tsv_path, newline="", encoding="utf-8") as f:
        r = csv.reader(f, delimiter="\t")
        header = next(r, None)

        expected_headers = ("ojibwe", "english", "speaker", "link")
        if has_id_col:
            expected_headers = ("sent_id",) + expected_headers
        
        header_is_names = (header and all(h.strip().lower() in expected_headers for h in header))

        def to_row(cells: List[str]) -> OPDRow:
            if has_id_col:
                cells = cells[1:]

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
    filename: str,
    write_tsv: bool = False,
    write_100: bool = False,
) -> None:
    """CG3 for the full set, and optionally TSV and a 100-sample subset."""
    outdir.mkdir(parents=True, exist_ok=True)
    fst = load_fst_parser(str(fst_binary))

    # cg3
    cg3_name = filename + ".txt"
    write_cg3(rows, fst, outdir / cg3_name)

    # tsv
    if write_tsv:
        tsv_name = filename + ".tsv"
        write_tsv(rows, outdir / tsv_name)

    # optional 100
    if write_100:
        subset = rows[:100]
        write_tsv(subset, outdir / "sample_100.tsv")
        write_cg3(subset, fst, outdir / "sample_100.txt")

def parse_conllu(path: Path) -> Dict[str, dict]:
    sentences = parse(path.read_text(encoding="utf-8"))

    blocks = {}

    for sent in sentences:
        sent_id = sent.metadata.get("sent_id", "")
        text = sent.metadata.get("text", "")

        tokens = []

        for tok in sent:
            if not isinstance(tok["id"], int):
                continue

            tokens.append({
                "id": tok["id"],
                "form": tok["form"],
                "lemma": tok["lemma"],
                "upos": tok["upos"],
                "xpos": tok["xpos"],
                "feats": tok["feats"],
                "head": tok["head"],
                "deprel": tok["deprel"],
            })

        blocks[str(sent_id)] = {
            "text": text,
            "tokens": tokens,
        }

    return blocks