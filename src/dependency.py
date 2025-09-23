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
    """
    Parse the output dependency CG3 into a list of dicts with all relevant analyses.
    """
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
            if current_surface in {".", "?", "!"}:
                tokens.append(dict(
                    form=current_surface, lemma=current_surface, tags=[current_surface], xpos=current_surface, upos="PUNCT",
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

            # old-style compatibility (remove if necessary) 
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

            # extract UD relation @label
            for f in list(fields):
                mrel = rel_pat.fullmatch(f)
                if mrel:
                    relkind = mrel.group(1)
                    fields.remove(f)

            # POS
            pos_idx = next((i for i, t in enumerate(fields) if t in UNIVERSAL_UPOS), None)
            upos = fields[pos_idx] if pos_idx is not None else "X"
            xpos = "|".join(fields) if fields else "_"

            # If lemma is "PUNCT" or the surface is actually punctuation, make UPOS=PUNCT and use token as XPOS
            if upos == "X" and (
                lemma.upper() == "PUNCT"
                or (current_surface and current_surface in {",", ";", ":", "—", "-", "(", ")", "…", "«", "»", "“", "”", "'", '"'})
            ):
                upos = "PUNCT"
                xpos = current_surface or lemma

            current_analyses.append(dict(
                form=None, lemma=lemma, tags=fields, xpos=xpos, upos=upos,
                cg_id=cg_id, head_cg=head_id, relkind=relkind
            ))

    # flush last token
    flush_surface()
    return tokens

def tokens_to_conllu(tokens: List[Dict], sent_id: int) -> str:
    """
    Convert a sequence of token dicts into a CoNLL-U block.

    Notes:
      - CG3 may restart token IDs per clause (e.g., after punctuation). We treat these as
        local IDs within clause segments and map heads within each segment only.
      - We still produce a single connected UD tree with exactly one global root:
        the leftmost VERB (fallback: first token).
      - If CG3 marks multiple self-roots, all but the chosen global root are demoted
        to attach under the global root. Labels prefer CG3's @relation, else 'punct'
        for punctuation, else FALLBACK_REL.
    """

    # 1) Detect segments and attach local numbering:
    # increment 'segno' each time G3 numbering restart at 1
    segno = 0
    last_seen_local = None
    for t in tokens:
        cg_id = t.get("cg_id")
        if cg_id is None:
            # PUNCT or no explicit CG3 id: stay in current segment
            t["_seg"] = segno
            t["_local_id"] = None
            continue

        # New segment if numbering restarts at 1 after we have seen ids >= 1.
        if last_seen_local is not None and cg_id == 1 and last_seen_local >= 1:
            segno += 1
        t["_seg"] = segno
        t["_local_id"] = cg_id
        last_seen_local = cg_id

    # 2) Build a (segment, local_id) -> global_row_index map (global rows are 1-based).
    key2idx: Dict[Tuple[int, int], int] = {}
    for i, t in enumerate(tokens, 1):
        if t.get("_local_id") is not None:
            key2idx[(t["_seg"], t["_local_id"])] = i

    # 3) Choose one global root:
    # Prefer leftmost VERB, or fallback to row 1 to keep tree connected.
    root_idx = next((i for i, t in enumerate(tokens, 1) if t.get("upos") == "VERB"), None)
    if root_idx is None:
        root_idx = 1

    # ---- helpers -------------------------------------------------------------
    def is_self_root(t: Dict) -> bool:
        """True if CG3 marks token as its own head within the local numbering."""
        return (t.get("_local_id") is not None) and (t.get("head_cg") == t.get("_local_id"))

    def resolve_head_index(t: Dict) -> Optional[int]:
        """Return global row index for CG3 head within the same segment, if resolvable."""
        head_local = t.get("head_cg")
        if head_local is None:
            return None
        return key2idx.get((t["_seg"], head_local))
    # -------------------------------------------------------------------------

    # 4) Emit CoNLL-U rows (attach by CG3 within segment; enforce single global root).
    rows: List[Tuple[str, ...]] = []
    for i, tok in enumerate(tokens, 1):
        # default head/deprel
        head_col = str(root_idx)          # attach to chosen root by default
        deprel = FALLBACK_REL

        # Prefer CG3 head if it resolves *within the same segment*
        head_idx = resolve_head_index(tok)
        if head_idx is not None:
            head_col = str(head_idx)

        # Single-root policy
        if i == root_idx:
            head_col = "0"
            deprel = "root"
        else:
            # Demote any other self-root to the chosen global root
            if is_self_root(tok):
                head_col = str(root_idx)

            # Label selection order: CG3 @label > PUNCT > fallback
            if tok.get("relkind"):
                deprel = tok["relkind"]
            elif tok.get("upos") == "PUNCT":
                deprel = "punct"

        # normalize punctuation lemma/XPOS consistently
        lemma = tok.get("lemma") or "_"
        xpos  = tok.get("xpos") or "_"
        upos  = tok.get("upos") or "X"
        form  = tok.get("form") or "_"

        if upos == "PUNCT":
            # prefer literal token for both lemma and xpos
            if lemma in {"_", "PUNCT"}:
                lemma = form
            if xpos in {"_", "X"}:
                xpos = form

        rows.append((
            str(i),
            form,
            lemma,               
            upos,
            xpos,                 
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
    """mini wrapper: CG3 text -> CoNLL-U block """
    tokens = parse_cg3_block(cg3_text)
    return tokens_to_conllu(tokens, sent_id)


def split_cg3_sentences(cg3_text: str) -> list[str]:
    """
    Split a CG3 cohort block into segments at sentence-final punctuation cohorts.
    Break when a line's form is exactly "<.>", "<?>", or "<!>".
    The punctuation line stays with the segment it ends.
    Returns segments each ending with a single \n.
    """
    EOS = {".", "?", "!"} # end of sentence punctuation

    segs = []
    cur = []
    last_was_eos = False  

    for ln in cg3_text.splitlines():
        s = ln.strip()

        if s.startswith("\"<") and s.endswith(">\""):
            if last_was_eos and cur:
                segs.append("\n".join(cur).rstrip() + "\n")
                cur = []
                last_was_eos = False  # reset after closing segment

            cur.append(ln)

            # if EOS close on the next surface cohort, so readings stay attached
            token = s[2:-2]
            if token in EOS:
                last_was_eos = True
        else:
            # append everything else to current block
            cur.append(ln)

    # close on end
    if cur:
        segs.append("\n".join(cur).rstrip() + "\n")

    return segs



def parse_dependencies(sentence: str, dependency_grammar: str, disambiguation_grammar: str, fst: Fst, verbose: bool = False):
    """
    Main entry point for dependency parsing. Needs both the disambiguation and the dependency CG3 files to perform a full parse.
    """
     # morphological disambiguation (one block)
    disambiguated = disambiguate(sentence, disambiguation_grammar, fst)

    # split into single-sentence CG3 segments
    segments = split_cg3_sentences(disambiguated)

    # run dep grammar per segment and concatenate
    dep_outputs = []
    for seg in segments:
        out_j = cg3_process_text(seg, dependency_grammar)
        # normalize: each segment ends with exactly one blank line
        dep_outputs.append(out_j.strip() + "\n\n")

    dependencies = "".join(dep_outputs)

    if verbose:
        print(f"# segments after sentence split: {len(segments)}")
        print("Before parsing (disambiguated text):")
        print(disambiguated, end="" if disambiguated.endswith("\n") else "\n")
        print("-" * 20)
        print("After parsing:")
        print(dependencies, end="" if dependencies.endswith("\n") else "\n")


    return dependencies


__all__ = [
    "UNIVERSAL_UPOS",
    "FALLBACK_REL",
    "parse_cg3_block",
    "tokens_to_conllu",
    "cg3_to_conllu_block",
    "split_cg3_sentences",
    "parse_dependencies",
]
