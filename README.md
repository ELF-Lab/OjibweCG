# Ojibwe Constraint Grammar

[Work in progress]

Constraint Grammar (CG3) rules are applied in Ojibwe language with 2 broad purposes:

### Disambiguation: 
there are cases that a verb or a noun can have multiple FST (Finite State Transducer) readings, and we can apply rules to determine which readings are likely to be correct, using the context of surround words. In general, demonstrative pronouns, nouns and verbs in Ojibwe agree on number (singular/plural), animacy (animate/inanimate) and obviation (proximate/obviative). We can disambiguate many cases using these rules. 

### Dependency parsing: 
also based on the agreement in number, animacy and obviation, we can analyze which nouns can be subject or object of which verb. From there, we can build relationships (dependencies) between the nouns and verbs.

### CG3 Dependency Rules

#### Noun/Demonstrative - Verb relations
1. For each noun or demonstrative, find the closest verb (VTA/VTI/VAI/VAIO/VII) on either side
2. Check if the verb argument morphology agrees in number, person, and obviation
3. If agreeing, create a named relation (Dep_Subject, Dep_Object) from noun/demonstrative to verb
4. Stop search on both sides at the nearest verb

#### Demonstrative - Noun relations
1. If a noun immediately follows a demonstrative, remove any relations added by Dem - Verb search
2. Add a named relation (Dep_Dem) from demonstrative to following noun

### FST -> UD UPOS Mapping
This mapping converts part-of-speech tags produced by the Ojibwe FST into Universal Part-of-Speech (UPOS) tags, following the UD v2 standard:

| FST Tag | UD UPOS |
| ------- | ------- |
| ADVNeg  |   ADV   |
| ADVQnt  |   ADV   |
|  VTA    |   VERB  |
|  VTI    |   VERB  |
|  VAI    |   VERB  |
|  VAIO   |   VERB  |
|  VII    |   VERB  |
|   NA    |   NOUN  |
|   NI    |   NOUN  |
| PRONDem |   DET   |
|    .    |   PUNCT |

### CG3 Relation -> UD DEPREL Mapping
Once dependency relations have been assigned using CG3 rules, relation fragments are mapped to Universal Dependency relation labels (DEPREL).

| CG3 Relation | UD DEPREL |
| ------------ | ---------
|     Subj     |   nsubj   |
|     Obj      |   obj     |
|     Adv      |   advmod  |
|     Dem      |   det     |
|     punct    |   punct   |


### Contributors:
- Christopher Hammerly
- Tran Minh Nguyen
- Matthias Diederichsen
