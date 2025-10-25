from __future__ import annotations
from collections import Counter
from typing import Dict, List, Tuple
import os
from tabulate import tabulate  
from fst_runtime.fst import Fst
from src import disambiguation as D
from src.disambiguation import (
    PUNCTUATIONS,
    PRESERVE_TOKEN,
    ojibwe_sentence_to_cg3_format,
    cg3_process_text,
)

# ────────────────────────────────────────────────────────────────
# stats_disambiguation.py — disambiguation statistics on corpus 
# ────────────────────────────────────────────────────────────────


# Tag inventories
VERB_TAGS    = {"VTA", "VAI", "VTI", "VII", "VAIO"}
PRONOUN_TAGS = {"PRONDem", "PRONDub", "PRONIndf", "PRONInter",
                "PRONPret", "PRONSim", "PRONPer"}
NOUN_TAGS    = {"NA", "NI", "NAD", "NID"}
ADVERB_TAGS  = {"ADVConj", "ADVDisc", "ADVDub", "ADVGram", "ADVInter",
                "ADVLoc", "ADVMan", "ADVNeg", "ADVPred", "ADVQnt",
                "ADVTmp", "AVDDeg"}
WORD_TYPES   = ("verb", "pronoun", "noun", "adverb", "other")

# tags that are always ignored when computing morphology only differences
_ALWAYS_DISCARD = VERB_TAGS | NOUN_TAGS | ADVERB_TAGS | PRONOUN_TAGS

_PUNCT_SET = set(PUNCTUATIONS)


# Helper functions
def _is_punct_surface(tok: str) -> bool:
    """True iff the surface token is punctuation/preserve token."""
    return tok in _PUNCT_SET or tok == PRESERVE_TOKEN

def _is_punct_reading_parts(parts: list[str]) -> bool:
    """
    True iff a reading line corresponds to punctuation.
    """
    if not parts:
        return False
    lemma = parts[0].strip('"')
    if lemma == "PUNCT":
        return True
    tags = set(parts[1:])
    return "PUNCT" in tags


def _progress(i: int, n: int, *, width: int = 28, label: str = "") -> None:
    """Simple progress bar"""
    if n <= 0:
        n = 1
    filled = int(width * (i / n))
    bar = "#" * filled + "-" * (width - filled)
    print(f"\r\033[K[{bar}] {i}/{n} {label}", end="", flush=True)
    if i >= n:
        print()

def _major_pos(tags: set[str]) -> str:
    """
    Return a POS category from a tag set.

    Parameters
    ----------
    tags : set[str]
        The tag set of a single reading.

    Returns
    -------
    str
        One of: "pronoun" | "verb" | "noun" | "adverb" | "other".
    """
    if tags & PRONOUN_TAGS: return "pronoun"
    if tags & VERB_TAGS:    return "verb"
    if tags & NOUN_TAGS:    return "noun"
    if tags & ADVERB_TAGS:  return "adverb"
    return "other"


def _strip_common(tagsets: List[set[str]]) -> List[set[str]]:
    """
    Remove tags common to all readings to highlight differences.

    Parameters
    ----------
    tagsets : list[set[str]]
        One set per reading for the same token.

    Returns
    -------
    list[set[str]]
        New tag sets with the intersection removed from each set.
    """
    return tagsets if not tagsets else [ts - set.intersection(*tagsets)
                                        for ts in tagsets]


def _count_readings(block: str) -> Tuple[int, int]:
    """
    Count words and analyses in a CG3 block.

    Parameters
    ----------
    block : str
        A CG3-formatted string (as produced before/after CG3).

    Returns
    -------
    (int, int)
        (number_of_words, number_of_readings)
        Only non-punctuation tokens are counted as words.
    """
    words = analyses = 0
    cur_tok = None
    cur_readings: list[list[str]] = []

    def flush():
        nonlocal words, analyses, cur_tok, cur_readings
        if cur_tok is None:
            return
        if not _is_punct_surface(cur_tok):
            non_punct = [r for r in cur_readings if not _is_punct_reading_parts(r)]
            if non_punct:
                words += 1
                analyses += len(non_punct)
        cur_tok = None
        cur_readings = []

    for ln in block.splitlines():
        if ln.startswith('"<') and ln.endswith('>"'):
            flush()
            cur_tok = ln[2:-2]
            continue
        if ln.startswith("\t"):
            cur_readings.append(ln.strip().split())
            continue
        if not ln.strip():
            flush()

    flush()
    return words, analyses


def _count_by_type(block: str) -> Dict[str, Dict[str, int]]:
    """
    Count words and readings per POS (verb, pronoun, noun, adverb, other).

    Parameters
    ----------
    block : str
        A CG3-formatted string (before or after disambiguation).

    Returns
    -------
    dict
        {pos: {"words": int, "readings": int}, ...} for each POS.

    Notes
    -----
    - Every countable token contributes at least one reading.
    - If all readings are stripped for a token, we file it under "other"
      with one synthetic reading to keep totals consistent.
    """
    counts = {wt: {"words": 0, "readings": 0} for wt in WORD_TYPES}
    cur_tok = None
    cur_readings: list[list[str]] = []

    def flush():
        nonlocal cur_tok, cur_readings
        if cur_tok is None:
            return
        if not _is_punct_surface(cur_tok):
            non_punct = [r for r in cur_readings if not _is_punct_reading_parts(r)]
            if non_punct:
                # determine POS bucket from first non-punct reading
                first_tags = set(non_punct[0][1:])
                pos = _major_pos(first_tags)
                counts[pos]["words"] += 1
                counts[pos]["readings"] += len(non_punct)
        cur_tok = None
        cur_readings = []

    for ln in block.splitlines() + ["## END"]:
        if ln.startswith('"<') and ln.endswith('>"'):
            flush()
            cur_tok = ln[2:-2]
        elif ln.startswith("\t"):
            cur_readings.append(ln.strip().split())

    return counts


def _classify_amb(readings: List[List[str]]) -> str:
    """
    Classify a token's ambiguity type.

    Parameters
    ----------
    readings : list[list[str]]
        Token readings as lists: [lemma, tag1, tag2, ...].

    Returns
    -------
    str
        One of: "lemma" | "preverb" | "pos" | "morpho".
        - "lemma": different lemmas
        - "preverb": differs in preverb sets (PV*)
        - "pos": POS differs
        - "morpho": same lemma/POS, differs in other tags
    """
    lemmas = {r[0].strip('"') for r in readings if r and r[0].startswith('"')}
    if len(lemmas) > 1:
        return "lemma"

    pv_sets = [{t for t in r[1:] if t.startswith("PV")} for r in readings]
    if len({frozenset(s) for s in pv_sets}) > 1:
        return "preverb"

    pos_set = {_major_pos(set(r[1:])) for r in readings}
    if len(pos_set) > 1:
        return "pos"

    return "morpho"


def _ambiguity(block: str, total_words: int,
               top_n: int = 50) -> Dict[str, object]:
    """
    Compute ambiguity overview, top tokens, and patterns for a CG3 block.

    Parameters
    ----------
    block : str
        CG3-formatted text (before or after).
    total_words : int
        Number of countable tokens in the block.
    top_n : int, optional
        Max number of “top ambiguous tokens” to return (default 50).

    Returns
    -------
    dict w/ "overview", "top tokens", and "patterns"
    """
    kinds, tok_counter = Counter(), Counter()
    patterns = {"lemma": {}, "preverb": {}, "morpho": {}, "pos": {}}
    token = None
    readings: list[list[str]] = []

    def flush_token():
        nonlocal token, readings
        if token is None or _is_punct_surface(token):
            token, readings = None, []
            return
        non_punct = [r for r in readings if not _is_punct_reading_parts(r)]
        if token and len(non_punct) > 1:
            k = _classify_amb(non_punct)
            pos_bucket = _major_pos(set(non_punct[0][1:]))
            kinds[k] += 1
            tok_counter[token] += 1

            if k == "pos":
                key = "+".join(sorted({_major_pos(set(r[1:])) for r in non_punct}))
                store = patterns["pos"]
            elif k == "preverb":
                pv_sets = [{t for t in r[1:] if t.startswith("PV")} for r in non_punct]
                diff = _strip_common(pv_sets)
                key = " vs ".join(sorted(",".join(sorted(d)) if d else "{}" for d in diff))
                store = patterns["preverb"].setdefault(pos_bucket, {})
            elif k == "lemma":
                key = " vs ".join(sorted({r[0].strip('"') for r in non_punct}))
                store = patterns["lemma"].setdefault(pos_bucket, {})
            else:  # morpho
                sig_sets = [{t for t in r[1:]
                             if not t.startswith("PV") and t not in _ALWAYS_DISCARD}
                            for r in non_punct]
                diff = _strip_common(sig_sets)
                key = " | ".join(sorted(",".join(sorted(d)) if d else "{}" for d in diff))
                store = patterns["morpho"].setdefault(pos_bucket, {})

            info = store.setdefault(key, {"count": 0, "tokens": Counter()})
            info["count"] += 1
            info["tokens"][token] += 1

        token, readings = None, []

    for ln in block.splitlines() + ["## END"]:
        if ln.startswith('"<') and ln.endswith('>"'):
            flush_token()
            token = ln[2:-2]
        elif ln.startswith("\t"):
            parts = ln.strip().split()
            if not _is_punct_reading_parts(parts):
                readings.append(parts)
    
    flush_token()

    total = sum(kinds.values())
    overview = {"total_ambiguous_tokens": total,
        "pct_tokens_ambiguous": total / total_words if total_words else 0.0,
        **{t: kinds[t] for t in ("lemma", "preverb", "pos", "morpho")},}

    return {"overview": overview,
        "top_tokens": tok_counter.most_common(top_n),
        "patterns": patterns,}


def _table_dict(stats: dict) -> Dict[str, str]:
    """
    render numeric tables (summary, by_type, ambiguity overvieww)

    Parameters
    ----------
    stats : dict
        Stats dict from disambiguate_with_stats.

    Returns
    -------
    dict[str, str]
        {"summary": str, "by_type": str, "amb_ov": str, "amb_top": str}
        Each value is a text table ready to print.
    """
    summary = tabulate(
        [["total words",        stats["total_words"]],
         ["readings before",    stats["total_readings_before"]],
         ["readings after",     stats["total_readings_after"]],
         ["analyses removed",   stats["analyses_removed"]],
         ["ambiguity removed",  f'{stats["ambiguity_removed"]:.3f}'],
         ["ambiguous before",   f'{stats["ambiguous_before"]:.3f}'],
         ["ambiguous after",    f'{stats["ambiguous_after"]:.3f}']],
        tablefmt="github")

    by_type = tabulate(
        [[wt,
          d["words_before"], d["words_after"],
          d["readings_before"], d["readings_after"],
          d["analyses_removed"],
          f'{d["avg_before"]:.2f}', f'{d["avg_after"]:.2f}']
         for wt, d in stats["by_type"].items()],
        headers=["type",
                 "words b", "words a",
                 "readings b", "readings a",
                 "removed", "avg b", "avg a"],
        tablefmt="github")

    ov = stats["ambiguity"]["overview"]  # AFTER disambiguation
    amb_ov = tabulate(
        [["lemma amb.",  ov["lemma"]],
         ["preverb amb.",ov["preverb"]],
         ["POS amb.",    ov["pos"]],
         ["morpho amb.", ov["morpho"]]],
        tablefmt="github")

    amb_top = tabulate(stats["ambiguity"]["top_tokens"],
                       headers=["top tokens", "count"], tablefmt="github")

    return {"summary": summary, "by_type": by_type,
            "amb_ov": amb_ov, "amb_top": amb_top}


def _pattern_table(pat_dict: Dict[str, dict], top: int = 200) -> str:
    """
    Render a nested pattern dictionary into a printable table.

    Parameters
    ----------
    pat_dict : dict
        One of stats["ambiguity"]["patterns"][...].
    top : int, optional
        Maximum number of rows to show (default 200).

    Returns
    -------
    str
        A text table (GitHub-style) or empty string if no rows.
    """
    # If POS nested structure, include POS in the table
    if pat_dict and isinstance(next(iter(pat_dict.values())), dict) \
       and "count" not in next(iter(pat_dict.values())).keys():
        rows = []
        for pos, sub in pat_dict.items():
            for k, info in sub.items():
                rows.append([pos, k, info["count"],
                             ", ".join(t for t,_ in info["tokens"].most_common(3))])
        hdr = ["POS", "pattern", "tokens", "examples ≤3"]
    else:
        rows = [[k, info["count"],
                 ", ".join(t for t,_ in info["tokens"].most_common(3))]
                for k, info in pat_dict.items()]
        hdr = ["pattern", "tokens", "examples ≤3"]

    rows = sorted(rows, key=lambda r: r[2 if hdr[0]=="POS" else 1], reverse=True)[:top]
    return tabulate(rows, headers=hdr, tablefmt="github") if rows else ""


def format_stats_report(stats: dict) -> str:
    """
    Build a multi-section, human-readable stats report.

    Parameters
    ----------
    stats : dict
        Stats dict from disambiguate_with_stats.

    Returns
    -------
    str
        A printable string that includes:
        - overall summary,
        - per-type counts,
        - ambiguity overview and top tokens,
        - pattern sections (POS, lemma, preverb, morphology).
    """
    tbl = _table_dict(stats)
    pat = stats["ambiguity"]["patterns"]
    sections = [
        tbl["summary"], tbl["by_type"], tbl["amb_ov"], tbl["amb_top"],
        "# POS-level patterns",      _pattern_table(pat["pos"]),
        "# Lemma patterns",          _pattern_table(pat["lemma"]),
        "# Preverb patterns",        _pattern_table(pat["preverb"]),
        "# Morphological patterns",  _pattern_table(pat["morpho"]),
    ]
    return "\n\n".join(s for s in sections if s)


# ------------------------------- Public API ----------------------------------

def disambiguate_with_stats(
    text_path: str,
    grammar: str,
    fst: Fst,
    *,
    verbose: bool = False,
    top_n: int = 50,
) -> tuple[str, Dict]:
    """
    Disambiguate text and compute statistics.

    Parameters
    ----------
    text_path : str
        Path to Ojibwe text to analyze.
    grammar : str
        Path to a CG3 disambiguation grammar (.cg3).
    fst : Fst
        Loaded FST instance used to produce readings.
    verbose : bool, optional
        If True, print a formatted stats report (default False).
    top_n : int, optional
        Number of “top ambihuous tokens” to keep (default 50).

    Returns
    -------
    (str, dict)
        (after_block, stats) where:
        - after_block: CG3-formatted string after disambiguation.
        - stats: dictionary summarizing counts, ratios, and patterns.
    """
    # check path
    if not (os.path.exists(text_path) and os.path.isfile(text_path)):
        raise FileNotFoundError(f"Text file not found: {text_path}")

    # progress bar functionality, split into stages
    total_stages = 4
    stage = 1
    _progress(stage, total_stages, label="reading file...")
    with open(text_path, "r", encoding="utf-8") as f:
        text = f.read()

    stage = 2
    _progress(stage, total_stages, label="fst to cg3 conversion (almost all running time is spent here!)")
    before = ojibwe_sentence_to_cg3_format(text, fst=fst)


    stage = 3
    _progress(stage, total_stages, label="processing text with cg3")
    after = cg3_process_text(before, grammar)

    stage = 4
    _progress(stage, total_stages, label="All done!")

    w_b, a_b = _count_readings(before)
    type_b   = _count_by_type(before)
    amb_before = _ambiguity(before, w_b, top_n=top_n)

    w_a, a_a = _count_readings(after)
    type_a   = _count_by_type(after)
    amb_after = _ambiguity(after, w_a, top_n=top_n)

    removed = a_b - a_a
    amb_before_cnt = amb_before["overview"]["total_ambiguous_tokens"]
    amb_after_cnt  = amb_after["overview"]["total_ambiguous_tokens"]
    ambiguity_removed = ((amb_before_cnt - amb_after_cnt) / amb_before_cnt
                         if amb_before_cnt else 0.0)

    stats = {
        "total_words": w_a,
        "total_readings_before": a_b,
        "total_readings_after": a_a,
        "analyses_removed": removed,
        "ambiguity_removed": ambiguity_removed,
        "ambiguous_before": amb_before["overview"]["pct_tokens_ambiguous"],
        "ambiguous_after":  amb_after["overview"]["pct_tokens_ambiguous"],
        "by_type": {},
        "ambiguity": amb_after,          # detailed patterns AFTER disambig
        "ambiguity_before": amb_before,  # kept for reference
    }

    for wt in WORD_TYPES:
        wb, rb = type_b[wt]["words"], type_b[wt]["readings"]
        wa, ra = type_a[wt]["words"], type_a[wt]["readings"]
        stats["by_type"][wt] = {
            "words_before":    wb,
            "words_after":     wa,
            "readings_before": rb,
            "readings_after":  ra,
            "analyses_removed": rb - ra,
            "avg_before": (rb / wb) if wb else 0.0,
            "avg_after":  (ra / wa) if wa else 0.0,
        }

    if verbose:
        print(format_stats_report(stats))

    return after, stats
