import csv
import ast
import string
from pathlib import Path
from typing import Iterable

# Helper functions
# skip punctuation readings
def is_punct(form: str) -> bool:
    return all(c in string.punctuation for c in form)

# check that all tags are contained in at least one analysis line
def token_has_tags(analyses: list[str], tags: Iterable[str]) -> bool:
    return all(any(tag in ana for ana in analyses) for tag in tags)

# get the lemma from an analysis  
def get_lemma(reading: str) -> str:
    for chunk in reading.strip('"').split('+'):
        chunk = chunk.lower().replace("’", "'")
        if '/' not in chunk and chunk:          
            return chunk
    return "" # fall back

# not used right now
def reading_has_all_tags(reading: str, tags: Iterable[str]) -> bool:
    """Return True iff every tag in tags occurs in this FST reading."""
    return all(tag in reading for tag in tags)


def extract_examples(
    tsv_path: str | Path,
    *,
    limit: int = 50,
    ojibwe_out: str | Path,
    english_out: str | Path,
    require_tags: bool = False,
    tags: tuple[str, ...] | None = None,
    require_ambiguity: bool = False,
    ambiguous_sets: tuple[tuple[str, ...], ...] | None = None,
    lemma_ambiguity: bool = False,
) -> None:
    """
    Write parallel oj_ and en_ files that contain required tags and/or required ambiguity. 
    "readings" are the wordform + analyses (FST outputs). "analyses" are just the FST outputs. 
    """
    # check written lines to avoid rewrite later
    already_written: set[str] = set()
    if Path(ojibwe_out).exists():
        with open(ojibwe_out, encoding="utf-8") as f:
            already_written.update(line.rstrip("\n") for line in f)

    # collect matching rows
    matches: list[tuple[str, str]] = []
    seen_this_run: set[str] = set()

    with open(tsv_path, newline="", encoding="utf-8") as fin:
        reader = csv.DictReader(fin, delimiter="\t")
        lemma_pairs = set()
        for row in reader:
            # get and validate fst readings 
            try:
                readings = ast.literal_eval(row["fst_readings"])
            except Exception:
                continue

            # Skip examples where there are unparsed tokens (comment out if not needed)
            if any((not tok.get("fst_analyses")) and
                   (not is_punct(tok.get("word_form", "")))
                   for tok in readings):
                continue

            # check that at least one word in the fst_readings contains the tag we're looking for
            if require_tags:
                if not any(
                    any(any(tag in ana for tag in tags)
                        for ana in tok["fst_analyses"])
                    for tok in readings):
                    continue
                
            # need the analyses of one token to have all the tags in ambiguous_sets
            # doesn't discriminate between tags being part of the same analysis line
            if require_ambiguity:
                if not ambiguous_sets:
                    raise ValueError("require_ambiguity=True but ambiguous_sets=None")
                if not any(
                        any(token_has_tags(tok.get("fst_analyses", []), tg)
                            and len(tok.get("fst_analyses", [])) >= 2
                            for tg in ambiguous_sets)
                        for tok in readings):
                    continue

            # special subcase of ambiguity where only the lemma is ambiguous, other tags are equal
            ambiguous_lemmas = []
            found_lemma_only = False
            if lemma_ambiguity:
                for tok in readings:
                    # check that lemma is ambiguous and other readings are the same
                    lemmas = []
                    no_lemma_analyses = []
                    for ana in tok["fst_analyses"]:
                        lemma = get_lemma(ana)
                        lemmas.append(lemma)
                        no_lemma_analyses.append(ana.replace(lemma, "", 1))

                    unique_lemmas = sorted(set(lemmas))
                    unique_analyses = list(set(no_lemma_analyses))

                    if len(unique_lemmas) > 1 and len(unique_analyses) == 1:
                        pair = tuple(unique_lemmas)
                        if pair not in lemma_pairs:
                            lemma_pairs.add(pair)
                        found_lemma_only = True

                if not found_lemma_only:
                    continue
                    
            

            oj = row["ojibwe"].strip()
            en = row["english"].strip()

            # de-duplicate
            if oj in already_written or oj in seen_this_run:
                continue

            seen_this_run.add(oj)
            matches.append((oj, en))

            # if at limit stop collecting examples
            if len(matches) >= limit:
                break

    if lemma_ambiguity:
        print(sorted(lemma_pairs))

    if not matches:
        print("No new sentences matched the criteria.")
        return

    # write output files
    with (
        open(ojibwe_out,  "a", encoding="utf-8") as f_oj,
        open(english_out, "a", encoding="utf-8") as f_en,
    ):
        for oj, en in matches:
            f_oj.write(oj + "\n")
            f_en.write(en + "\n")
    print(f"Wrote {len(matches)} new sentence pairs "
          f"to {ojibwe_out} / {english_out}")
    