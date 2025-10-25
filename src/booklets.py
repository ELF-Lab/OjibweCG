from __future__ import annotations
from rich.progress import Progress
from pathlib import Path
from typing import List, Dict, Tuple, Iterable, Optional
import os
import re

# third-party
import jinja2
import pyconll

try:
    from rich import print as rprint
except Exception:
    def rprint(*a, **k):  # graceful fallback
        print(*a, **k)

# local
from src.disambiguation import (
    disambiguate,
    ojibwe_sentence_to_cg3_format,
    load_fst_parser
)
from src.dependency import parse_dependencies
from src.corpus import cg3_to_conllu_batch  # used by build-dep when --reparse is set

# ────────────────────────────────────────────────────────────────
# booklets.py — build HTML visualization booklets
# ────────────────────────────────────────────────────────────────


# ---------- shared utilities ----------

def load_lines(path: Path) -> List[str]:
    return [ln.rstrip("\n") for ln in path.read_text(encoding="utf8").splitlines() if ln.strip()]

def ensure_usr_local_bin_in_path() -> None:
    os.environ["PATH"] += os.pathsep + "/usr/local/bin"

def assert_parallel(oj: List[str], en: List[str]) -> None:
    if len(oj) != len(en):
        raise ValueError(f"Parallel files not aligned: oj={len(oj)} vs en={len(en)}")

def try_import_spacy():
    """Import spacy, return error on exception."""
    try:
        import spacy
        from spacy.tokens import Doc  
        from spacy import displacy
    except Exception as e:
        raise RuntimeError(
            "spaCy is required for dependency SVG rendering. "
            "Install with pip install spacy."
        ) from e

def parse_disamb_file(path: Path) -> List[Dict[str, str]]:
    """Parse an already formatted disambiguation file into English, Ojibwe, and CG3 blocks."""

    items: List[Dict[str, str]] = []
    oj: Optional[str] = None
    en: Optional[str] = None
    block_lines: List[str] = []

    CG3_TEXT_RE = re.compile(r"^#\s*text\s*=\s*(.+)$")
    CG3_ENG_RE  = re.compile(r"^#\s*eng\s*=\s*(.+)$")

    def flush():
        nonlocal oj, en, block_lines
        if oj is not None and en is not None and block_lines:
            items.append({"oj": oj.strip(), "en": en.strip(),
                          "cg3_disamb": "\n".join(block_lines).rstrip() + "\n"})
        oj, en, block_lines = None, None, []

    with path.open("r", encoding="utf-8") as f:
        for raw in f:
            line = raw.rstrip("\n"); line_l = line.lstrip()
            if line_l.startswith("# sent_id"):
                flush(); continue
            m = CG3_TEXT_RE.match(line_l); m2 = CG3_ENG_RE.match(line_l)
            if m:  oj = m.group(1); continue
            if m2: en = m2.group(1); continue
            if line_l.startswith("<") or line_l.startswith('"') or not line_l.strip():
                block_lines.append(line); continue
        flush()
    return items

def build_dep_booklet_from_disamb(
    source_cg3_file: Path,
    dep_grammar_path: Path,
    out_conllu_path: Path,
    out_html_path: Path,
    html_title: str = "Dependency Booklet",
) -> None:
    """
    Render a dependency booklet from a CG3 disambiguation file.
    - Runs the dependency CG on each segment (using append_parent_block_as_segments in src.corpus)
    - Writes a CoNLL-U file and grouped HTML booklet (segments grouped by parent_id)
    """
    from src.corpus import append_parent_block_as_segments  # local import to avoid cycles

    ensure_usr_local_bin_in_path()
    try_import_spacy()

    items = parse_disamb_file(source_cg3_file)
    if not items:
        raise ValueError(f"No sentences parsed from {source_cg3_file}")

    out_conllu_path.write_text("", encoding="utf-8")

    # 1) run dependency grammar per item; collect dep CG3 by sent_id
    dep_runs_by_sid: Dict[str, str] = {}
    with Progress() as progress:
        task = progress.add_task("Running dependency grammar", total=len(items))
        for idx, it in enumerate(items, 1):
            used = append_parent_block_as_segments(
                cg3_disamb_block = it["cg3_disamb"],
                dep_grammar_path = dep_grammar_path,
                parent_index     = idx,
                oj_text          = it.get("oj"),
                en_text          = it.get("en"),
                corpus_path      = out_conllu_path,
                verbose          = False,
            )
            for sid, dep_cg3 in used:
                dep_runs_by_sid[sid] = dep_cg3
            progress.update(task, advance=1)

    # 2) load trees and header map
    trees = list(pyconll.load_from_file(str(out_conllu_path)))
    conllu_text = out_conllu_path.read_text(encoding="utf-8")
    sid2hdr: Dict[str, Dict[str, str]] = {}
    for block in re.split(r"\n\s*\n", conllu_text.strip()):
        header_lines = [ln for ln in block.splitlines() if ln.startswith("#")]
        if not header_lines:
            continue
        header = "\n".join(header_lines)
        m_id   = re.search(r"^#\s*sent_id\s*=\s*(.+)$", header, re.M)
        m_text = re.search(r"^#\s*text\s*=\s*(.+)$", header, re.M)
        m_en   = re.search(r"^#\s*text_en\s*=\s*(.+)$", header, re.M) \
              or re.search(r"^#\s*text_en_full\s*=\s*(.+)$", header, re.M)
        if m_id:
            sid = m_id.group(1).strip()
            sid2hdr[sid] = {
                "text":    (m_text.group(1).strip() if m_text else ""),
                "text_en": (m_en.group(1).strip()   if m_en   else ""),
            }

    # 3) group by parent_id
    def _parent_id(sid: str) -> str:
        return sid.split(".", 1)[0] if sid and "." in sid else sid or ""

    # linear list in file order
    linear: List[Dict[str, str]] = []
    with Progress() as progress:
        task = progress.add_task("Rendering dependency SVGs", total=len(trees))
        for tree in trees:
            svg = sentence_svg(tree, compact=True, collapse_punct=True)
            sid = getattr(tree, "id", None)
            hdr = sid2hdr.get(sid, {})
            linear.append({
                "sid": sid,
                "oj": hdr.get("text", ""),
                "en": hdr.get("text_en", ""),
                "svg": svg,
                "cg3": dep_runs_by_sid.get(sid, ""),
            })
            progress.update(task, advance=1)

    groups: List[Dict[str, str]] = []
    cur_parent: Optional[str] = None
    cur_oj: List[str] = []; cur_en: List[str] = []
    cur_svg: List[str] = []; cur_cg3: List[str] = []

    def _flush():
        if not cur_oj: return
        groups.append({
            "oj": "\n".join(cur_oj),
            "en": "\n".join(cur_en),
            "svg": "".join(f'<div class="viz">{s}</div>' for s in cur_svg),
            "cg3": "\n\n".join([c for c in cur_cg3 if c]) or None,
        })

    for seg in linear:
        pid = _parent_id(seg["sid"])
        if cur_parent is None:
            cur_parent = pid
        if pid != cur_parent:
            _flush()
            cur_parent = pid
            cur_oj.clear(); cur_en.clear(); cur_svg.clear(); cur_cg3.clear()
        cur_oj.append(seg["oj"]); cur_en.append(seg["en"])
        cur_svg.append(seg["svg"]); cur_cg3.append(seg["cg3"])
    _flush()

    rows = [{"no": i, **g} for i, g in enumerate(groups, 1)]
    out_html_path.write_text(DEP_TPL.render(rows=rows, title=html_title), encoding="utf-8")
    print(f"Wrote booklet: {out_html_path}  ({len(rows)} sentences)")
    print(f"Wrote treebank: {out_conllu_path}")

# ---------- disambiguation booklet ----------

DISAMBIG_TPL = jinja2.Template(r"""
<!doctype html><html lang="en"><head>
<meta charset="utf-8">
<title>{{ title }} ({{ rows|length }} sentences)</title>
<style>
body{font-family:system-ui,Arial,sans-serif;margin:2rem;}
figure{margin:2rem 0;padding:1rem;border:1px solid #ddd;border-radius:8px;}
figcaption{font-weight:bold;margin-bottom:.5rem;}
.oj{color:#1565c0;} .en{color:#2e7d32;}
pre{background:#f9f9f9;border:1px solid #eee;
    padding:1rem;margin-top:.5rem;
    font:14px/1.4 monospace;white-space:pre-wrap;}
.before{max-height:20em;overflow-y:auto;}
.after {max-height:20em;overflow-y:auto;border-color:#cfd;}
</style></head><body>
<h1>{{ title }} ({{ rows|length }} sentences)</h1>
{% for r in rows %}
<figure>
  <figcaption>#{{ "%02d"|format(r.no) }}
    <span class="oj">{{ r.oj }}</span><br>
    <span class="en">{{ r.en }}</span>
  </figcaption>

  <pre class="before">{{ r.before | e }}</pre>
  <pre class="after">{{ r.after  | e }}</pre>
</figure>
{% endfor %}
</body></html>""")

def build_disambig_booklet(
    ojibwe_path: Path,
    english_path: Path,
    cg3_grammar_path: Path,
    fst_path: Path,
    out_html_path: Path,
    html_title: str,
) -> None:
    ensure_usr_local_bin_in_path()

    FST = load_fst_parser(str(fst_path))
    ojibwe  = load_lines(ojibwe_path)
    english = load_lines(english_path)
    assert_parallel(ojibwe, english)

    rows = []
    with Progress() as progress:
        task = progress.add_task("Parsing", total=len(ojibwe))
        for idx, (oj, en) in enumerate(zip(ojibwe, english), 1):
            before = ojibwe_sentence_to_cg3_format(oj, FST)
            after  = disambiguate(oj, str(cg3_grammar_path), FST)
            rows.append({"no": idx, "oj": oj, "en": en, "before": before, "after": after})

            progress.update(task, advance=1)


    out_html_path.write_text(DISAMBIG_TPL.render(rows=rows, title=html_title), encoding="utf8")
    rprint(f"[bold green]✔ Disambiguation booklet written to {out_html_path} ({len(rows)} sentences)")


# ---------- dependency booklet ----------

def assert_tree(doc):
    """Make sure there are no cycles in the conllu."""
    for tok in doc:
        seen = set()
        cur  = tok
        while cur != cur.head:
            if cur in seen:
                raise RuntimeError(f"Cycle involving «{tok.text}»")
            seen.add(cur)
            cur = cur.head

def sentence_svg(sent, *, compact=True, collapse_punct=True) -> str:
    """Render the svg per sentence."""
    import spacy
    from spacy.tokens import Doc
    from spacy import displacy

    words = [tok.form for tok in sent]
    spaces = [True] * (len(words) - 1) + [False]
    nlp = spacy.blank("xx")
    doc = Doc(nlp.vocab, words=words, spaces=spaces)

    # POS/TAG
    for sp_tok, ud_tok in zip(doc, sent):
        sp_tok.pos_ = ud_tok.upos or "X"
        sp_tok.tag_ = ud_tok.xpos or "_"

    # heads & labels
    for sp_tok, ud_tok in zip(doc, sent):
        if ud_tok.head == "0":        # root
            sp_tok.head = sp_tok
            sp_tok.dep_ = "root"
        elif not ud_tok.deprel or ud_tok.deprel == "dep":
            sp_tok.head = sp_tok
            sp_tok.dep_ = "dep"
        else:
            head_i = int(ud_tok.head) - 1
            sp_tok.head = doc[head_i]
            sp_tok.dep_ = ud_tok.deprel

    assert_tree(doc)
    return displacy.render(doc, style="dep", jupyter=False,
                           options={"compact": compact, "collapse_punct": collapse_punct})

def tree_meta_fallback(tree) -> Tuple[Optional[str], str, str]:
    """
    Return metadata that works across pyconll versions.
    """
    sid = getattr(tree, "id", None)
    oj  = getattr(tree, "text", "") or ""
    meta = getattr(tree, "meta", {}) or {}
    en  = meta.get("text_en") or meta.get("text_en_full") or ""
    return sid, oj, en


DEP_TPL = jinja2.Template("""
<!doctype html><html lang="en"><head>
<meta charset="utf-8">
<title>{{ title }} ({{ rows|length }} sentences)</title>
<style>
body{font-family:system-ui,Arial,sans-serif;margin:2rem;}
figure{margin:2rem 0;padding:1rem;border:1px solid #ddd;border-radius:8px;}
figcaption{font-weight:bold;margin-bottom:.5rem;}
.oj{color:#1565c0;} .en{color:#2e7d32;}
.viz svg{width:100%!important;height:auto;}
.viz svg{overflow:visible;}
.viz svg > * { transform: translateX(80px); }
.cg3{background:#f9f9f9;border:1px solid #eee;
     padding:1rem;margin-top:1rem;
     font:14px/1.4 monospace;white-space:pre-wrap;
     overflow-x:auto;max-height:28em;}
</style></head><body>
<h1>{{ title }} ({{ rows|length }} sentences)</h1>
{% for r in rows %}
<figure>
 <figcaption>#{{ "%02d"|format(r.no) }}
   <span class="oj">{{ r.oj }}</span><br>
   <span class="en">{{ r.en }}</span>
 </figcaption>
 <div class="viz">{{ r.svg | safe }}</div>
 {% if r.cg3 is not none %}
 <pre class="cg3">{{ r.cg3 | e }}</pre>
 {% endif %}
</figure>
{% endfor %}
</body></html>""")

def build_dep_booklet(
    treebank_path: Path,
    ojibwe_path: Path,
    english_path: Path,
    out_html_path: Path,
    html_title: str,
    *,
    reparse_with_cg3: bool = False,
    disamb_grammar_path: Optional[Path] = None,
    dep_grammar_path: Optional[Path] = None,
    fst_path: Optional[Path] = None,
) -> None:
    """
    If reparse_with_cg3=True, must pass paths to FST and CG3 grammars.
    We will:
      - disambiguate each Ojibwe sentence with CG3,
      - collect the raw CG3 output,
      - convert to CONLL-U via cg3_to_conllu_batch (appending to treebank_path).
    Otherwise, we assume treebank_path already exists and is aligned with parallel text.
    """
    ensure_usr_local_bin_in_path()
    try_import_spacy()

    ojibwe  = load_lines(ojibwe_path)
    english = load_lines(english_path)
    assert_parallel(ojibwe, english)

    cg3_runs: List[str] = [None] * len(ojibwe)  # keep index alignment

    if reparse_with_cg3:
        if not (disamb_grammar_path and dep_grammar_path and fst_path):
            raise ValueError("reparse_with_cg3=True requires disamb_grammar_path, dep_grammar_path, and fst_path")
        FST = load_fst_parser(str(fst_path))
        Path(treebank_path).write_text("", encoding="utf8")

        with Progress() as progress:
            task = progress.add_task("Reparsing with CG3", total=len(ojibwe))
            for i, sentence in enumerate(ojibwe):
                deps_cg3 = parse_dependencies(sentence, dependency_grammar=str(dep_grammar_path), disambiguation_grammar=str(disamb_grammar_path), fst=FST, verbose=False)
                cg3_runs[i] = deps_cg3  # keep for display under each SVG if desired
                cg3_to_conllu_batch(deps_cg3, str(treebank_path), verbose=False)
                progress.update(task, advance=1)

    # Load trees (either just written, or already present)
    trees = list(pyconll.load_from_file(str(treebank_path)))

    # If reparsing/splitting happened, len(trees) may != len(ojibwe).
    if len(trees) != len(ojibwe):
        rprint(f"[bold yellow]Note: treebank has {len(trees)} sentence(s); "
            f"parallel text has {len(ojibwe)} line(s). Using CoNLL-U headers for display.")

    # Sanity sweep for empty tokens
    for s_no, sent in enumerate(trees, 1):
        for t_no, tok in enumerate(sent, 1):
            if not tok.form:
                rprint(f"[bold red]Empty token: sentence {s_no}, token {t_no} (id={tok.id})")

    rows: List[Dict] = []
    with Progress() as progress:
        task = progress.add_task("Rendering dependency SVGs", total=len(trees))

        if len(trees) == len(ojibwe):
            # 1:1 alignment, use og text
            for i, (tree, oj, en) in enumerate(zip(trees, ojibwe, english), 1):
                svg = sentence_svg(tree, compact=True, collapse_punct=True)
                rows.append({
                    "no": i,
                    "oj": oj,
                    "en": en,
                    "svg": svg,
                    "cg3": cg3_runs[i-1] if i-1 < len(cg3_runs) else None,
                })
                progress.update(task, advance=1)
        else:
            # Counts differs
            for i, tree in enumerate(trees, 1):
                sid, oj, en = tree_meta_fallback(tree)
                svg = sentence_svg(tree, compact=True, collapse_punct=True)
                rows.append({
                    "no": i,
                    "oj": oj,
                    "en": en,
                    "svg": svg,
                    "cg3": None,
                })
                progress.update(task, advance=1)

    out_html_path.write_text(DEP_TPL.render(rows=rows, title=html_title), encoding="utf8")
    rprint(f"[bold green]✔ Dependency booklet written to {out_html_path} ({len(rows)} sentences)")

__all__ = [
    "build_disambig_booklet",
    "build_dep_booklet",
]