from __future__ import annotations
from pathlib import Path
from typing import List, Union, Optional
from src.dependency import parse_cg3_block, tokens_to_conllu
import re
import rich
import subprocess
import shlex


def append_sentence(conllu_text: str,
                    sent_id: int,
                    corpus_path: Union[str, Path] = "ojibwe_treebank.conllu"
                    ) -> Optional[int]:
    """Append one CoNLL‑U sentence if its `# text =` is new; return id used.
    Duplicate detection is by exact `# text =` match.
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
            print(f"⚠️  sentence already in {corpus_path} with sent_id {dup_id}")
            return dup_id

    corpus_path.write_text(existing + conllu_text if existing else conllu_text, encoding="utf-8")
    print(f"✓ appended sentence #{sent_id} to {corpus_path.name}")
    return sent_id


def cg3_to_conllu_batch(cg3_text: str,
                        corpus_path: Union[str, Path] = "ojibwe_treebank.conllu",
                        lang: str = "ud") -> None:
    """Parse CG3 text → CoNLL‑U, then append to `corpus_path`.
    Auto-assigns sent_id = (current sentence count + 1).
    """
    p = Path(corpus_path)
    sent_id = 1 + (p.read_text(encoding="utf-8").count("\n\n") if p.exists() else 0)
    tokens = parse_cg3_block(cg3_text)
    conllu = tokens_to_conllu(tokens, sent_id)
    append_sentence(conllu, sent_id, p)


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

    cmd = f"python3 {validator.as_posix()} --lang {lang} {shlex.quote(str(corpus_path))}"
    proc = subprocess.run(cmd, shell=True, capture_output=True, text=True)
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
    """Render one sentence with spaCy displaCy (requires pyconll + spacy)."""
    try:
        import pyconll, spacy
        from spacy.tokens import Doc
        from spacy import displacy
    except ImportError as e:
        rich.print("[bold red]❌ spaCy/pyconll missing"); rich.print(str(e)); return

    corpus_path = Path(corpus_path)
    if not corpus_path.is_file():
        rich.print(f"[bold red]❌ file not found: {corpus_path}")
        return

    sentences = list(pyconll.load_from_file(corpus_path))
    if not 0 < sent_no <= len(sentences):
        rich.print(f"[bold red]❌ sentence index {sent_no} out of range (1..{len(sentences)})")
        return
    sent = sentences[sent_no - 1]

    words = [tok.form for tok in sent]
    spaces = [True] * (len(words) - 1) + [False]
    nlp = spacy.blank("xx")
    doc = Doc(nlp.vocab, words=words, spaces=spaces)

    for i, (sp_tok, ud_tok) in enumerate(zip(doc, sent)):
        head_i = int(ud_tok.head) - 1 if ud_tok.head != "0" else i
        sp_tok.pos_ = ud_tok.upos or "X"
        sp_tok.tag_ = ud_tok.xpos or "_"
        sp_tok.dep_ = ud_tok.deprel or "dep"
        sp_tok.head = doc[head_i]

    rich.print(f"[bold cyan]visualising sentence {sent_no} from {corpus_path.name}")
    displacy.render(doc, style="dep", jupyter=True,
                    options={"compact": compact, "collapse_punct": collapse_punct})


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
