from __future__ import annotations
from pathlib import Path
from itertools import islice
from typing import List, Union, Optional, Tuple, Iterable, Iterator
from grammar_modules.disambiguation import (
    DISAMBIGUATION_PATH,
    cg3_process_text,
    tokenize,
)
from grammar_modules.dependency import (
    DEPENDENCY_PATH,
    cg3_to_conllu_block,
    parse_dependencies_batch,
    split_cg3_sentences,
)
from grammar_modules.fst import (
    Fst,
    load_fst_parser,
)
import sys
import re
import rich
import subprocess

# ────────────────────────────────────────────────────────────────
# corpus.py — build and query CoNLL-U corpus
# ────────────────────────────────────────────────────────────────


def append_sentence(conllu_text: str, sent_id: int, corpus_path: Union[str, Path] = "ojibwe_treebank.conllu", verbose: bool = False) -> int:
    corpus_path = Path(corpus_path)

    # exactly one blank line after the sentence block
    conllu_block = conllu_text.rstrip() + "\n\n"

    with corpus_path.open(
        mode="a",
        encoding="utf-8",
    ) as corpus_file:
        corpus_file.write(conllu_block)

    if verbose:
        print(f"Appended sentence #{sent_id} to {corpus_path.name}")

    return sent_id

def cg3_to_conllu_batch(cg3_text: str,
                        corpus_path: Union[str, Path] = "ojibwe_treebank.conllu",
                        en_line: str = None,
                        lang: str = "ud",
                        verbose: bool = True) -> None:
    """Parse CG3 text -> CoNLL-U, then append to corpus_path.
    Auto-assigns sent_id = (current sentence count + 1).
    """
    p = Path(corpus_path)
    sent_id = 1 + (p.read_text(encoding="utf-8").count("\n\n") if p.exists() else 0)
    conllu = cg3_to_conllu_block(cg3_text, sent_id, en_line=en_line)
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
    """Render one sentence with spaCy displaCy."""
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
    displacy.render(doc, style="dep", jupyter=False,
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


def _batched(iterable: Iterable, batch_size: int) -> Iterator[list]:
    iterator = iter(iterable)
    while batch := list(islice(iterator, batch_size)):
        yield batch


def build_treebank_from_xml_sentences(
    sentences: Iterable[tuple[str, str]],
    corpus_path: Union[str, Path],
    *,
    fst: Optional[Fst] = None,
    batch_size: int = 500,
    dependency_grammar: Union[str, Path] = DEPENDENCY_PATH,
    disambiguation_grammar: Union[str, Path] = DISAMBIGUATION_PATH,
    verbose: bool = True,
) -> int:
    corpus_path = Path(corpus_path)
    corpus_path.parent.mkdir(parents=True, exist_ok=True)

    dependency_grammar = str(dependency_grammar)
    disambiguation_grammar = str(disambiguation_grammar)

    if fst is None:
        fst = load_fst_parser()


    existing_text = (
        corpus_path.read_text(encoding="utf-8")
        if corpus_path.exists()
        else ""
    )

    existing_ids = [
        int(match)
        for match in re.findall(
            r"^#\s*sent_id\s*=\s*(\d+)\s*$",
            existing_text,
            flags=re.MULTILINE,
        )
    ]

    next_sent_id = max(existing_ids, default=0) + 1
    num_sentences = 0

    with corpus_path.open("a", encoding="utf-8") as corpus_file:
        if existing_text and not existing_text.endswith("\n\n"):
            corpus_file.write("\n\n")

        for batch_number, sentence_batch in enumerate(
            _batched(sentences, batch_size),
            start=1,
        ):
            batch_tokens = [
                token
                for ojibwe_text, _ in sentence_batch
                for token in tokenize(ojibwe_text)
            ]

            # One FST lookup for all unseen forms in the batch.
            fst.preload(batch_tokens)

            dependency_blocks = parse_dependencies_batch(
                sentences=[
                    ojibwe_text
                    for ojibwe_text, _ in sentence_batch
                ],
                dependency_grammar=dependency_grammar,
                disambiguation_grammar=disambiguation_grammar,
                fst=fst,
            )

            conllu_blocks = []

            for dependency_block, (_, english_text) in zip(
                dependency_blocks,
                sentence_batch,
                strict=True,
            ):
                conllu = cg3_to_conllu_block(
                    dependency_block,
                    next_sent_id,
                    en_line=english_text,
                )

                conllu_blocks.append(
                    conllu.rstrip() + "\n\n"
                )

                next_sent_id += 1
                num_sentences += 1

            corpus_file.write("".join(conllu_blocks))

            if verbose:
                print(
                    f"Processed batch {batch_number}: "
                    f"{num_sentences} sentences added."
                )

    if verbose:
        print(
            f"Added {num_sentences} sentences to "
            f"{corpus_path.name}."
        )

    return num_sentences

__all__ = [
    "append_sentence",
    "cg3_to_conllu_batch",
    "validate_ud",
    "visualise_conllu",
    "delete_sentence",
    "build_treebank_from_xml_sentences",
]
