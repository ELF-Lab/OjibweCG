from fst_runtime.fst import Fst
import subprocess

# constants for tokenization
PUNCTUTATIONS = ".,!()?$"
PRESERVE_TOKEN = "..." # keep ... as literal as in some sentences


def load_fst_parser(binary_file_path:str) -> Fst: 
    """Load FST parser from binary 'att' file"""
    return Fst(binary_file_path)

def fst_parse_word(input_word:str, fst_parser:Fst) -> list[str]:
    """ Parse an Ojibwe word and return a list of analyses"""
    fst_analyses = fst_parser.up_analysis(wordform=input_word)
    return [item.output_string
            for item in fst_analyses
            ] 
    
    
def fst_parse_sentence(input_words:list[str], fst_parser:Fst) -> list:
    """ Parse an Ojibwe sentence (list of words) and return a nested list of analyses"""
    return [{"word_form": word,
             "fst_analyses": fst_parse_word(word, fst_parser=fst_parser)
            }
            for word in input_words
            ]
    


def tokenize(ojibwe_sentence:str) -> list[str]:
    "Tokenize Ojibwe sentence, separate symbols like . , !"
    
    raw_tokens = ojibwe_sentence.lower().split()
    
    output = []
    for i, item in enumerate(raw_tokens):
        if (item[0] in PUNCTUTATIONS) and (PRESERVE_TOKEN not in item):
            # word starts with a character in PUNCTUATIONS
            output.extend([item[0], item[1:]])
        elif (item[-1] in PUNCTUTATIONS) and (PRESERVE_TOKEN not in item):
            # word ends with a character in PUNCTUATIONS
            output.extend([item[:-1], item[-1]])
        else:
           output.append(item) 
    
    return output 


def fst_tags_to_cg3_reading(fst_analysis:str) -> str:
    """ Convert FST tags to CG3 reading format, e.g. 
        waabam+VTA+Cnj+Pos+Neu+1SgSubj+3SgProxObj -> "waabam" VTA Cnj Pos Neu 1SgSubj 3SgProxObj
    """
    output = ""
    tags = fst_analysis.split("+") 

    # scan for Pre-verb / Pre-noun tags
    lemma_id = 0
    for i in range(len(tags)):
        if not tags[i].startswith("P"):
            lemma_id = i
            break 

    lemma = tags.pop(lemma_id)
    
    # post processing
    lemma = f'"{lemma}"'
    tags = " ".join(tags)    

    output = f"{lemma} {tags}"
    return output 

def fst_output_to_cg3_format(fst_item:dict[str, list]) -> str:
    """Reformat FST output to CG3 format """
    output = ""
    word_form = fst_item.get("word_form", "")
    
    word_form_line = f'"<{word_form}>"'
    reading_lines = []
    
    for analysis in fst_item.get("fst_analyses", []):
        reading_line_item = f"\t{fst_tags_to_cg3_reading(fst_analysis=analysis)}"
        reading_lines.append(reading_line_item)
    
    output = f"{word_form_line}\n{'\n'.join(reading_lines)}"
    return output
    
def objiwe_sentence_to_cg3_format(ojibwe_sentence:str, fst:Fst) -> str:
    """Convert an Ojibwe sentence to cg3 input format """
    output = "" 
    tokens = tokenize(ojibwe_sentence=ojibwe_sentence)
    # print("Tokens =", tokens)
    sentence_fst_outputs = fst_parse_sentence(input_words=tokens, fst_parser=fst)
    output = "\n".join([fst_output_to_cg3_format(fst_item=item)
                        for item in sentence_fst_outputs
                        ])
    return output

def is_cg3_available() -> bool: 
    """ Check if CG3 is installed in the system"""
    command = ["cg3", "--help"]  # display cg3 help
    output = subprocess.run(command, capture_output=True, text=True)
    
    return output.returncode == 0 # return code = 0 means calling cg3 successfully

def cg3_process_text(input_text:str, cg3_grammar_filepath:str) -> str:
    """Call CG3 parser to process input text, using a custom cg3 rules file """
    command = ["cg3", "--grammar", cg3_grammar_filepath]  
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
    
def disambugate(sentence:str, cg3_grammar_filepath:str, fst: Fst) -> str:
    """Call FST to get readings of a word, then run the CG rules and returns the disambiguated readings"""
    input_readings = objiwe_sentence_to_cg3_format(ojibwe_sentence=sentence, fst=fst)
    disambiguated_str = cg3_process_text(input_text=input_readings, cg3_grammar_filepath=cg3_grammar_filepath)
    print("Before parsing:")
    print(input_readings)
    print("-"*20)
    print("After parsing:")
    print(disambiguated_str)
    
    return disambiguated_str