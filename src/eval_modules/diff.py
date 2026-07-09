from pathlib import Path
from typing import List, Dict
from eval_modules.auto_contrast_eval import parse_cg3_file, Block, Token
from eval_modules.data_io import parse_conllu
import pandas as pd
import re

def diff_table(diffs, out_path: Path | None = None):
    df = pd.DataFrame(diffs)

    if df.empty:
        print("No diffs found.")
        return df

    for col in df.columns:
        if df[col].apply(lambda x: isinstance(x, list)).any():
            df[col] = df[col].apply(
                lambda x: "\n".join(map(str, x)) if isinstance(x, list) else x
            )

    if out_path is not None:
        df.to_csv(out_path, sep="\t", index=False)

    return df

def write_changed_cg3_blocks(new_path: Path, changed_sent_ids: set, out_path: Path):

    content = new_path.read_text(encoding="utf-8")
    raw_blocks = re.split(r"\n\s*\n", content)

    selected_blocks = []

    for raw_block in raw_blocks:
        sent_id_match = re.search(
            r"^#\s*sent_id\s*=\s*(.+?)\s*$",
            raw_block,
            flags=re.MULTILINE
        )

        if sent_id_match is None:
            continue

        sent_id = sent_id_match.group(1)

        if sent_id in changed_sent_ids:
            selected_blocks.append(raw_block.strip())

    output = "\n\n".join(selected_blocks)

    if selected_blocks:
        output += "\n"

    out_path.write_text(output, encoding="utf-8")

def compare_cg3_readings(old_path: Path, new_path: Path, write_changed_blocks_path: Path | None = None):
    old_blocks = parse_cg3_file(old_path)
    new_blocks = parse_cg3_file(new_path)

    old_by_id = {block.sent_id: block for block in old_blocks}
    new_by_id = {block.sent_id: block for block in new_blocks}

    diffs = []
    changed_sent_ids = set()

    for sent_id in old_by_id:
        old_block = old_by_id[sent_id]
        new_block = new_by_id[sent_id]

        if len(old_block.tokens) != len(new_block.tokens):
            print(f"token length mismatch in block # {sent_id}")
            continue

        for i, old_tok in enumerate(old_block.tokens):
            new_tok = new_block.tokens[i]

            old_keys = {reading.key() for reading in old_tok.readings}
            new_keys = {reading.key() for reading in new_tok.readings}

            added = sorted(new_keys - old_keys)
            removed = sorted(old_keys - new_keys)

            if added or removed:
                diffs.append({
                    "sent_id": sent_id,
                    "text": old_block.text,
                    "token_idx": i + 1,
                    "surface": old_tok.surface,
                    "added": added,
                    "removed": removed,
                })
                
                changed_sent_ids.add(str(sent_id))
    
    if write_changed_blocks_path is not None:
        write_changed_cg3_blocks(
            new_path=new_path,
            changed_sent_ids=changed_sent_ids,
            out_path=write_changed_blocks_path
        )

    return diffs

def compare_conllu_outputs(old_path: Path, new_path: Path):
    old = parse_conllu(old_path)
    new = parse_conllu(new_path)

    diffs = []

    for sent_id in old:
        if sent_id not in new:
            raise ValueError(f"Sentence {sent_id} not in new file.")

        old_sent = old[sent_id]
        new_sent = new[sent_id]

        old_tokens = old_sent["tokens"]
        new_tokens = new_sent["tokens"]

        if len(old_tokens) != len(new_tokens):
            raise ValueError(
                f"Token count mismatch in sentence {sent_id}: "
                f"old has {len(old_tokens)}, new has {len(new_tokens)}"
            )

        for i, old_tok in enumerate(old_tokens):
            new_tok = new_tokens[i]

            if old_tok["form"] != new_tok["form"]:
                raise ValueError(
                    f"Token mismatch in sentence {sent_id}, token {i + 1}: "
                    f"old has {old_tok['form']}, new has {new_tok['form']}"
                )

            changed = []

            if old_tok["head"] != new_tok["head"]:
                changed.append("head")

            if old_tok["deprel"] != new_tok["deprel"]:
                changed.append("deprel")

            if changed:
                diffs.append({
                    "sent_id": sent_id,
                    "text": old_sent["text"],
                    "token_id": old_tok["id"],
                    "form": old_tok["form"],
                    "old_head": old_tok["head"],
                    "new_head": new_tok["head"],
                    "old_deprel": old_tok["deprel"],
                    "new_deprel": new_tok["deprel"],
                    "changed": changed,
                })

    return diffs