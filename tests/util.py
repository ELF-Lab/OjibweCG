import re
from pathlib import Path
from typing import Dict

#  normalise CG3 blocks
def normalise(block: str) -> str:
    block = re.sub(r"//.*", "", block)          # remove comments
    block = re.sub(r"\n{2,}", "\n", block)      # collapse blank lines
    block = "\n".join(line.rstrip() for line in block.splitlines())
    return block.strip()

# load / dump '### ID' blocks 
DELIM = re.compile(r"^###\s+(\S+)\s*$", re.M)

def load_blocks(path: Path) -> Dict[str, str]:
    txt = path.read_text(encoding="utf-8") if path.exists() else ""
    parts = DELIM.split(txt)
    return {parts[i]: parts[i + 1].strip() for i in range(1, len(parts), 2)}

def dump_blocks(blocks: Dict[str, str]) -> str:
    out = []
    for _id in sorted(blocks):
        out += [f"### {_id}", blocks[_id].rstrip(), ""]
    return "\n".join(out).strip() + "\n"