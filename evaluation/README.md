Please run the evaluation notebooks in the following order:
- `01_data_preprocessing.ipynb`: to use FST parser to parse Ojibwe sentences, and convert to CG3 readings format
- `02_disambiguation_evaluation.ipynb`: to run CG3 disambiguation, and compare with gold results

Please note that there are 2 different CG3 grammar files:
- `Ojibwe_disambiguation.cg3`: contains disambiguation rules, but not dependencies and Subject / Object tags assignment
- `Ojibwe_dependency_parsing.cg3`: contains rules for both disambiguation, Subject/Object assignment AND dependency parsing. 

For the purpose of disambiguation evaluation, we use the `Ojibwe_disambiguation.cg3` grammar file.