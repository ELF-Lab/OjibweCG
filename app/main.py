from nicegui import ui
import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../src/')))
import cg3_process as cg3 
from fst_runtime.fst import Fst

FST_BINARY_FILENAME = "../data/fst/ojibwe.att"
CG3_GRAMMAR_FILENAME = "../data/CG3_rules/Ojibwe.cg3"

PUNCTUATIONS = [".", ",", "!", "?", ";", ":", ")"]

def initialize_core_environment() -> dict: 
    """Initialize FST parser and CG3 parser"""
    output = dict() 
    # load Ojibwe FST binary file to parse Ojibwe words
    output["fst_parser"] = cg3.load_fst_parser(binary_file_path=FST_BINARY_FILENAME)
    
    return output 

def process_input(page_states: dict):
    # ui.notify(f'FST parsing {page_states["ojibwe_sentence"]}...')
    if page_states["ojibwe_sentence"][-1] not in PUNCTUATIONS:
        page_states["ojibwe_sentence"] += "."
    fst_readings = cg3.objiwe_sentence_to_cg3_format(ojibwe_sentence=page_states["ojibwe_sentence"], 
                                                     fst=core_environment["fst_parser"])
    # disambiguated_str = cg3_process_text(input_text=fst_readings, cg3_grammar_filepath=CG3_GRAMMAR_FILENAME)
    page_states["fst_readings"] = fst_readings
    print(f"Fst readings = \n{page_states['fst_readings']}")
    return fst_readings

def apply_cg3_rules(page_states: dict):
    # ui.notify(f'CG3 parsing {page_states["fst_readings"]}...')
    disambiguated_str = cg3.cg3_process_text(input_text=page_states["fst_readings"], cg3_grammar_filepath=CG3_GRAMMAR_FILENAME)
    print(f"Disambiguated readings = \n{disambiguated_str}")
    page_states["disambiguated_readings"] = disambiguated_str
    return disambiguated_str
    
@ui.page('/')
def homepage():
    ui.markdown("#### Ojibwe Disambiguation and Dependency Parser")
    ui.markdown("**Ojibwe sentence:**")
    
    page_states = {"ojibwe_sentence": "",
                   "fst_readings": "", 
                   "disambiguated_readings": ""
                  }

    ui.input(value="Nindayaawaa mishiimin.").bind_value_to(page_states, 'ojibwe_sentence')

    ui.button('FST Analysis', color='orange', on_click=lambda: fst_readings.set_content(f"``` {process_input(page_states)} ```"))
    
    # handles FST parsing
    ui.markdown("**Fst readings:**")
    fst_readings = ui.markdown().style("white-space:pre-wrap;") # support multiple-line markdown
            
    # handles CG3 parsing
    ui.button('Apply Constraint Grammar', color='orange', on_click=lambda: disambiguated_readings.set_content(f"``` {apply_cg3_rules(page_states=page_states)} ```"))
    ui.markdown("**Disambiguated readings:**")
    disambiguated_readings = ui.markdown().style("white-space:pre-wrap;")


core_environment = initialize_core_environment()
ui.run(title="Ojibwe Disambiguation and Dependency Parser")