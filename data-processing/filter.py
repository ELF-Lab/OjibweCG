import csv
import ast
import random
import string
from pathlib import Path
from typing import Iterable

# Helper functions
# skip punctuation readings
def is_punct(form: str) -> bool:
    return all(c in string.punctuation for c in form)

# check that at least one analysis has every tag in tags
def token_has_tags(analyses: list[str], tags: Iterable[str]) -> bool:
    return all(any(tag in ana for ana in analyses) for tag in tags)

def get_lemma(reading: str) -> str:
    for chunk in reading.strip('"').split('+'):
        chunk = chunk.lower().replace("’", "'")
        if '/' not in chunk and chunk:          
            return chunk
    return ""                                 # fall back


def reading_has_all_tags(reading: str, tags: Iterable[str]) -> bool:
    """Return True iff *every* tag in `tags` occurs in this FST reading."""
    return all(tag in reading for tag in tags)

def extract_examples(
    csv_path: str | Path,
    *,
    limit: int = 50,
    ojibwe_out: str | Path,
    english_out: str | Path,
    using_patterns: bool = False,
    patterns: tuple[str, ...] | None = None,
    require_ambiguity: bool = False,
    ambiguous_sets: tuple[tuple[str, ...], ...] | None = None,
    random_sample: bool = False,
    random_seed: int | None = None,
    index_range: tuple[int, int] | None = None,
) -> None:
    """
    Write up to limit sentence pairs (ojibwe_out / english_out).

    Sampling order:
    1. If index_range=(start, stop) is given, slice the eligible list
       exactly as matches[start:stop].
    2. Else if random_sample is True, take a random sample of size limit
       with random_seed for reproducibility.
    3. Else take a centred slice of length limit.
    """
    # -------------------------------------------------------------- #
    # 0. Collect already-written Ojibwe lines to avoid re-adding them
    # -------------------------------------------------------------- #
    already_written: set[str] = set()
    if Path(ojibwe_out).exists():
        with open(ojibwe_out, encoding="utf-8") as f:
            already_written.update(line.rstrip("\n") for line in f)

    # -------------------------------------------------------------- #
    # 1. Gather all eligible rows
    # -------------------------------------------------------------- #
    matches: list[tuple[str, str]] = []
    seen_this_run: set[str] = set()

    with open(csv_path, newline="", encoding="utf-8") as fin:
        for row in csv.DictReader(fin):
            # ------- parse & validate fst_readings ------------------
            try:
                analyses = ast.literal_eval(row["fst_readings"])
            except Exception:
                continue

            if any((not tok.get("fst_analyses")) and
                   (not is_punct(tok.get("word_form", "")))
                   for tok in analyses):
                continue

            
            if using_patterns:
                if not any(
                    any(any(pat in ana for pat in patterns)
                        for ana in tok["fst_analyses"])
                    for tok in analyses):
                    continue
                
            """
            FOR LEMMAS 

            LEMMA_SET = set(patterns)               

            if using_patterns:
                if not any(
                        any(get_lemma(ana) in LEMMA_SET for ana in tok["fst_analyses"])
                        for tok in analyses):
                    continue
            """
            # ------- ambiguity filter ------------------------------
            if require_ambiguity:
                if not ambiguous_sets:
                    raise ValueError("require_ambiguity=True but ambiguous_sets=None")
                if not any(
                        any(token_has_tags(tok.get("fst_analyses", []), tg)
                            and len(tok.get("fst_analyses", [])) >= 2
                            for tg in ambiguous_sets)
                        for tok in analyses):
                    continue

            oj = row["ojibwe"].strip()
            en = row["english"].strip()

            # --------------- de-duplication ------------------------
            if oj in already_written or oj in seen_this_run:
                continue

            seen_this_run.add(oj)
            matches.append((oj, en))

    if not matches:
        print("No new sentences matched your criteria.")
        return

    # -------------------------------------------------------------- #
    # 2. Decide which subset to keep
    # -------------------------------------------------------------- #
    if index_range:
        start, stop = index_range
        chosen = matches[start:stop]
    elif random_sample:
        rng = random.Random(random_seed)
        rng.shuffle(matches)
        chosen = matches[:limit]
    else:  # middle slice (default)
        mid   = len(matches) // 2
        half  = limit // 2
        start = max(0, mid - half)
        chosen = matches[start:start + limit]

    # -------------------------------------------------------------- #
    # 3. Write parallel output files (append mode)
    # -------------------------------------------------------------- #
    with (
        open(ojibwe_out,  "a", encoding="utf-8") as f_oj,
        open(english_out, "a", encoding="utf-8") as f_en,
    ):
        for oj, en in chosen:
            f_oj.write(oj + "\n")
            f_en.write(en + "\n")

    mode = ("index slice" if index_range else
            "random" if random_sample else
            "middle slice")
    print(f"Wrote {len(chosen)} new sentence pairs ({mode}) "
          f"to {ojibwe_out} / {english_out}")
    