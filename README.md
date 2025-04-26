# Ojibwe Constraint Grammar

[Work in progress]

Constraint Grammar (CG3) rules are applied in Ojibwe language with 2 broad purposes:

### Disambiguation: 
there are cases that a verb or a noun can have multiple FST (Finite State Transducer) readings, and we can apply rules to determine which readings are likely to be correct, using the context of surround words. In general, demonstrative pronouns, nouns and verbs in Ojibwe agree on number (singular/plural), animacy (animate/inanimate) and obviation (proximate/obviative). We can disambiguate many cases using these rules. 

### Dependency parsing: 
also based on the agreement in number, animacy and obviation, we can analyze which nouns can be subject or object of which verb. From there, we can build relationships (dependencies) between the nouns and verbs.

### Contributors:
- Christopher Hammerly
- Tran Minh Nguyen
- Matthias Diederichsen
