from pathlib import Path
from grammar_modules.fst import Fst, fst_parse_sentence, fst_parse_word
import subprocess, re

# ────────────────────────────────────────────────────────────────
# disambiguation.py — process input and run CG3
# ────────────────────────────────────────────────────────────────


# Name of cg3 command 
CG3_NAME = "vislcg3" # or cg3"

# constants for tokenization
PUNCTUATIONS = (
    r'.,;:!?(){}\[\]<>«»“”"'  
)
PRESERVE_TOKEN = "..." # keep ... as literal as in some sentences

# dialects we are handling
# SO = Southern Ojibwe (only PCP RC formation)
# NO = Northern Ojibwe (both gaa- and PCP)
DIALECTS = {"SO", "NO"}

# Paths to disambiguation grammar. Update if moved.
REPO_ROOT = Path(__file__).resolve().parents[2]
DISAMBIGUATION_PATH = REPO_ROOT / "data" / "grammars" / "disambiguation.cg3"


### --------Helper functions (used across the repository)---------
def get_repo_root() -> Path:
    """
    Return a pathlib Path to the repository root.
    """
    return REPO_ROOT

def get_disambiguation_path() -> Path:
    """
    Return a pathlib Path to the disambiguation grammar.
    """
    return DISAMBIGUATION_PATH

def is_dialect_handled(dialect:str):
    return dialect in DIALECTS

def tokenize(ojibwe_sentence:str) -> list[str]:

    """
    Tokenize an Ojibwe sentence, separating punctuation symbols from words.

    Parameters
    ----------
    ojibwe_sentence : str
        The Ojibwe sentence to tokenize.
    Returns
    -------
    list of str
        A list of tokens, where punctuation symbols are separated from words.
    """
    
    TOKEN_RE = re.compile(
        rf'({re.escape(PRESERVE_TOKEN)})'       
        rf'|([{PUNCTUATIONS}])'                   
        rf'|([\wʼ’\'\-–]+)',                      
        flags=re.UNICODE,
        )
    
    tokens = []

    for m in TOKEN_RE.finditer(ojibwe_sentence):
        punct, word = m.group(2), m.group(3)

        if punct is not None:             
            tokens.append(punct)
        elif word is not None:            
            tokens.append(word)
        else:                            
            tokens.append(PRESERVE_TOKEN)

    return tokens


def fst_tags_to_cg3_reading(fst_analysis: str) -> str:
    """
    Convert FST (Finite State Transducer) tags to CG3 (Constraint Grammar 3) reading format.

    The function transforms an FST analysis string containing tags separated by '+'
    into a CG3 reading format where the first word is quoted and the remaining tags
    are listed separately, separated by spaces.

    Parameters
    ----------
    fst_analysis : str
        The input FST analysis string containing tags separated by '+'.

    Returns
    -------
    str
        The CG3 reading format of the input string.
    """    
    output = ""
    if '\t' in fst_analysis:
        fst_analysis = fst_analysis.split('\t', 1)[1]
    tags = fst_analysis.split("+")

    # scan for Pre-verb / Pre-noun tags
    lemma_id = 0
    for i in range(len(tags)):
        if not tags[i].startswith("P") and not tags[i] == "ChCnj":
            lemma_id = i
            break 

    lemma = tags.pop(lemma_id)
    
    # post processing
    lemma = f'"{lemma}"'
    tags = " ".join(tags)    

    output = f"{lemma} {tags}"
    return output 

def fst_output_to_cg3_format(fst_item: dict[str, list]) -> str:
    """
    Reformat FST (Finite State Transducer) output to CG3 (Constraint Grammar 3) format.

    Parameters
    ----------
    fst_item : dict[str, list]
        A dictionary where the key is a string representing a lexical item,
        and the value is a list of attributes or tags associated with that item.

    Returns
    -------
    str
        A string representing the FST output in CG3 format, with the lexical item quoted
        and its attributes separated by spaces.
    """
    output = ""
    word_form = fst_item.get("word_form", "")
    
    word_form_line = f'"<{word_form}>"'
    reading_lines = []
    
    for analysis in fst_item.get("fst_analyses", []):
        reading_line_item = f"\t{fst_tags_to_cg3_reading(fst_analysis=analysis)}"
        reading_lines.append(reading_line_item)
    
    joined_readings = '\n'.join(reading_lines)
    output = f"{word_form_line}\n{joined_readings}"

    return output
    
def ojibwe_sentence_to_cg3_format(ojibwe_sentence: str, fst: Fst, dialect: str | None = None) -> str:
    """
    Convert an Ojibwe sentence to CG3 (Constraint Grammar 3) format.

    Parameters
    ----------
    ojibwe_sentence : str
        The Ojibwe sentence to be converted.
    fst : Fst
        The Finite State Transducer used to analyze the sentence and generate its linguistic tags.

    Returns
    -------
    str
        The Ojibwe sentence reformatted into the CG3 format.

    """
    tokens = tokenize(ojibwe_sentence=ojibwe_sentence)
    sentence_fst_outputs = fst_parse_sentence(input_words=tokens, fst_parser=fst)
    body = "\n".join(fst_output_to_cg3_format(x) for x in sentence_fst_outputs)

    if dialect:
        lines = body.rstrip("\n").split("\n")
        if len(lines) >= 2 and lines[1].startswith("\t"):
            lines[1] = f"{lines[1]} {dialect}"
        else:
            for i in range(1, len(lines)):
                if lines[i].startswith("\t"):
                    lines[i] = f"{lines[i]} {dialect}"
                    break
        body = "\n".join(lines)

    return body.rstrip("\n") + "\n\n"

def is_cg3_available() -> bool:
    """
    Check if CG3 is installed in the system.

    Returns
    -------
    bool
        True if CG3 is installed and accessible, otherwise False.

    """
    command = [CG3_NAME, "--help"]  # display cg3 help
    output = subprocess.run(command, capture_output=True, text=True)
    
    return output.returncode == 0 # return code = 0 means calling cg3 successfully

def cg3_process_text(input_text: str, cg3_grammar_filepath: str) -> str:
    """
    Process input text with the CG3 parser using a custom grammar file.

    Parameters
    ----------
    input_text : str
        The text to be processed.
    cg3_grammar_filepath : str
        Path to the custom CG3 grammar rules file.

    Returns
    -------
    str
        The processed output in CG3 format.
    """
    command = [CG3_NAME, "--grammar", cg3_grammar_filepath] 
    process = subprocess.Popen(command, 
                               stdin=subprocess.PIPE,
                               stdout=subprocess.PIPE,
                               stderr=subprocess.PIPE,
                               text=True,
                               encoding="utf-8"                        
                               )
    try:
        output, error = process.communicate(input=input_text)
        if error:
            print("Error:", error)
        return output
    except Exception as e:
        print("Error:", e)
        return "" 

def sentence_has_ambiguity(sentence:str, fst: Fst) -> tuple:
    """Use FST parser to parse sentence and returns if the sentence has ambiguity in any word"""
    tokens = tokenize(ojibwe_sentence=sentence)
    sentence_fst_outputs = fst_parse_sentence(input_words=tokens, fst_parser=fst)
    for item in sentence_fst_outputs:
        if len(item.get("fst_analyses", [])) > 1:
            return (True, sentence_fst_outputs, item)
    
    return (False, sentence_fst_outputs, None)
    

def disambiguate(sentence: str, cg3_grammar_filepath: str, fst: Fst, verbose: bool = False,  dialect: str | None = None) -> str:
    """
    Disambiguate a sentence using FST readings and CG3 rules.

    Parameters
    ----------
    sentence : str
        The sentence to process.
    cg3_grammar_filepath : str
        Path to the CG3 grammar rules file.
    fst : Fst
        The Finite State Transducer for generating readings.
    verbose : bool, optional
        If True, provides detailed processing information (default is False).

    Returns
    -------
    str
        The disambiguated readings of the sentence.
    """
    if dialect:
        if not is_dialect_handled(dialect):
            raise ValueError(f"Inputted dialect: \"{dialect}\" not currently handled!")
    input_readings = ojibwe_sentence_to_cg3_format(ojibwe_sentence=sentence, fst=fst, dialect=dialect)
    disambiguated_str = cg3_process_text(input_text=input_readings, cg3_grammar_filepath=cg3_grammar_filepath)
    if verbose:
        print("Before parsing:")
        print(input_readings)
        print("-"*20)
        print("After parsing:")
        print(disambiguated_str)
    
    return disambiguated_str