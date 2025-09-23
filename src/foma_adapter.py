from __future__ import annotations
import subprocess, os, platform
from typing import List
from pathlib import Path

# ────────────────────────────────────────────────────────────────
# dependency.py — adapter module to support Foma FST
# ────────────────────────────────────────────────────────────────

class _Analysis:
    """Matches fst_runtime's item shape: provides .output_string"""
    def __init__(self, s: str) -> None:
        self.output_string = s

class FomaFst:
    """
    Minimal adapter so the rest of your pipeline can call:
       up_analysis(wordform) -> list[_Analysis]
    Internally calls your batch flookup([word]).
    """
    def __init__(self, bin_path: str) -> None:
        if not Path(bin_path).exists():
            raise FileNotFoundError(bin_path)
        # Optional: sanity check that flookup can open it
        _ = is_flookup_available(bin_path)

        self._bin_path = bin_path  # kept for parity; your flookup uses a global path

    def up_analysis(self, wordform: str) -> List[_Analysis]:
        # Use your flookup() on a single token
        rows = flookup([wordform], bin_path=self._bin_path)  # [{'word_form': ..., 'fst_analyses': [...]}]
        if not rows:
            return []
        analyses = rows[0].get("fst_analyses", [])
        return [_Analysis(a) for a in analyses]


def flookup(input_words, bin_path: str):
    """returns a list of dicts {"word_form": str, "fst_analyses": [RHS strings]}"""
    outputlist = []
    input_str = '\n'.join(input_words) + '\n'  # ensure trailing newline
    if input_str.strip():
        if platform.system() == 'Windows':
            proc = subprocess.run(['flookup', bin_path, '-x'],
                                  input=input_str, text=True, capture_output=True)
            parsed = proc.stdout.strip()
        else:
            # simpler: pass input directly (no printf)
            proc = subprocess.run(['flookup', bin_path, '-x'],
                                  input=input_str, text=True, capture_output=True)
            parsed = proc.stdout.strip()

        blocks = parsed.split('\n\n') if parsed else []
        for i, block in enumerate(blocks):
            rhs_list = []
            for line in block.splitlines():
                if '\t' not in line:
                    continue
                _, rhs = line.split('\t', 1)              # keep RHS only
                rhs = rhs.strip()
                if rhs and rhs != '+?':                   # drop unknowns
                    rhs_list.append(rhs)
            outputlist.append({"word_form": input_words[i], "fst_analyses": rhs_list})
    return outputlist
    


def is_flookup_available(bin_path: str) -> bool:
    """
    Check if flookup is installed in the system.

    Returns
    -------
    bool
        `True` if flookup is installed and accessible, otherwise `False`.
    """
    print(f"FST file is {bin_path}")
    command = ['flookup', bin_path, "-h"]  
    output = subprocess.run(command, input='', capture_output=True, text=True)
    
    return output.returncode == 0 
