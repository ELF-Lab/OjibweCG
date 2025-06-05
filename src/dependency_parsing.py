from __future__ import annotations
from pathlib import Path
from typing import List, Dict, Tuple, Union, Optional
from pathlib import Path
from typing import Union
import re
import rich
import subprocess, shlex, sys

# ──────────────────────────────────────────────────────────────────
# 0.  CONSTANT TABLES
# ──────────────────────────────────────────────────────────────────
UNIVERSAL_UPOS = {
    "ADJ", "ADP", "ADV", "AUX", "CCONJ", "DET", "INTJ",
    "NOUN", "NUM", "PART", "PRON", "PROPN", "PUNCT",
    "SCONJ", "SYM", "VERB", "X"
}

# CG relation -> UD DEPREL 
REL_MAP = {                           
    "Obj":  "obj",
    "Adv":  "advmod",
    "Subj": "nsubj",
    "punct": "punct",
    "Dem": "det",
    "RelCl": "acl:relcl",
    "Prep": "case",
    "Obl": "obl",
    "discourse": "discourse",
    "AdvMod": "advmod",
    "Neg": "neg",
}
FALLBACK_REL = "dep"                  # when no mapping is known


# ──────────────────────────────────────────────────────────────────
# 1.  INPUT  ->  TOKEN DICTS
# ──────────────────────────────────────────────────────────────────
def parse_cg3_block(cg3_text: str) -> List[Dict]:
    """Return a list of token dictionaries extracted from a disambiguated
    CG-3 block that contains surface lines («<word>») followed by exactly
    one analysis line for each surface form.
    """
    tokens: List[Dict] = []
    current_surface: Optional[str] = None

    def flush_stub() -> None:
        """If a surface was seen but no analysis followed, emit an 'X' token."""
        nonlocal current_surface
        if current_surface is not None:
            tokens.append(dict(
                form=current_surface,
                lemma=current_surface,
                tags=[],
                xpos="_",
                upos="X",          # unknown / foreign / unparsed
                cg_id=None,
                head_cg=None,
                relkind=None,
            ))
            current_surface = None

    for raw in cg3_text.splitlines():
        line = raw.strip()
        if not line:
            continue

        # a) surface form: "<word>"
        if line.startswith("\"<") and line.endswith(">\""):
            # if the previous surface never got an analysis line, flush it now
            flush_stub()

            current_surface = line[2:-2]      # strip " < > "
            if current_surface == ".":        # fast-path punctuation
                tokens.append(dict(
                    form=".", lemma=".", tags=["."], xpos=".",
                    upos="PUNCT", cg_id=None, head_cg=None, relkind="punct"
                ))
                current_surface = None
            continue

        # b) analysis line
        if current_surface:
            m = re.match(r'"([^"]+)"\s+(.+)', line)
            if not m:
                continue                      # malformed -> skip
            lemma, remainder = m.groups()

            fields  = remainder.split()
            cg_id   = head_id = None
            relkind = None

            for f in fields[:]:               # iterate over a copy
                if f.startswith("ID:"):
                    cg_id = int(f.split(":")[1]); fields.remove(f)
                elif f.startswith("R:Dep_"):
                    m2 = re.match(r"R:Dep_([A-Za-z]+)_[A-Za-z]:(\d+)", f)
                    if m2:
                        relkind, head_id = m2.groups()
                        head_id = int(head_id)
                    fields.remove(f)

            upos_tag = next((t for t in fields if t in UNIVERSAL_UPOS), None)
            upos = upos_tag or "X"

            # if particle or interjection, attach to root (easier to be done here)
            if relkind == None and upos in ("INTJ", "PART"):
                relkind = "discourse"

            tokens.append(dict(
                form=current_surface,
                lemma=lemma,
                tags=fields,
                xpos="|".join(fields) or "_",
                upos=upos,
                cg_id=cg_id,
                head_cg=head_id,
                relkind=relkind,
            ))
            current_surface = None

    # end-of-file: flush a trailing stub if the very last word was unanalyzed
    flush_stub()
    return tokens


# ──────────────────────────────────────────────────────────────────
# 2.  TOKENS  ->  CoNLL-U TEXT
# ──────────────────────────────────────────────────────────────────
def tokens_to_conllu(tokens: List[Dict], sent_id: int) -> str:
    """Build a single-sentence CoNLL-U block (ending in a blank line)."""
    # root = first VERB or fallback to token 1
    root_idx = next((i for i, t in enumerate(tokens) if t["upos"] == "VERB"), 0)
    cg2conllu = {t["cg_id"]: i + 1
                 for i, t in enumerate(tokens) if t["cg_id"] is not None}

    rows: List[Tuple[str, ...]] = []
    for i, tok in enumerate(tokens, 1):
        # HEAD column
        head = "0" if i - 1 == root_idx else str(root_idx + 1)
        if tok["head_cg"] in cg2conllu:
            head = str(cg2conllu[tok["head_cg"]])

        # DEPREL column
        deprel = "root" if i - 1 == root_idx else REL_MAP.get(tok["relkind"],
                                                              FALLBACK_REL)

        rows.append((
            str(i), tok["form"], tok["lemma"], tok["upos"], tok["xpos"], "_",
            head, deprel, "_", "_"
        ))

    return (
        f"# sent_id = {sent_id}\n"
        f"# text = {' '.join(t['form'] for t in tokens)}\n" +
        "\n".join("\t".join(r) for r in rows) + "\n\n"
    )


# ──────────────────────────────────────────────────────────────────
# 3.  SAVE and APPEND TO A CORPUS FILE
# ──────────────────────────────────────────────────────────────────
def append_sentence(conllu_text: str,
                    sent_id: int,
                    corpus_path: Union[str, Path] = "ojibwe_treebank.conllu"
                    ) -> Optional[int]:
    """
    Append conllu_text (a single CoNLL-U sentence, incl. trailing blank line)
    to corpus_path, but only if the same natural-language sentence is not
    already present.

    Duplicate detection uses the 1st `# text = …` line of the new block.  
    If a match is found, print a warning and return the existing sent_id.  
    On successful append, return the new sent_id (the one you passed in).

    Parameters
    ----------
    conllu_text : str
        Full CoNLL-U block for one sentence (must end in “\\n\\n”).
    sent_id : int
        The intended sentence-id for the new block (already embedded in
        the metadata line by `tokens_to_conllu`).
    corpus_path : str | Path
        Destination file (created if missing).

    Returns
    -------
    int | None
        Existing id (if duplicate) or sent_id (if appended); `None` if the
        check failed for some reason (e.g. malformed input).
    """
    corpus_path = Path(corpus_path)

    # 1. extract plain-text line of the new sentence 
    m = re.search(r"^#\s*text\s*=\s*(.+)$", conllu_text, flags=re.M)
    if not m:
        print("❌ append_sentence: cannot find '# text =' line in new block")
        return None
    new_text_line = m.group(1).strip()

    # 2. read existing corpus
    existing = corpus_path.read_text(encoding="utf-8") if corpus_path.exists() else ""

    # 3. look for the same '# text =' line 
    # split on blank lines -> individual sentence blocks
    for block in re.split(r"\n\s*\n", existing.strip()):
        mm_text = re.search(r"^#\s*text\s*=\s*(.+)$", block, flags=re.M)
        if mm_text and mm_text.group(1).strip() == new_text_line:
            # duplicate found -> fetch its sent_id for the caller
            mm_id = re.search(r"^#\s*sent_id\s*=\s*(.+)$", block, flags=re.M)
            dup_id = int(mm_id.group(1)) if mm_id else "?"
            print(f"⚠️  sentence already in {corpus_path} corpus with sent_id {dup_id}")
            return dup_id

    # 4. append & save 
    corpus_path.write_text(existing + conllu_text if existing else conllu_text,
                           encoding="utf-8")
    print(f"✓ appended sentence #{sent_id} to {corpus_path.name}")
    return sent_id


# ──────────────────────────────────────────────────────────────────
# 4.  HIGH-LEVEL PIPELINE  (one CG-3 block -> corpus file)
# ──────────────────────────────────────────────────────────────────
def cg3_to_conllu_batch(cg3_text: str,
                        corpus_path: str = "ojibwe_treebank.conllu",
                        lang: str = "ud") -> None:
    """Full conversion + append in one call."""
    # next sentence id = current number of sentences + 1
    sent_id = 1
    if Path(corpus_path).exists():
        existing = Path(corpus_path).read_text(encoding="utf-8")
        sent_id += existing.count("\n\n")

    tokens   = parse_cg3_block(cg3_text)
    conllu   = tokens_to_conllu(tokens, sent_id)
    append_sentence(conllu, sent_id, corpus_path)


# ──────────────────────────────────────────────────────────────────
# 5.  UNIVERSAL-DEPENDENCIES VALIDATOR WRAPPER  
# ──────────────────────────────────────────────────────────────────
def validate_ud(corpus_path: Union[str, Path],
                lang: str = "ud",
                validator: Union[str, Path] = "../ud-tools/validate.py") -> bool:
    """
    Run the UD validator on corpus_path.  Return True if the file is
    clean, otherwise print the validator output and return False.

    Parameters
    ----------
    corpus_path : str | Path
        Path to the CoNLL-U file (one or many sentences).
    lang : str
        UD language code passed to --lang (default "ud").
    validator : str | Path
        Location of validate.py from the UD tools repository.
    """
    corpus_path = Path(corpus_path)
    validator   = Path(validator)

    if not validator.is_file():
        rich.print(f"[bold red]❌ validator not found: {validator}")
        return False
    if not corpus_path.is_file():
        rich.print(f"[bold red]❌ file not found: {corpus_path}")
        return False

    cmd = f"python3 {validator.as_posix()} --lang {lang} {shlex.quote(str(corpus_path))}"
    proc = subprocess.run(cmd, shell=True, capture_output=True, text=True)

    if proc.returncode == 0:
        rich.print(f"[bold green]✓ {corpus_path.name} validated OK")
        return True
    else:
        # the validator writes most messages to STDOUT
        rich.print(f"[bold red]⚠️  validator error(s) in {corpus_path.name}")
        rich.print(proc.stdout or proc.stderr)
        return False


# ──────────────────────────────────────────────────────────────────
# 6.  CONLLU -> DISPLACY VISUALISER    
# ──────────────────────────────────────────────────────────────────
def visualise_conllu(corpus_path: Union[str, Path],
                     sent_no: int = 1,
                     *,
                     compact: bool = True,
                     collapse_punct: bool = True) -> None:
    """
    Load sent_no from a CoNLL-U file and display its dependency graph
    in the notebook / VS Code via spaCy-displaCy.

    Parameters
    ----------
    corpus_path : str | Path
        File containing one or more CoNLL-U sentences.
    sent_no : int
        Zero-based index of the sentence to visualise (default 0 == first).
    compact : bool
        DisplaCy 'compact' option.
    collapse_punct : bool
        DisplaCy 'collapse_punct' option.
    """
    try:
        import pyconll, spacy
        from spacy.tokens import Doc
        from spacy import displacy
    except ImportError as e:
        rich.print("[bold red]❌ spaCy, pyconll or their deps are missing")
        rich.print(str(e))
        return

    corpus_path = Path(corpus_path)
    if not corpus_path.is_file():
        rich.print(f"[bold red]❌ file not found: {corpus_path}")
        return

    # 1. read sentence
    sentences = list(pyconll.load_from_file(corpus_path))
    if not 0 < sent_no <= len(sentences):
        rich.print(f"[bold red]❌ sentence index {sent_no} out of range (1..{len(sentences)})")
        return
    sent = sentences[sent_no-1]

    # 2. spaCy Doc with identical tokenisation
    words  = [tok.form for tok in sent]
    spaces = [True] * (len(words) - 1) + [False]
    nlp    = spacy.blank("xx")
    doc    = Doc(nlp.vocab, words=words, spaces=spaces)

    # 3. copy morpho-syntactic columns
    for i, (sp_tok, ud_tok) in enumerate(zip(doc, sent)):
        head_i        = int(ud_tok.head) - 1 if ud_tok.head != "0" else i
        sp_tok.pos_   = ud_tok.upos or "X"
        sp_tok.tag_   = ud_tok.xpos or "_"
        sp_tok.dep_   = ud_tok.deprel or "dep"
        sp_tok.head   = doc[head_i]

    # 4. render
    rich.print(f"[bold cyan]visualising sentence {sent_no} from {corpus_path.name}")
    displacy.render(doc, style="dep",
                    jupyter=True,
                    options={"compact": compact,
                             "collapse_punct": collapse_punct})
    
# ──────────────────────────────────────────────────────────────────
# 7.  SENTENCE ID -> DELETE FROM CORPUS
# ──────────────────────────────────────────────────────────────────
def delete_sentence(corpus_path: Union[str, Path],
                    sent_id: int | str) -> bool:
    """
    Delete the sentence whose `# sent_id = …` equals sent_id from
    corpus_path, renumber the remaining sentences so that sent_id's
    are again 1..N, and write the file back in-place.

    Parameters
    ----------
    corpus_path : str | Path
        CoNLL-U file containing ≥1 sentences separated by blank lines.
    sent_id : int | str
        The exact value that follows `# sent_id = ` in the metadata
        line.  For your pipeline that means an integer.

    Returns
    -------
    bool
        True on success, False if the sentence wasn’t found.
    """
    corpus_path = Path(corpus_path)
    if not corpus_path.is_file():
        rich.print(f"[bold red]❌ file not found: {corpus_path}")
        return False

    text = corpus_path.read_text(encoding="utf-8").rstrip()
    # split on one or more completely blank lines
    sentences: List[str] = re.split(r"\n\s*\n", text)

    # locate the index of the sentence to delete
    to_delete = None
    for i, block in enumerate(sentences):
        if re.search(rf"^#\s*sent_id\s*=\s*{re.escape(str(sent_id))}\s*$",
                     block, flags=re.M):
            to_delete = i
            break

    if to_delete is None:
        rich.print(f"[bold yellow]⚠️  sent_id {sent_id} not found in {corpus_path.name}")
        return False

    # remove and renumber
    del sentences[to_delete]
    renumbered: List[str] = []
    for new_id, block in enumerate(sentences, 1):
        # replace the first (only) sent_id line in this block
        block = re.sub(r"^#\s*sent_id\s*=\s*.*$",
                       f"# sent_id = {new_id}",
                       block, count=1, flags=re.M)
        renumbered.append(block)

    # join blocks ensuring exactly one blank line between sentences + final NL
    new_text = "\n\n".join(renumbered) + "\n\n"
    corpus_path.write_text(new_text, encoding="utf-8")

    rich.print(f"[bold green]✓ removed sent_id {sent_id} and renumbered the file")
    return True


