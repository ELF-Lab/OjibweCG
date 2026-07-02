from __future__ import annotations
import subprocess, os, platform
from typing import List
from pathlib import Path

# ────────────────────────────────────────────────────────────────
# dependency.py — adapter module to support Foma FST
# ────────────────────────────────────────────────────────────────

# Global variables
# Path to fst
# Paths to disambiguation and dependency grammars. Update if moved.
REPO_ROOT = Path(__file__).resolve().parents[2]
FST_PATH = REPO_ROOT / "data" / "fst" / "ojibwe20260630.fomabin"


class _Analysis:
    """Matches fst_runtime's item shape: provides .output_string"""
    def __init__(self, s: str) -> None:
        self.output_string = s

class Fst:
    """
    Minimal adapter so the rest of your pipeline can call:
       up_analysis(wordform) -> list[_Analysis]
    Internally calls your batch flookup([word]).
    """
    def __init__(self, bin_path: str) -> None:
        if not Path(bin_path).exists():
            raise FileNotFoundError(bin_path)
        # check that flookup can open the path
        _ = is_flookup_available(bin_path)

        self._bin_path = bin_path

    def up_analysis(self, wordform: str) -> List[_Analysis]:
        # Use flookup() on a single token
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
        proc = subprocess.run(['flookup', bin_path, '-x'], input=input_str, text=True, capture_output=True)
        parsed = proc.stdout.strip()

        blocks = parsed.split('\n\n') if parsed else []
        for i, block in enumerate(blocks):
            rhs_list = []
            for line in block.splitlines():
                if '\t' in line:
                    _, rhs = line.split('\t', 1)              # keep RHS only
                    rhs = rhs.strip()
                else: 
                    rhs = line
                if rhs and rhs != '+?':                   # drop unknowns
                    rhs_list.append(rhs)
                    
            outputlist.append({"word_form": input_words[i], "fst_analyses": rhs_list})
    return outputlist
    


def fst_parse_word(input_word:str, fst_parser:Fst) -> list[str]:
    """
    Parse an Ojibwe word using a FST and return a list of analyses.

    Parameters
    ----------
    input_word : str
        The Ojibwe word to be analyzed.
    fst_parser : Fst
        An FST parser object that provides the `up_analysis` method for morphological analysis.

    Returns
    -------
    list of str
        A list of analysis strings produced by the FST for the given input word.

    """
    fst_analyses = fst_parser.up_analysis(wordform=input_word)
    return [item.output_string
            for item in fst_analyses
            ] 
    
    
def fst_parse_sentence(input_words:list[str], fst_parser:Fst) -> list:
    """
    Parse an Ojibwe sentence and return analyses for each word.

    Parameters
    ----------
    input_words : list of str
        A list of words representing the Ojibwe sentence to be parsed.
    fst_parser : Fst
        An FST (Finite State Transducer) parser instance used to analyze each word.

    Returns
    -------
    list of dict
        A list of dictionaries, each containing:
            - 'word_form': str, the original word.
            - 'fst_analyses': list, the analyses produced by the FST parser for the word.

    """
    return [{"word_form": word,
             "fst_analyses": fst_parse_word(word, fst_parser=fst_parser)
            }
            for word in input_words
            ]

def is_flookup_available(bin_path: str) -> bool:
    """
    Check if flookup is installed in the system.

    Returns
    -------
    bool
        True if flookup is installed and accessible, otherwise `False`.
    """
    print(f"FST file is {bin_path}")
    command = ['flookup', bin_path, "-h"]  
    output = subprocess.run(command, input='', capture_output=True, text=True)
    
    return output.returncode == 0 


def load_fst_parser(binary_file_path="") -> Fst: 
    """
    Return a Foma compiled Fst (using flookup()). fst_runtime (.att files) deprecated.
    """
    if binary_file_path: 
        return Fst(binary_file_path)
    else:
        return Fst(FST_PATH)
