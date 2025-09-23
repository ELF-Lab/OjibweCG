# Usage Guide  
This document explains how to install the required tools and run the grammar CLI scripts in this repository.  
To see the modules in a more interactive Jupyter Notebook, go to the [`notebooks/`](../notebooks/) folder. 

# Table of Contents
- [Installation / Requirements](#installation--requirements)


## Installation / Requirements

Follow these steps to get the project running:

### 1. Install Python
You will need Python version 3.11 or 3.12.  
Newer versions like 3.13 may not work with all the tools yet.  

On macOS, if you have [Homebrew](https://brew.sh/) installed:
```bash
brew install python@3.12
```

On Ubuntu or Debian Linux:
```bash
sudo apt install python3.12
```

For Windows use WSL (Ubuntu) and follow the Ubuntu steps. Native Windows builds of CG3 are not maintained.

### 2. Create a virtual environment
It is best to create a Python virtual environment so that all the project’s libraries are installed in one place and don’t interfere with other projects.

In the root folder of the repository:
```bash
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install --upgrade pip
```

Now you will see `(.venv)` in your terminal prompt. This means the environment is active.  
Whenever you come back later, run `source .venv/bin/activate` again to activate it.

### 3. Install Python libraries
All required Python libraries are listed in `requirements.txt`.  
Install them with:
```bash
pip install -r requirements.txt
```
This installs packages such as spaCy, pyconll, jinja2, and others that the scripts depend on.


### 4. Install Foma 
[Foma](https://fomafst.github.io/) provides the `foma` compiler and the `flookup` utility used by the FST portion of the pipeline.

On macOS:
```bash
brew install foma
```

On Ubuntu / Debian Linux:
```
sudo apt install foma
```

To check that it is installed, run:
```
foma -v
```

If a version number is printed, Foma is installed.

### 5. Install VISL CG3 (Constraint Grammar)
[CG3](https://edu.visl.dk/cg3/chunked/installation.html) is a separate program that the Python code calls. You must install it so that the `vislcg3` command is available in your terminal.

On macOS:
```bash
brew install vislcg3
```

On Ubuntu / Debian Linux:
```bash
sudo apt install cg3
```

If these commands do not work on your system, you can build CG3 from source:  
https://visl.sdu.dk/cg3.html

To check that it is installed, run:
```bash
vislcg3 --version
```
You should see a version number printed.

### 6. FST file
The tools also require a finite-state transducer (FST) binary file.  
This repository already includes two FST formats under `data/fst/`.  
If you only want to run the existing scripts, you do not need to build anything yourself.


### 7. Ready to go! 
Once you have completed the steps above, the scripts detailed below should all be runnable without issues. 
One thing to note, there might be certain system-based installation quirks for some of the packages above, if there are serious issues on any system with the current set, please let us know! 


## Running the CLI Tools
All main models in this repository can be run from the command line. This section will introduce the various commands to run both the disambiguation and dependency grammars, and what type of output formats can be produced with them. 

As an additional note, most of development is done through Jupyter notebooks. The scripts below are useful as quick entry points to running the main modules, but using notebooks allows for a more transparent view of the steps taken in the pipeline. 

---

### Flag index (shared across commands)
Use the following as an index when going through the various CLI examples.

#### Core flags (shared across most commands)
- `--fst-bin PATH` — **required**. Path to your FST binary (e.g., `data/fst/ojibwe.att`).
- `--grammar PATH` — **required**. Path to the CG3 grammar used by the command (disambiguation or dependency).
- `--input PATH|-` — **required**. Input text file (or `-`/stdin).
- `--output PATH` — **required if applicable**. Output file (when the command writes results).
- `--cg3-name NAME` — *optional*. CG3 binary (default: `vislcg3`). Change only if CG3 is not on your PATH.
- `--sent-split` — *optional*. Treat each line of the input as a separate sentence/unit. Without it, the whole file is processed as one block.

#### Stats-only flags
- `--top N` — *optional*. Number of “top ambiguous tokens” to list (default: 50).
- `--quiet` — *optional*. Suppress printing the stats to terminal (useful if you only care about the output file).

#### Corpus flags
- `--cg3-file PATH` — **required for `add`**. CG3 output file to convert/append.
- `--corpus PATH` — **required**. Target `.conllu` file (treebank).
- `--lang CODE` — *optional*. UD language code (default: `ud`, currently no code for Ojibwe).
- `--validator PATH` — *optional*. Path to UD `validate.py` (default: `third_party/ud-tools/validate.py`).
- `--no-validate` — *optional*. Skip UD validation after appending (faster, but less safe).
- `--id SENT_ID` — **required for `delete`**. Sentence ID to remove from the corpus.

#### Booklets flags
- `--treebank PATH` — **required for dep booklet**. CoNLL-U file to render (or regenerate).
- `--oj PATH` — **required**. Ojibwe sentences file.
- `--en PATH` — **required**. English translations file.
- `--out PATH` — **required**. Output HTML file.
- `--title TEXT` — **required**. Title shown at the top of the HTML page.
- `--reparse` — *optional*. If set, re-run CG3 on the Ojibwe sentences and regenerate the treebank before rendering.

---

### Disambiguation CLI (Text → FST → CG3 disambiguation)

The pure disambiguation pipeline takes Ojibwe text, runs it through the FST and the disambiguation grammar, and then prints the CG3 output to the terminal (stdout). This is most useful for quickly inspecting CG3 analyses. 
The associated script is located at [`scripts/disambiguation_cli.py`](scripts/disambiguation_cli.py)

**Inputs:** `--fst-bin  --grammar  --input`  
**Options:** `--cg3-name  --sent-split`  
**Output:** Printed to terminal (stdout). Use `>` to save to file. 

### Examples

**Example 1:** Run on a text file (one parse per line):
```bash
python3 -m scripts.disambiguation_cli \
  --fst-bin data/fst/ojibwe.att \
  --grammar data/rules/disambiguation.cg3 \
  --input data/parallel/oj.txt \
  --sent-split
```
Processes each line of `oj.txt` through the FST + CG3 and prints the CG3 analyses to the terminal.  

**Example 2:**  Run on a single sentence from stdin:
```bash
echo "odaanaang bimibatoowan odayan gaa-bimaagonebizod ." \
| python3 -m scripts.disambiguation_cli \
    --fst-bin data/fst/ojibwe.att \
    --grammar data/rules/disambiguation.cg3 \
    --sent-split
```
Takes the text typed into the terminal (via `echo`) and prints its CG3 analysis.  

**Example 3:**  Save output to a file:
```bash
python3 -m scripts.disambiguation_cli \
  --fst-bin data/fst/ojibwe.att \
  --grammar data/rules/disambiguation.cg3 \
  --input data/parallel/oj.txt --sent-split \
  > data/results/disambiguated.txt
```
Processes `oj.txt` and writes the CG3 output into `disambiguated.txt`.

---

### Disambiguation Stats CLI (Text → FST → CG3 disambiguation → Stats table)

This tool runs the disambiguation pipeline on your text and produces a stats report with counts and ambiguity patterns (e.g., how many readings were removed, top ambiguous tokens, patterns by POS).  
The script is located at [`scripts/disambiguation_stats_cli.py`](scripts/disambiguation_stats_cli.py) .

**Inputs:** `--fst-bin  --grammar  --input`  
**Options:** `--cg3-name  --sent-split  --top  --output  --quiet`  
**Output:** Stats report (stdout or `--output` file).  

###

**Example 1:** Run on a text file (treat each line as one input)
```bash
python3 -m scripts.disambiguation_stats_cli \
  --fst-bin data/fst/ojibwe.att \
  --grammar data/rules/disambiguation.cg3 \
  --input data/parallel/oj.txt \
  --sent-split
```
Processes each line in `oj.txt` with FST + CG3 and prints a stats report to the terminal.

**Example 2:** Save the report to a file
```bash
python3 -m scripts.disambiguation_stats_cli \
  --fst-bin data/fst/ojibwe.att \
  --grammar data/rules/disambiguation.cg3 \
  --input data/parallel/oj.txt --sent-split \
  --output data/disambig_stats/ojibwe_stats.md
```
Processes `oj.txt` and writes a stats report to `ojibwe_stats.md`.

**Example 3: Change how many top ambiguous tokens are listed**
```bash
python3 -m scripts.disambiguation_stats_cli \
  --fst-bin data/fst/ojibwe.att \
  --grammar data/rules/disambiguation.cg3 \
  --input data/parallel/oj.txt --sent-split \
  --top 10 \
  --output data/disambig_stats/ojibwe_stats_top10.md
```
Same as above but shows only the top 10 ambiguous tokens in the report.

--- 

### Dependency CLI (Text → FST → CG3 dependency → CoNLL-U)

Takes Ojibwe text, runs it through the FST, then a dependency CG3 grammar**, converts the result to **CoNLL-U**, and writes a `.conllu` file.
The script is located at [`scripts/dependency_cli.py`](scripts/dependency_cli.py) .


**Inputs:** `--fst-bin  --grammar  --input  --output`  
**Options:** `--cg3-name`  
**Output:** CoNLL-U file (`.conllu`).  

### Examples

**Example 1:** Basic usage (one CoNLL-U block per line)
```bash
python3 -m scripts.dependency_cli \
  --fst-bin data/fst/ojibwe.att \
  --grammar data/rules/dependency.cg3 \
  --input data/parallel/oj.txt \
  --output data/results/sample_dependency.conllu
```
This assumes your input file (`oj.txt`) has one input per line. Each line will be processed separately and added to the output `.conllu` file.

**Example 2:** Single sentence from stdin
```bash
echo "odaanaang bimibatoowan odayan gaa-bimaagonebizod ." \
| python3 -m scripts.dependency_cli \
    --fst-bin data/fst/ojibwe.att \
    --grammar data/rules/dependency.cg3 \
    --input /dev/stdin \
    --output data/results/one_sentence.conllu
```
Here you directly type or pipe in one sentence. Using `/dev/stdin` as input tells the script to read from the shell instead of a file.

---

### Corpus CLI (Manage CoNLL-U treebanks)

This tool provides simple commands to add, validate, and delete sentences in your CoNLL-U corpus.  
The script is located at `scripts/corpus_cli.py`.

**Subcommands:**
1. `add` – Convert CG3 output into CoNLL-U format and append it to a corpus file.  
2. `validate` – Run the UD validator (`validate.py`) on an existing CoNLL-U file.  
3. `delete` – Remove a sentence by its `sent_id` from a corpus file, renumbering subsequent sent_id values. 




**`add`:**  
**Inputs:** `--cg3-file PATH  --corpus PATH`  
**Options:** `--lang CODE  --validator PATH  --no-validate`  
**Output:** Updates the `.conllu` file in place

**`validate`:**
**Inputs:** `--corpus PATH` 
**Options:** `--lang CODE  --validator PATH`
**Output:** Prints validation results.  

**`delete`:**  
**Inputs:** `--corpus PATH  --id N`
**Options:** none
**Output:** Removes the specified sentence from `.conllu` file.  

### Examples

**Example 1:** Add a CG3 output file into a corpus  
```bash
python3 -m scripts.corpus_cli add \
  --cg3-file data/results/sample_output.cg3 \
  --corpus data/results/ojibwe_treebank.conllu
```
Converts `sample_output.cg3` into CoNLL-U format and appends it to `ojibwe_treebank.conllu`, then runs UD validation.

**Example 2:** Validate an existing corpus  
```bash
python3 -m scripts.corpus_cli validate \
  --corpus data/results/ojibwe_treebank.conllu
```
Checks `ojibwe_treebank.conllu` for UD compliance using the validator script.

**Example 3:** Delete a sentence by `sent_id`  
```bash
python3 -m scripts.corpus_cli delete \
  --corpus data/results/ojibwe_treebank.conllu \
  --id 3
```
Deletes the sentence with `sent_id = 3` from the corpus and renumbers the rest.

--- 

### Booklets CLI (Render HTML booklets)

This tool generates **HTML booklets** that visualize disambiguation or dependency parses for Ojibwe text.  
The script is located at `scripts/ojcg_booklets.py`.

There are two subcommands:  
1. `build-disambig` – Creates a before/after booklet showing the raw CG3 disambiguation and the disambiguated output.  
2. `build-dep` – Creates a dependency booklet with SVG visualizations of parses (using spaCy’s displacy).


**Inputs required:**

For `build-disambig`:  
  - `--oj PATH  --en PATH  --grammar PATH  --fst PATH  --out PATH  --title TEXT`

For `build-dep`:  
  - `--treebank PATH  --oj PATH  --en PATH  --out PATH  --title TEXT`  
  - If using `--reparse`, also: `--grammar PATH  --fst PATH`

**Outputs:**  
- `build-disambig` – An HTML file showing each sentence with its raw CG3 analysis and disambiguated version.  
- `build-dep` – An HTML file showing dependency parse trees as interactive SVG diagrams.  

### Examples 

**Example 1:** Build a disambiguation booklet  
```bash
python3 -m scripts.ojcg_booklets build-disambig \
  --oj data/parallel/oj.txt \
  --en data/parallel/en.txt \
  --grammar data/rules/disambiguation.cg3 \
  --fst data/fst/ojibwe.att \
  --out data/results/disambig_booklet.html \
  --title "Disambiguation Booklet"
```
Creates an HTML file showing before/after disambiguation for each sentence.

**Example 2:** Build a dependency booklet from an existing treebank  
```bash
python3 -m scripts.ojcg_booklets build-dep \
  --treebank data/results/sample_dependency.conllu \
  --oj data/parallel/oj.txt \
  --en data/parallel/en.txt \
  --out data/results/dep_booklet.html \
  --title "Dependency Booklet"
```
Uses an existing CoNLL-U file to render dependency trees as SVGs.

**Example 3:** Re-parse text and build a fresh dependency booklet  
```bash
python3 -m scripts.ojcg_booklets build-dep \
  --treebank data/results/sample_dependency.conllu \
  --oj data/parallel/oj.txt \
  --en data/parallel/en.txt \
  --out data/results/dep_booklet_reparse.html \
  --title "Dependency Booklet (Reparsed)" \
  --reparse \
  --grammar data/rules/dependency.cg3 \
  --fst data/fst/ojibwe.att
```
Re-runs CG3 on the Ojibwe text, regenerates the `.conllu` treebank, and produces a new dependency booklet.