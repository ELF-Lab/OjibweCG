# ojcg/booklets.py
# Unified HTML booklet generator for disambiguation and dependency trees.

from __future__ import annotations
from rich.progress import Progress
from pathlib import Path
from typing import List, Dict, Tuple, Iterable, Optional
import os

# third-party
import jinja2
import pyconll

try:
    from rich import print as rprint
except Exception:
    def rprint(*a, **k):  # graceful fallback
        print(*a, **k)

# local
from fst_runtime.fst import Fst
from src.disambiguation import (
    disambiguate,
    ojibwe_sentence_to_cg3_format,
)
from src.corpus import cg3_to_conllu_batch  # used by build-dep when --reparse is set


# ---------- shared utilities ----------

def load_lines(path: Path) -> List[str]:
    return [ln.rstrip("\n") for ln in path.read_text(encoding="utf8").splitlines() if ln.strip()]

def ensure_usr_local_bin_in_path() -> None:
    os.environ["PATH"] += os.pathsep + "/usr/local/bin"

def assert_parallel(oj: List[str], en: List[str]) -> None:
    if len(oj) != len(en):
        raise ValueError(f"Parallel files not aligned: oj={len(oj)} vs en={len(en)}")

def try_import_spacy():
    try:
        import spacy  # noqa
        from spacy.tokens import Doc  # noqa
        from spacy import displacy  # noqa
    except Exception as e:
        raise RuntimeError(
            "spaCy is required for dependency SVG rendering. "
            "Install with `pip install spacy`."
        ) from e


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

    FST = Fst(str(fst_path))
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
    for tok in doc:
        seen = set()
        cur  = tok
        while cur != cur.head:
            if cur in seen:
                raise RuntimeError(f"Cycle involving «{tok.text}»")
            seen.add(cur)
            cur = cur.head

def sentence_svg(sent, *, compact=True, collapse_punct=True) -> str:
    import spacy
    from spacy.tokens import Doc
    from spacy import displacy

    words  = [tok.form for tok in sent]
    spaces = [True] * (len(words) - 1) + [False]
    nlp    = spacy.blank("xx")
    doc    = Doc(nlp.vocab, words=words, spaces=spaces)

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
    cg3_grammar_path: Optional[Path] = None,
    fst_path: Optional[Path] = None,
) -> None:
    """
    If reparse_with_cg3=True, you must pass cg3_grammar_path and fst_path.
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
        if not (cg3_grammar_path and fst_path):
            raise ValueError("reparse_with_cg3=True requires cg3_grammar_path and fst_path")
        FST = Fst(str(fst_path))

        # Clear / recreate treebank file (fresh run)
        Path(treebank_path).write_text("", encoding="utf8")

        with Progress() as progress:
            task = progress.add_task("Reparsing with CG3", total=len(ojibwe))
            for i, sentence in enumerate(ojibwe):
                disamb = disambiguate(sentence, str(cg3_grammar_path), FST)
                cg3_runs[i] = disamb
                cg3_to_conllu_batch(disamb, str(treebank_path))
                progress.update(task, advance=1)

    # Load trees (either just written, or already present)
    trees = list(pyconll.load_from_file(str(treebank_path)))

    if len(trees) != len(ojibwe):
        rprint(f"[bold yellow]Warning: treebank has {len(trees)} trees; text has {len(ojibwe)} lines.")
        # We still attempt to zip safely by min length:
        min_n = min(len(trees), len(ojibwe))
        trees   = trees[:min_n]
        ojibwe  = ojibwe[:min_n]
        english = english[:min_n]
        cg3_runs = cg3_runs[:min_n]

    # sanity sweep for empty tokens
    for s_no, sent in enumerate(trees, 1):
        for t_no, tok in enumerate(sent, 1):
            if not tok.form:
                rprint(f"[bold red]Empty token: sentence {s_no}, token {t_no} (id={tok.id})")

    rows: List[Dict] = []
    with Progress() as progress:
        task = progress.add_task("Rendering dependency SVGs", total=len(trees))
        for i, (tree, oj, en) in enumerate(zip(trees, ojibwe, english), 1):
            svg = sentence_svg(tree, compact=True, collapse_punct=True)
            rows.append({"no": i, "oj": oj, "en": en, "svg": svg, "cg3": cg3_runs[i-1]})
            progress.update(task, advance=1)

    out_html_path.write_text(DEP_TPL.render(rows=rows, title=html_title), encoding="utf8")
    rprint(f"[bold green]✔ Dependency booklet written to {out_html_path} ({len(rows)} sentences)")

__all__ = [
    "build_disambig_booklet",
    "build_dep_booklet",
]
