from pathlib import Path
from typing import Dict, List, Tuple, Iterable, Optional
from collections import defaultdict
from .data_io import parse_conllu

FOCUS_RELS = Iterable[str]

def eval_rels_from_paths(gold_path, sys_path, focus_rels) -> tuple[dict, dict]:
    return eval_rels_detailed(parse_conllu(gold_path), parse_conllu(sys_path), focus_rels)

def write_per_rel_table(per_rel: dict, rels: Iterable[str], out_path: Optional[Path] = None) -> str:
    """
    Plain text table w/ per-relation counts.
    """
    def g(r, k, default=0):
        return per_rel.get(r, {}).get(k, default)

    header = f"{'rel':<14}{'gold':>6}{'sys':>6}{'correct':>9}{'P':>7}{'R':>7}{'F1':>7}"
    lines = [header, "-" * len(header)]
    for r in rels:
        gold = g(r, "gold")
        sysc = g(r, "sys")
        corr = g(r, "correct")
        p = g(r, "precision", 0.0)
        rc = g(r, "recall", 0.0)
        f1 = g(r, "f1", 0.0)
        lines.append(f"{r:<14}{gold:>6}{sysc:>6}{corr:>9}{p:>7.3f}{rc:>7.3f}{f1:>7.3f}")

    table = "\n".join(lines)
    if out_path is not None:
        Path(out_path).write_text(table, encoding="utf-8")
    return table

def eval_rels_detailed(
    gold: Dict[str,List[Tuple[str,str]]],
    sys: Dict[str,List[Tuple[str,str]]],
    focus_rels = FOCUS_RELS
):
    focus = set(focus_rels)

    # totals for overall metrics, restricted to focus rels (either side has one)
    total_considered = 0
    sys_total = 0
    gold_total = 0
    correct_total = 0

    # per-relation tallies
    per_gold = defaultdict(int) # gold count for rel r
    per_sys  = defaultdict(int) # sys count for rel r
    per_corr = defaultdict(int) # correct count for rel r

    for sid, g_toks in gold.items():
        if sid not in sys: 
            continue
        s_toks = sys[sid]
        L = min(len(g_toks), len(s_toks))
        for i in range(L):
            _, g_rel = g_toks[i]
            _, s_rel = s_toks[i]

            # update per-rel denominators
            if g_rel in focus: per_gold[g_rel] += 1
            if s_rel in focus: per_sys[s_rel]  += 1

            # overall set of tokens we evaluate (union condition)
            if (g_rel in focus) or (s_rel in focus):
                total_considered += 1
                if s_rel in focus: sys_total += 1
                if g_rel in focus: gold_total += 1
                if g_rel == s_rel and g_rel in focus:
                    correct_total += 1
                    per_corr[g_rel] += 1

    def safe_div(n, d): return (n / d) if d else 0.0

    # overall metrics
    overall_precision = safe_div(correct_total, sys_total)
    overall_recall    = safe_div(correct_total, gold_total)
    overall_f1        = safe_div(2*overall_precision*overall_recall, (overall_precision+overall_recall))
    overall_acc       = safe_div(correct_total, total_considered)

    # per-relation metrics
    per_rel_metrics = {}
    for r in focus_rels:
        p = safe_div(per_corr[r], per_sys[r])
        rcl = safe_div(per_corr[r], per_gold[r])
        f1 = safe_div(2*p*rcl, (p+rcl))
        per_rel_metrics[r] = {
            "gold": per_gold[r],
            "sys": per_sys[r],
            "correct": per_corr[r],
            "precision": p,
            "recall": rcl,
            "f1": f1,
        }

    macro_p = sum(m["precision"] for m in per_rel_metrics.values()) / len(focus_rels)
    macro_r = sum(m["recall"]    for m in per_rel_metrics.values()) / len(focus_rels)
    macro_f = safe_div(2*macro_p*macro_r, macro_p+macro_r)

    overall = {
        "tokens_considered": total_considered,
        "precision": overall_precision,
        "recall": overall_recall,
        "f1": overall_f1,
        "accuracy": overall_acc,
        "sys_total": sys_total,
        "gold_total": gold_total,
        "correct": correct_total,
        "macro_precision": macro_p,
        "macro_recall": macro_r,
        "macro_f1": macro_f,
    }
    return overall, per_rel_metrics