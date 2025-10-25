from __future__ import annotations
from pathlib import Path
from typing import List, Union, Optional, Tuple
from src.disambiguation import cg3_process_text
from src.dependency import cg3_to_conllu_block, split_cg3_sentences, tokens_to_conllu
import sys
import re
import rich
import subprocess

# ────────────────────────────────────────────────────────────────
# corpus.py — build and query CoNLL-U corpus
# ────────────────────────────────────────────────────────────────


def append_sentence(conllu_text: str,
                    sent_id: int,
                    corpus_path: Union[str, Path] = "ojibwe_treebank.conllu",
                    verbose: bool = True
                    ) -> Optional[int]:
    """Append one CoNLL-U sentence if its # text = is new; return id used.
    Duplicate detection is by exact # text = match.
    """
    corpus_path = Path(corpus_path)
    m = re.search(r"^#\s*text\s*=\s*(.+)$", conllu_text, flags=re.M)
    if not m:
        print("❌ append_sentence: missing '# text ='")
        return None
    new_text_line = m.group(1).strip()

    existing = corpus_path.read_text(encoding="utf-8") if corpus_path.exists() else ""
    for block in re.split(r"\n\s*\n", existing.strip()):
        mm_text = re.search(r"^#\s*text\s*=\s*(.+)$", block, flags=re.M)
        if mm_text and mm_text.group(1).strip() == new_text_line:
            mm_id = re.search(r"^#\s*sent_id\s*=\s*(.+)$", block, flags=re.M)
            dup_id = int(mm_id.group(1)) if mm_id else "?"
            if verbose:
                print(f"⚠️  sentence already in {corpus_path} with sent_id {dup_id}")
            return dup_id

    corpus_path.write_text(existing + conllu_text if existing else conllu_text, encoding="utf-8")
    if verbose:
        print(f"✓ appended sentence #{sent_id} to {corpus_path.name}")
    return sent_id


def cg3_to_conllu_batch(cg3_text: str,
                        corpus_path: Union[str, Path] = "ojibwe_treebank.conllu",
                        lang: str = "ud",
                        verbose: bool = True) -> None:
    """Parse CG3 text -> CoNLL-U, then append to corpus_path.
    Auto-assigns sent_id = (current sentence count + 1).
    """
    p = Path(corpus_path)
    sent_id = 1 + (p.read_text(encoding="utf-8").count("\n\n") if p.exists() else 0)
    conllu = cg3_to_conllu_block(cg3_text, sent_id)
    append_sentence(conllu, sent_id, p, verbose=verbose)
    


def append_parent_block_as_segments(
    *,
    cg3_disamb_block: str,
    dep_grammar_path: Path | str,      
    parent_index: int,              
    oj_text: Optional[str] = None,
    en_text: Optional[str] = None,  
    corpus_path: Path | str = "ojibwe_treebank.conllu",
    verbose: bool = True,
) -> List[Tuple[str, str]]:
    """
    Split the disambiguated CG3 block into sentence segments, run the dependency
    grammar on each segment, convert to CoNLL-U with provenance headers, and append.

    Returns a list of (sent_id, dep_cg3_output) for later display.
    """
    corpus_path = Path(corpus_path)
    existing = corpus_path.read_text(encoding="utf-8") if corpus_path.exists() else ""

    segments = split_cg3_sentences(cg3_disamb_block)
    used: List[Tuple[str, str]] = []
    new_blocks: List[str] = []

    for k, seg in enumerate(segments, 1):
        sent_id = f"g{parent_index}.s{k}"

        # 1) run dep grammar on THIS segment
        dep_cg3 = cg3_process_text(seg, str(dep_grammar_path))
        if not dep_cg3.strip():
            raise RuntimeError(f"Empty dep output for {sent_id}")

        # 2) convert to CoNLL-U
        block = cg3_to_conllu_block(dep_cg3, sent_id)

        # 3) inject provenance headers
        extra = [f"# parent_id = g{parent_index}", f"# seg_index = {k}"]
        # store full EN once (on first segment only)
        if en_text and k == 1:
            extra.append(f"# text_en_full = {en_text.strip()}")
        # store full oj once too
        if oj_text and k == 1:
            extra.append(f"# text_full_parent = {oj_text.strip()}")

        lines = block.splitlines()
        insert_at = 2 if len(lines) >= 2 and lines[0].startswith("# sent_id") and lines[1].startswith("# text") else 0
        block = "\n".join(lines[:insert_at] + extra + lines[insert_at:])
        if not block.endswith("\n"):
            block += "\n"
        if not block.endswith("\n\n"):
            block += "\n"

        new_blocks.append(block)
        used.append((sent_id, dep_cg3))

    if new_blocks:
        corpus_path.write_text(existing + "".join(new_blocks), encoding="utf-8")
        if verbose:
            print(f"✓ appended {len(new_blocks)} segment(s) for parent g{parent_index} → {corpus_path.name}")

    return used




def validate_ud(corpus_path: Union[str, Path],
                lang: str = "ud",
                validator: Union[str, Path] = "../ud-tools/validate.py") -> bool:
    """Run the UD validator; True if clean, else False and print output."""
    corpus_path = Path(corpus_path)
    validator = Path(validator)
    if not validator.is_file():
        rich.print(f"[bold red]❌ validator not found: {validator}")
        return False
    if not corpus_path.is_file():
        rich.print(f"[bold red]❌ file not found: {corpus_path}")
        return False

    cmd = [sys.executable, str(validator), "--lang", lang, str(corpus_path)]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode == 0:
        rich.print(f"[bold green]✓ {corpus_path.name} validated OK")
        return True
    rich.print(f"[bold red]⚠️  validator error(s) in {corpus_path.name}")
    rich.print(proc.stdout or proc.stderr)
    return False


def visualise_conllu(corpus_path: Union[str, Path],
                     sent_no: int = 1,
                     *,
                     compact: bool = True,
                     collapse_punct: bool = True) -> None:
    """Render one sentence from a CoNLL-U file with spaCy displaCy."""
    try:
        import pyconll, spacy
        from spacy import displacy
        from IPython.display import HTML, display
    except ImportError as e:
        rich.print("[bold red]❌ Missing dependency (install pyconll/spacy/IPython)"); 
        rich.print(str(e)); 
        return

    corpus_path = Path(corpus_path)
    if not corpus_path.is_file():
        rich.print(f"[bold red]❌ file not found: {corpus_path}")
        return

    sents = list(pyconll.load_from_file(corpus_path))
    if not 0 < sent_no <= len(sents):
        rich.print(f"[bold red]❌ sentence index {sent_no} out of range (1..{len(sents)})")
        return
    sent = sents[sent_no - 1]

    # Words list (skip punctuation if collapse_punct)
    keep = [i for i, tok in enumerate(sent) if not (collapse_punct and (tok.upos or "").upper() == "PUNCT")]
    idx_map = {old_i: new_i for new_i, old_i in enumerate(keep)}

    words = [{"text": sent[i].form, "tag": (sent[i].upos or "")} for i in keep]

    # Build arcs for dependencies (needs start/end indices and direction)
    arcs = []
    for i_old in keep:
        tok = sent[i_old]
        if tok.head == "0":
            continue  # skip root arc
        head_old = int(tok.head) - 1
        # skip if head got collapsed
        if head_old not in idx_map or i_old not in idx_map:
            continue
        i = idx_map[i_old]
        h = idx_map[head_old]
        start, end = (h, i) if h < i else (i, h)
        direction = "left" if h < i else "right"
        arcs.append({"start": start, "end": end, "label": tok.deprel or "dep", "dir": direction})

    rich.print(f"[bold cyan]visualising sentence {sent_no} from {corpus_path.name}")

    html = displacy.render({"words": words, "arcs": arcs},
                           style="dep", manual=True, jupyter=False,
                           options={"compact": compact})
    display(HTML(html))


def delete_sentence(corpus_path: Union[str, Path],
                    sent_id: int | str) -> bool:
    """Delete sentence with matching `# sent_id =` and renumber remaining."""
    corpus_path = Path(corpus_path)
    if not corpus_path.is_file():
        rich.print(f"[bold red]❌ file not found: {corpus_path}")
        return False

    text = corpus_path.read_text(encoding="utf-8").rstrip()
    sentences: List[str] = re.split(r"\n\s*\n", text)

    to_delete = None
    for i, block in enumerate(sentences):
        if re.search(rf"^#\s*sent_id\s*=\s*{re.escape(str(sent_id))}\s*$", block, flags=re.M):
            to_delete = i
            break
    if to_delete is None:
        rich.print(f"[bold yellow]⚠️  sent_id {sent_id} not found in {corpus_path.name}")
        return False

    del sentences[to_delete]
    renumbered: List[str] = []
    for new_id, block in enumerate(sentences, 1):
        block = re.sub(r"^#\s*sent_id\s*=\s*.*$", f"# sent_id = {new_id}", block, count=1, flags=re.M)
        renumbered.append(block)

    Path(corpus_path).write_text("\n\n".join(renumbered) + "\n\n", encoding="utf-8")
    rich.print(f"[bold green]✓ removed sent_id {sent_id} and renumbered the file")
    return True


__all__ = [
    "append_sentence",
    "cg3_to_conllu_batch",
    "validate_ud",
    "visualise_conllu",
    "delete_sentence",
]
