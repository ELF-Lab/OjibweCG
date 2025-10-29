# Testing  

The `test/` folder currently only contains tests for the disambiguation component of the project. Tests for the dependency portion are in development.

## Disambiguation Tests

Disambiguation tests take an indexed list of unparsed Ojibwe sentences and, after parsing, compare them to the expected CG3 output.  

These tests should be run when updates are made to data/rules/disambiguation.cg3 (LINK!) to ensure existing functionality is unchanged. 

The expected output can be updated, and test cases can be added to sentences.ojib. 

### Structure
- `data/` — contains the input sentences and the expected (gold) CG3 output.
- `test_disamb.py` — main test functionality.
- `util.py` / `conftest.py` — helper functions and fixtures.


### Running the Tests

To test against the current regression set (last updated Aug. 15 2025), run:
``` 
pytest
```

To update the expected sentences, run:
``` 
pytest --update-gold
```
