from fst_runtime.fst import Fst
from src.foma_adapter import FomaFst
import subprocess, re

# ────────────────────────────────────────────────────────────────
# disambiguation.py — process input and run CG3
# ────────────────────────────────────────────────────────────────


# Name of cg3 command 
CG3_NAME = "vislcg3" # or cg3

# constants for tokenization
PUNCTUATIONS = (
    r'.,;:!?(){}\[\]<>«»“”"'  
)
PRESERVE_TOKEN = "..." # keep ... as literal as in some sentences


def load_fst_parser(binary_file_path:str) -> Fst: 
    """
    If given .fomabin, return FomaFst (using flookup()).
    Otherwise use fst_runtime for .att file. 
    """
    ext = binary_file_path.lower().rsplit(".", 1)[-1]
    if ext in ("fomabin", "bin"):
        return FomaFst(binary_file_path)
    return Fst(binary_file_path)

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
            tokens.append(word.lower())
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
    
def ojibwe_sentence_to_cg3_format(ojibwe_sentence: str, fst: Fst) -> str:
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
    

def disambiguate(sentence: str, cg3_grammar_filepath: str, fst: Fst, verbose: bool = False) -> str:
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
    input_readings = ojibwe_sentence_to_cg3_format(ojibwe_sentence=sentence, fst=fst)
    disambiguated_str = cg3_process_text(input_text=input_readings, cg3_grammar_filepath=cg3_grammar_filepath)
    if verbose:
        print("Before parsing:")
        print(input_readings)
        print("-"*20)
        print("After parsing:")
        print(disambiguated_str)
    
    return disambiguated_str