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
FST_PATH = REPO_ROOT / "data" / "fst" / "OjibweMorph-v1_2_1.fomabin"


class _Analysis:
    """Matches fst_runtime's item shape: provides .output_string"""
    def __init__(self, s: str) -> None:
        self.output_string = s

class Fst:
    """
    Minimal adapter so the rest of your pipeline can call:
       up_analysis(wordform) -> list[_Analysis]
    """
    def __init__(self, bin_path: str) -> None:
        if not Path(bin_path).exists():
            raise FileNotFoundError(bin_path)
        # check that flookup can open the path
        _ = is_flookup_available(bin_path)

        self._bin_path = bin_path
        self._cache: dict[str, tuple[str, ...]] = {}


    def up_analysis(self, wordform: str) -> List[_Analysis]:
        # Use flookup() on a single token
        analyses_by_word = self.up_analysis_batch([wordform])
        return analyses_by_word[wordform]

    def up_analysis_batch(self, wordforms: list[str]) -> dict[str, List[_Analysis]]:
        unique_wordforms = list(dict.fromkeys(wordforms))

        missing_wordforms = [
            wordform
            for wordform in unique_wordforms
            if wordform not in self._cache
        ]

        if missing_wordforms:
            rows = flookup(
                missing_wordforms,
                bin_path=self._bin_path,
            )

            if len(rows) != len(missing_wordforms):
                raise RuntimeError(
                    "flookup returned an unexpected number of result blocks: "
                    f"expected {len(missing_wordforms)}, got {len(rows)}"
                )

            for row in rows:
                wordform = row["word_form"]
                analyses = row.get("fst_analyses", [])
                self._cache[wordform] = tuple(analyses)

        return {
            wordform: [
                _Analysis(analysis)
                for analysis in self._cache[wordform]
            ]
            for wordform in unique_wordforms
        }
    
    def preload(self, wordforms: list[str]) -> None:
        lookup_wordforms = []

        for wordform in wordforms:
            lookup_wordforms.append(wordform)

            if wordform and wordform[0].isupper():
                lowercase_word = wordform[0].lower() + wordform[1:]
                lookup_wordforms.append(lowercase_word)

        self.up_analysis_batch(lookup_wordforms)


def flookup(input_words, bin_path: str):
    """returns a list of dicts {"word_form": str, "fst_analyses": [RHS strings]}"""
    if not input_words:
        return []

    input_str = "\n".join(input_words) + "\n"

    proc = subprocess.run(
        ["flookup", bin_path, "-x"],
        input=input_str,
        text=True,
        capture_output=True,
        encoding="utf-8",
    )

    if proc.returncode != 0:
        raise RuntimeError(
            "flookup failed:\n"
            f"{proc.stderr.strip()}"
        )

    parsed = proc.stdout.strip()
    blocks = parsed.split("\n\n") if parsed else []

    outputlist = []

    for wordform, block in zip(input_words, blocks, strict=True):
        rhs_list = []

        for line in block.splitlines():
            if "\t" in line:
                _, rhs = line.split("\t", 1)
                rhs = rhs.strip()
            else:
                rhs = line.strip()

            if rhs and rhs != "+?":
                rhs_list.append(rhs)

        outputlist.append({
            "word_form": wordform,
            "fst_analyses": rhs_list,
        })

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
    original_analyses = [
        item.output_string
        for item in fst_parser.up_analysis(wordform=input_word)
    ]

    if not input_word or not input_word[0].isupper():
        return original_analyses

    lowercase_word = input_word[0].lower() + input_word[1:]

    lowercase_analyses = [
        item.output_string
        for item in fst_parser.up_analysis(wordform=lowercase_word)
    ]

    return list(dict.fromkeys(original_analyses + lowercase_analyses))
    
    
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
    lookup_wordforms = []

    for word in input_words:
        lookup_wordforms.append(word)

        if word and word[0].isupper():
            lowercase_word = word[0].lower() + word[1:]
            lookup_wordforms.append(lowercase_word)

    analyses_by_word = fst_parser.up_analysis_batch(lookup_wordforms)

    sentence_analyses = []

    for word in input_words:
        analyses = [
            item.output_string
            for item in analyses_by_word[word]
        ]

        if word and word[0].isupper():
            lowercase_word = word[0].lower() + word[1:]

            analyses.extend(
                item.output_string
                for item in analyses_by_word[lowercase_word]
            )

        sentence_analyses.append({
            "word_form": word,
            "fst_analyses": list(dict.fromkeys(analyses)),
        })

    return sentence_analyses


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
