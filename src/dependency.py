from __future__ import annotations
from fst_runtime.fst import Fst
from typing import List, Dict, Tuple, Optional
from src.disambiguation import disambiguate, cg3_process_text
import re

# ────────────────────────────────────────────────────────────────
# dependency.py — parse CG3 output and build CoNLL-U rows
# ────────────────────────────────────────────────────────────────

UNIVERSAL_UPOS = {
    "ADJ", "ADP", "ADV", "AUX", "CCONJ", "DET", "INTJ",
    "NOUN", "NUM", "PART", "PRON", "PROPN", "PUNCT",
    "SCONJ", "SYM", "VERB", "X"
}

FALLBACK_REL = "dep"


def parse_cg3_block(cg3_text: str) -> List[Dict]:
    tokens: List[Dict] = []

    current_surface: Optional[str] = None
    current_analyses: list[Dict] = []

    rel_pat = re.compile(r"@([a-z][a-z0-9_:.-]*)$")

    def choose_best(analyses: list[Dict]) -> Dict:
        # 1) prefer one with UD relation
        with_rel = [a for a in analyses if a.get("relkind")]
        if with_rel:
            return with_rel[0]
        # 2) then one with explicit head id
        with_head = [a for a in analyses if a.get("head_cg") is not None]
        if with_head:
            return with_head[0]
        # 3) then one with a known UPOS
        with_pos = [a for a in analyses if a.get("upos") in UNIVERSAL_UPOS]
        if with_pos:
            return with_pos[0]
        # 4) otherwise first
        return analyses[0]

    def flush_surface():
        nonlocal current_surface, current_analyses
        if current_surface is None:
            current_analyses = []
            return
        if not current_analyses:
            tokens.append(dict(
                form=current_surface, lemma=current_surface, tags=[],
                xpos="_", upos="X", cg_id=None, head_cg=None, relkind=None
            ))
        else:
            best = choose_best(current_analyses)
            best["form"] = current_surface
            tokens.append(best)
        current_surface = None
        current_analyses = []

    for raw in cg3_text.splitlines():
        line = raw.strip()
        if not line:
            continue

        # Surface line starts a new token
        if line.startswith("\"<") and line.endswith(">\""):
            flush_surface()
            current_surface = line[2:-2]
            if current_surface == ".":
                tokens.append(dict(
                    form=".", lemma=".", tags=["."], xpos=".", upos="PUNCT",
                    cg_id=None, head_cg=None, relkind="punct"
                ))
                current_surface = None
            continue

        # Analysis line(s): collect all for this surface
        if current_surface:
            m = re.match(r'"([^"]+)"\s+(.+)', line)
            if not m:
                continue
            lemma, remainder = m.groups()
            fields = remainder.split()

            # extract ids
            cg_id = head_id = None
            for f in list(fields):
                m_id = re.fullmatch(r"#(\d+)->(\d+)", f)
                if m_id:
                    cg_id = int(m_id.group(1))
                    head_id = int(m_id.group(2))
                    fields.remove(f)

            # old-style compat
            relkind = None
            for f in list(fields):
                if f.startswith("ID:"):
                    try:
                        cg_id = int(f.split(":", 1)[1])
                    except ValueError:
                        pass
                    fields.remove(f)
                elif f.startswith("R:Dep_"):
                    # e.g., R:Dep_obj_A:2
                    m2 = re.match(r"R:Dep_([A-Za-z:._-]+)_[A-Za-z]:(\d+)", f)
                    if m2:
                        relkind = m2.group(1).lower()
                        if head_id is None:
                            head_id = int(m2.group(2))
                        fields.remove(f)

            # strip bookkeeping
            fields = [f for f in fields if not f.startswith(("ADD:", "SELECT:", "SETPARENT:"))]

            # NEW: extract UD relation @label
            for f in list(fields):
                mrel = rel_pat.fullmatch(f)
                if mrel:
                    relkind = mrel.group(1)
                    fields.remove(f)

            # POS
            pos_idx = next((i for i, t in enumerate(fields) if t in UNIVERSAL_UPOS), None)
            upos = fields[pos_idx] if pos_idx is not None else "X"
            xpos = "|".join(fields) if fields else "_"

            current_analyses.append(dict(
                form=None, lemma=lemma, tags=fields, xpos=xpos, upos=upos,
                cg_id=cg_id, head_cg=head_id, relkind=relkind
            ))

    # flush last token
    flush_surface()
    return tokens


def tokens_to_conllu(tokens: List[Dict], sent_id: int) -> str:
    # Map CG ids -> 1-based indices
    cg2conllu = {t.get("cg_id"): i + 1 for i, t in enumerate(tokens) if t.get("cg_id") is not None}

    # Helpers
    def has_self_root(t: Dict) -> bool:
        return (t.get("cg_id") is not None) and (t.get("head_cg") == t.get("cg_id"))

    def head_points_to_token(t: Dict) -> bool:
        return t.get("head_cg") in cg2conllu and t.get("head_cg") != t.get("cg_id")

    # 1) leftmost explicit self-root
    root_idx = next((i for i, t in enumerate(tokens) if has_self_root(t)), None)

    # 2) leftmost VERB whose head doesn't point to another token (i.e., not “connected”)
    if root_idx is None:
        root_idx = next((i for i, t in enumerate(tokens)
                         if t.get("upos") == "VERB" and not head_points_to_token(t)), None)

    # 3) leftmost VERB
    if root_idx is None:
        root_idx = next((i for i, t in enumerate(tokens) if t.get("upos") == "VERB"), None)

    # 4) fallback to first token
    if root_idx is None:
        root_idx = 0

    root_conllu_id = root_idx + 1

    rows: List[Tuple[str, ...]] = []
    for i, tok in enumerate(tokens, 1):
        # Default: attach to chosen root
        head_col = str(root_conllu_id)
        deprel = FALLBACK_REL

        # Resolve CG head if it points to some token
        if tok.get("head_cg") in cg2conllu:
            head_col = str(cg2conllu[tok["head_cg"]])

        # Demote any *other* self-roots by overriding head to the true root
        if i != root_conllu_id and has_self_root(tok):
            head_col = str(root_conllu_id)

        # Set labels
        if i == root_conllu_id:
            head_col = "0"
            deprel = "root"
        else:
            if tok.get("relkind"):
                deprel = tok["relkind"]
            elif tok.get("upos") == "PUNCT":
                deprel = "punct"
            # else keep FALLBACK_REL

        rows.append((
            str(i),
            tok.get("form") or "_",
            tok.get("lemma") or "_",
            tok.get("upos") or "X",
            tok.get("xpos") or "_",
            "_",
            head_col,
            deprel,
            "_",
            "_"
        ))

    text_line = " ".join(t.get("form") or "_" for t in tokens)
    return (
        f"# sent_id = {sent_id}\n"
        f"# text = {text_line}\n" +
        "\n".join("\t".join(r) for r in rows) + "\n\n"
    )


def cg3_to_conllu_block(cg3_text: str, sent_id: int) -> str:
    """Minimal wrapper: CG3 text → CoNLL-U block (no file I/O)."""
    tokens = parse_cg3_block(cg3_text)
    return tokens_to_conllu(tokens, sent_id)


def parse_dependencies(sentence: str, dependency_grammar: str, disambiguation_grammar: str, fst: Fst, verbose: bool = False):
    """
    Main entry point for dependency parsing. Needs both the disambiguation and the dependency CG3 files to perform a full parse.
    """
    # First do morphological disambiguation
    disambiguated = disambiguate(sentence, disambiguation_grammar, fst)

    dependencies = cg3_process_text(disambiguated, dependency_grammar)
    if verbose:
        print("Before parsing (disambiguated text):")
        print(disambiguated)
        print("-"*20)
        print("After parsing:")
        print(dependencies)

    # Then do dependency parsing
    return dependencies


__all__ = [
    "UNIVERSAL_UPOS",
    "FALLBACK_REL",
    "parse_cg3_block",
    "tokens_to_conllu",
    "cg3_to_conllu_block",
    "parse_dependencies",
]
