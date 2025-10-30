
from dataclasses import dataclass
from pathlib import Path
from typing import List, Dict, Tuple, Optional, Set
from collections import defaultdict, Counter
import re

# ---------------- Data model ----------------
@dataclass
class Reading:
    lemma: str
    tags_str: str
    def key(self) -> str:
        return f"{self.lemma}\t{' '.join(self.tags_str.split())}"
    def tags(self) -> List[str]:
        return self.tags_str.strip().split()

@dataclass
class Token:
    surface: str
    readings: List[Reading]

@dataclass
class Block:
    sent_id: str
    text: str
    eng: str
    tokens: List[Token]

# ---------------- CG3 parser ----------------
_HEADER_RE  = re.compile(r"^#\s*(sent_id|text|eng)\s*=\s*(.*)\s*$")
_TOKEN_RE   = re.compile(r'^\s*"?<(.+?)>"?\s*$')
_READING_RE = re.compile(r'^\s*"(.+?)"\s+(.+?)\s*$')

def parse_cg3_text(text: str) -> List[Block]:
    blocks: List[Block] = []
    sid = txt = eng = ""
    toks: List[Token] = []
    cur_surface: Optional[str] = None
    cur_reads: List[Reading] = []

    def push_token():
        nonlocal cur_surface, cur_reads, toks
        if cur_surface is not None:
            toks.append(Token(cur_surface, cur_reads))
        cur_surface, cur_reads = None, []

    def push_block():
        nonlocal sid, txt, eng, toks, blocks
        if toks:
            blocks.append(Block(sid, txt, eng, toks))
        sid = txt = eng = ""
        toks = []

    for raw in text.splitlines():
        line = raw.rstrip("\n")
        m = _HEADER_RE.match(line)
        if m:
            k, v = m.group(1), m.group(2).strip()
            if k == "sent_id":
                if toks:
                    push_token(); push_block()
                sid = v
            elif k == "text":
                txt = v
            elif k == "eng":
                eng = v
            continue
        m = _TOKEN_RE.match(line.strip())
        if m:
            if cur_surface is not None:
                push_token()
            cur_surface = m.group(1); cur_reads = []
            continue
        if line.startswith("\t") or line.startswith("    "):
            m = _READING_RE.match(line.strip())
            if m:
                cur_reads.append(Reading(m.group(1), m.group(2)))
            continue
        if not line.strip():
            if cur_surface is not None:
                push_token()
            if toks:
                push_block()
            continue
    if cur_surface is not None:
        push_token()
    if toks:
        push_block()
    return blocks

def parse_cg3_file(path: Path) -> List[Block]:
    return parse_cg3_text(Path(path).read_text(encoding="utf-8"))

def _align_idx_map(blocks: List[Block]) -> Dict[Tuple[str,int], Tuple[Block,int]]:
    return { (b.sent_id, i+1): (b, i) for b in blocks for i, _ in enumerate(b.tokens) }

# ---------------- Auto-contrast discovery ----------------
_POS_ATOMS = {"NA","NI","NAD","NID","VAI","VTI","VTA","VII","VAIO","ADVInter","PCInterj"}
_FORM_ATOMS = {"ChCnj","Cnj","Ind","Imp","Pcp","Pos","Neg"}
_NOUN_POS = {"NA", "NAD", "NI", "NID"}

def _cat_NOUN(r: Reading) -> Optional[str]:
    pos = _cat_POS(r)
    if pos not in _NOUN_POS:
        return None
    tags = set(r.tags())
    for t in ("ObvSg", "ObvPl", "ProxSg", "ProxPl", "Sg", "Pl"):
        if t in tags:
            return t
    return None


def _cat_POS(r: Reading) -> Optional[str]:
    for t in r.tags():
        if t in _POS_ATOMS: return t
    return None
def _cat_FORM(r: Reading) -> tuple:
    return tuple(sorted(set(_FORM_ATOMS & set(r.tags()))))
def _cat_PV(r: Reading) -> tuple:
    fams = []
    for t in r.tags():
        if t.startswith("PVTense/"): fams.append(t.split("/",1)[1])
        elif t.startswith("PVSub/"): fams.append(t.split("/",1)[1])
        elif t.startswith("PVDir/"): fams.append(t.split("/",1)[1])
        elif t.startswith("PVRel/"): fams.append(t.split("/",1)[1])
        elif t.startswith("PVLex/"): fams.append(t.split("/",1)[1])
    return tuple(sorted(set(fams))) if fams else tuple()
def _cat_SUBJ(r: Reading) -> tuple:
    vals = [t for t in r.tags() if t.endswith("Subj")]
    return tuple(sorted(set(vals)))
def _cat_OBJ(r: Reading) -> tuple:
    vals = [t for t in r.tags() if t.endswith("Obj")]
    return tuple(sorted(set(vals)))
def _cat_POSS(r: Reading) -> tuple:
    vals = [t for t in r.tags() if t.endswith("Poss")]
    return tuple(sorted(set(vals)))
def _cat_LEMMA(r: Reading) -> str:
    return r.lemma

_CAT_FUNS = {
    "LEMMA": _cat_LEMMA,
    "POS":   _cat_POS,
    "FORM":  _cat_FORM,
    "PV":    _cat_PV,
    "SUBJ":  _cat_SUBJ,
    "OBJ":   _cat_OBJ,
    "POSS":  _cat_POSS,
    "NOUN":  _cat_NOUN,
}

def _reading_signature(r: Reading) -> Dict[str, object]:
    return { name: fn(r) for name, fn in _CAT_FUNS.items() }

def token_contrast_key(readings: List[Reading]) -> tuple:
    per_cat_values: Dict[str, Set[str]] = defaultdict(set)

    for r in readings:
        sig = _reading_signature(r)
        for cat, val in sig.items():
            if val is None or val == "" or val == tuple():
                continue
            sval = "|".join(val) if isinstance(val, tuple) and val else str(val)
            per_cat_values[cat].add(sval)

    # collect varying categories
    varying = [(cat, tuple(sorted(vals))) for cat, vals in per_cat_values.items() if len(vals) > 1]

    # to make outputs cleaner - choose the "parent"
    SUPPRESS_IF_PRESENT = {
        "NOUN": {"POS"},
        "FORM": {"PV", "SUBJ", "OBJ", "POSS"},
    }

    cats_present = {c for c, _ in varying}
    to_hide: Set[str] = set()
    for parent, kids in SUPPRESS_IF_PRESENT.items():
        if parent in cats_present:
            to_hide.update(kids)

    if to_hide:
        varying = [(c, v) for (c, v) in varying if c not in to_hide]

    varying.sort(key=lambda x: x[0])
    return tuple(varying)

def contrast_label(key: tuple) -> str:
    if not key:
        return "(no-contrast)"

    def _noun_to_animacy_if_binary(vals: Tuple[str, ...]) -> Optional[str]:
        pairs = {
            ("ObvPl", "Pl"), ("ObvSg", "Sg"), ("ProxPl", "Pl"), ("ProxSg", "Sg"),
        }
        s = tuple(sorted(vals))
        return "NOUN{NA, NI}" if s in pairs else None

    parts = []
    for cat, vals in key:
        if cat == "NOUN":
            animacy_label = _noun_to_animacy_if_binary(vals)
            if animacy_label:
                parts.append(animacy_label)
                continue
        parts.append(f"{cat}{{{', '.join(vals)}}}")
    return " | ".join(parts)


# ---------------- Evaluation ----------------
def _gold_key(tok: Token) -> Optional[str]:
    return tok.readings[0].key() if tok.readings else None

def _sys_keys(tok: Token) -> List[str]:
    return [r.key() for r in tok.readings]

def per_contrast_eval_from_paths(ambig_path: Path, gold_path: Path, sys_path: Path):
    """Return a pandas DataFrame with per-contrast metrics and a few examples."""
    import pandas as pd

    ambig_blocks = parse_cg3_file(ambig_path)
    gold_blocks  = parse_cg3_file(gold_path)
    sys_blocks   = parse_cg3_file(sys_path)

    gold_map = _align_idx_map(gold_blocks)
    sys_map  = _align_idx_map(sys_blocks)

    counts = Counter(); exact = Counter(); contains = Counter(); kept_sum = Counter()
    examples = defaultdict(list)

    for b in ambig_blocks:
        for i, tok in enumerate(b.tokens, start=1):
            if len(tok.readings) <= 1:
                continue
            key = token_contrast_key(tok.readings)
            label = contrast_label(key)
            sid = (b.sent_id, i)
            if sid not in gold_map or sid not in sys_map:
                continue
            gb, gi = gold_map[sid]; sb, si = sys_map[sid]
            gk = _gold_key(gb.tokens[gi]); sks = _sys_keys(sb.tokens[si])
            if gk is None:
                continue
            k = len(sks)
            counts[label] += 1
            kept_sum[label] += k
            if gk in sks: contains[label] += 1
            if k == 1 and sks and sks[0] == gk: exact[label] += 1
            if len(examples[label]) < 5:
                examples[label].append(dict(sent_id=b.sent_id, token_idx=i, surface=tok.surface, gold=gk, system=" | ".join(sks)))

    rows = []
    for label, n in counts.most_common():
        rows.append({
            "Contrast": label,
            "n": n,
            "Exact": int(exact[label]),
            "Fail": int(n - exact[label]),
            "Exact%": 100 * (exact[label]/n),
            "ContainsGold%": 100 * (contains[label]/n),
            "Avg sys kept": kept_sum[label]/n,
            "Examples": examples[label],
        })
    return pd.DataFrame(rows)