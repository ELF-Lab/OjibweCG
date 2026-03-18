# Ojibwe Constraint Grammar

Welcome! This repository hosts the Ojibwe constraint grammar project.

## What is this?
This project develops two unique grammars for the Ojibwe language: one for morphological disambiguation, and one for syntactic dependency parsing.

This page is mainly an index to the repository and to the documentation. Linguistic background, usage instructions, and other notes are all in the [`documentation/`](documentation/) folder, as detailed below. 

## Repository Overview

- [`data/`](./data) – Data and outputs generated from most of the code in the repository
- [`documentation/`](./documentation) – Documentation and examples
- [`evaluation/`](./evaluation) – Creation and evaluation of the gold standard for disambiguation and dependency parsing 
- [`scripts/`](./scripts) – Collection of scripts for running the modules from the CLI 
- [`src/`](./src) – Main modules and helper files  
- [`tests/`](./tests) – Regression tests for disambiguation
- [`ud-tools/`](./ud-tools) – Third-party repository with the UD CoNLL-U format validator



## Documentation Overview  

- [`01_overview.md`](documentation/01_overview.md) – project goals and scope  
- [`02_usage.md`](documentation/02_usage.md) – installation and running examples  
- [`03_grammar_modules.md`](documentation/03_grammar_modules.md) – explanation of the 2 CG modules
- [`04_examples.md`](documentation/04_examples.md) – examples for disambiguation and dependency applications
- [`05_work_in_progress.md`](documentation/05_work_in_progress.md) – next steps and current limitations of the project
- [`06_references_and_credits.md`](documentation/06_references_and_credits.md) – summary of references and contributions to the project
