# Project Overview  
Context and short examples for both the disambiguation and the dependency parsing modules. 

## Contents
- [Project Overview](#project-overview)
  - [Contents](#contents)
  - [Overview of the Disambiguation Module](#overview-of-the-disambiguation-module)
    - [Project Goals: The Big Picture](#project-goals-the-big-picture)
    - [At a glance: What does the FST do?](#at-a-glance-what-does-the-fst-do)
    - [What is CG3?](#what-is-cg3)
      - [CG3 Input \& Output](#cg3-input--output)
      - [Disambiguation in CG3](#disambiguation-in-cg3)
    - [What is the purpose of disambiguation?](#what-is-the-purpose-of-disambiguation)
      - [Disambiguation for the Ojibwe corpus](#disambiguation-for-the-ojibwe-corpus)
      - [Disambiguation for dependency parsing](#disambiguation-for-dependency-parsing)
      - [Disambiguation for other uses](#disambiguation-for-other-uses)
  - [Overview of the Dependency Parsing Module](#overview-of-the-dependency-parsing-module)
    - [Project Goals Continued: How did this come about?](#project-goals-continued-how-did-this-come-about)
    - [What is CoNLL-U Format?](#what-is-conll-u-format)
    - [How CG3 enables dependency parsing](#how-cg3-enables-dependency-parsing)
      - [Full example (English)](#full-example-english)
    - [Current focus and limitations](#current-focus-and-limitations)
    - [Why build a treebank?](#why-build-a-treebank)
  - [Sources and further reading](#sources-and-further-reading)


## Overview of the Disambiguation Module

We will first begin by introducing the disambiguation module. This is where development started, and is currently at a higher level of completion compared to the dependency module.

### Project Goals: The Big Picture  
Before exploring the purpose and functionality of the constraint grammar module, an important step is to understand where the module situates itself in the context of the wider project. 

One of the main objectives of the project is to build a corpus of morphologically tagged Ojibwe texts to serve as a linguistic database for anyone working with the Ojibwe language. The initial step to realizing this is to collect Ojibwe text from various sources, such as books, journals, transcriptions, and elicitations with Ojibwe speakers. The next key step, to realize the *morphologically tagged* goal of the corpus, is to parse the various texts using the FST module, which produces all possible morphological analyses of each word (see the [example below](#at-a-glance-what-does-the-fst-do)).

This next step is where the constraint grammar (or more specifically the disambiguation module) steps in. Once the FST parses the text and outputs the morphological analyses of words, the disambiguation module is used to remove unwanted morphological readings from words with more than one reading. These unwanted readings could be always unwanted, such as cases of overparsing by the FST which is easier fixed in the constraint grammar, or they could be cases of genuine morphological ambiguity which need to be disambiguated through context. 

The high-level pipeline with disambiguation looks like this: 

```Text → FST analyses → Constraint Grammar (disambiguation) → Corpus```

This gives some background on where the disambiguation module lives in the wider context of the project. Later sections will show concrete examples of how it works in practice.

### At a glance: What does the FST do? 

To understand the purpose and functionality of the constraint grammar, it is important to first understand what the FST module does.

The core functionality of the Ojibwe FST is to take an Ojibwe word and to decompose it into morphological tags. This is better understood through a short example:

**Ojibwe word:** 
mazina'igan - book, letter, paper ([OPD entry](https://ojibwe.lib.umn.edu/main-entry/mazina-igan-ni))

**FST analyses:** 

1. `mazina'igan+NA+ProxSg`

2. `mazina'igan+NI+Sg`

**Tag Glosses:**  

| Tag     | Meaning         |  
|---------|-----------------|  
| NA      | Noun Animate    |  
| NI      | Noun Inanimate  |  
| ProxSg  | Proximate       |  
| Sg      | Singular        |  



Here we see that the word mazina'igan gets two parses by the FST, both of which share the lemma 'mazina'igan'. (1) is parsed as an animate proximate singular noun and (2) is parsed as an inanimate singular noun. An important thing to remember is that the FST works at the word-level, meaning that it will always output all analyses possible for a given word.

Remembering that our goal is to disambiguate such readings with multiple analyses, in the next section we’ll see how constraint grammar resolves this ambiguity automatically.  

*Note*:
You can find much more detailed documentation on the FST and its outputs in the FST module [here](https://github.com/ELF-Lab/OjibweMorph). Its sibling repository [FSTmorph](https://github.com/ELF-Lab/FSTmorph) also has useful documentation.



### What is CG3?  
Constraint Grammar (CG) is a framework for rule-based disambiguation and syntactic annotation. In short, CG works by applying a sequence of linguistically motivated constraints to an input text. For disamguation, these constraints eliminate analyses that are incompatible with the surrounding context, while keeping the analyses that best fit. For syntactic annotation (or dependency parsing), CG rules can also assign grammatical functions such as subject, object, or modifier. This is done by looking at the surrounding context in much the same way as disambiguation rules, but instead of removing readings, the rules add functional tags that describe how words relate to each other. In this way, CG can serve as both a disambiguator and a lightweight dependency parser.

The version of the framework used here is **VISL CG-3** (or simply CG3), which is a modern implementation developed at the University of Southern Denmark. It provides a rule language and an efficient parser for writing and applying grammars.  

#### CG3 Input & Output
CG3 works with lines where each token is followed by one or more possible analyses. The format looks roughly like this:

```cg3
"<wordform>"
   "lemma" Tag1 Tag2
```

For example, if we were only to encode parts of speech, the word *document* could appear as:

```cg3
"<document>"
   "document" N
   "document" V
```

CG3 rules then operate over this structure, removing or keeping analyses.

#### Disambiguation in CG3

To disambiguate readings, CG3 rules look at windows of context around a target word and decide whether to remove (or keep) certain readings. 

While the following example is only two words, in case of longer or multiple sentences, context windows are bounded by delimiters such as punctuation marks, which you can define explicitly in the grammar (e.g., periods, commas, quotation marks). This means a rule will not parse across a delimiter, so context checks are always local to a clause or sentence.

A simple example to illustrate disambiguation in CG3:

**Input:**  
```cg3
"<the>"
   "the" Det
"<document>"
   "document" N
   "document" V
```

**CG3 rule:**
```
REMOVE V IF (-1 ("the")) ; # If preceded by "the", remove verb reading
```

**Output (after rule application):**  
```
"<the>"
   "the" Det
"<document>"
   "document" N
```

Here, the word *document* has two possible readings, noun or verb.
The rule says: if the previous word is *the*, then remove the verb reading.
So in the phrase “the document", *document* is correctly resolved as a noun.

This example is mainly to show how ambiguous morphological readings can be disambiguated using context, but it's important to remember that sentences in English and Ojibwe are made up of many words, often with more than one ambiguity. In practice, CG3 grammars contain hundreds of such rules, layered in a pipeline to gradually narrow down analyses. 

This was a very simple overview on disambiguation in CG3, to better understand the details behind the disambiguation and dependency modules built in this project, check the [overview of the grammar modules](documentation/03_grammar_modules.md) portion of the documentation.

*Note*:  
Much more detailed documentation on the CG3 formalism and parser can be found in the [VISL CG-3 manual](https://edu.visl.dk/cg3/single/).
.

### What is the purpose of disambiguation?

Above we have seen an introduction to how disambiguation works. But its purpose might still not be apparent - why do we want words to be disambiguated?

To give an answer to this question, pertaining to this project, we consider the three following questions: 

1. What is the disambiguation doing for the corpus?
2. What is disambiguation doing for dependency parsing?
3. What are the other uses of disambigation?

#### Disambiguation for the Ojibwe corpus
The first purpose of disambiguation in this project is to make the Ojibwe corpus consistent and reliable. The corpus is not only a collection of example sentences; it is a databse that should be searchable at the level of morphological annotation. Since the FST always outputs all possible analyses for a given word, leaving those analyses unresolved would mean the corpus is full of unwanted ambiguities. For example, a single word could be tagged as both animate and inanimate, or as both a noun and a verb. Disambiguation ensures that each word that can be resolved in context has a single, context-appropriate analysis. 

One thing to keep in mind is that it might not always be possible to disambiguate each word even in context, just like in the classic English example *We saw her duck*. Here, *duck* could be morphologically parsed as a noun and as a verb, and we would not be able to disambiguate it based on context. 

Ojibwe contains similar cases. For example, the word *ikwewan* can be parsed as either:  

- `ikwe+NA+ObvSg`
- `ikwe+NA+ObvPl`

Both analyses are grammatically possible, and the ambiguity cannot always be resolved from context. This kind of `ObvSg` / `ObvPl` ambiguity is common for many obviative noun forms, due to the fact that obviative demonstratives and verbs with obviative arguments show the same ambiguity with respect to number. In cases like this, we do not expect the disambiguation module to remove the ambiguity, since it is linguistically valid and should remain as part of the corpus.

#### Disambiguation for dependency parsing 
Another main use of the disambiguation module in this project is as the foundation for dependency parsing. Unambiguous morphological readings are necessary for correct syntactic dependencies to be assigned.

For example, when building a dependency tree we must first know whether a word is a verb or a noun, since each behaves very differently in syntactic structure. A verb does verb stuff: it heads the clause, finds its arguments, and links to other clauses. A noun does noun stuff: it combines with determiners, serves as the subject or object of a verb, and can head relative clauses.  

Disambiguation ensures that words are assigned the correct morphological category, allowing the dependency grammar to correctly model these relationships.

#### Disambiguation for other uses
Beyond the corpus and dependency parsing, disambiguation can also support language technology applications. For example, it could improve the quality of tools like spell-checkers, predictive text, or machine translation. These uses are not part of the current project, but they highlight the broader potential of a disambiguation model for the Ojibwe language.



 
## Overview of the Dependency Parsing Module

The following sections provides background on the goals and functionality of the dependency parsing module.

### Project Goals Continued: How did this come about?

As mentioned above, the original goal of the project was to build an Ojibwe corpus, using CG3 to disambiguate the morphological readings produced by the FST. During this process, it became clear that CG3 could also be extended beyond disambiguation. In addition to removing unwanted morphological readings, CG3 has the capacity to assign syntactic functions (such as subject, object, or determiner) based on context.  

This opened up an equally exciting direction for the project: the possibility of building an Ojibwe treebank. To our knowledge, there is currently no treebank for any Algonquian language, which makes this work both novel and linguistically valuable.  

In this project, CG3 provides the initial modeling of syntactic dependencies. The output is then passed through post-processing modules to convert it into the CoNLL-U format, the widely used standard for treebank data. 

Here is a visualization for how the project pipeline with dependency parsing looks:

```
Text → FST → CG3 (disambiguation) → Corpus
                     ↓
                CG3 (dependency parsing) → Treebank (CoNLL-U)
```

 The next section gives a brief introduction to CoNLL-U and its role in treebanking.



### What is CoNLL-U Format?  

CoNLL-U is the standardized format used in the [Universal Dependencies](https://universaldependencies.org/format.html) project for representing sentences with token-level annotations. It makes treebank data both human-readable and machine-readable, which is why it has become the standard for building and sharing treebanks across languages.  


In the CoNLL-U format, each word in a sentence appears on its own line, with columns giving information such as the word’s form, lemma, part of speech, and syntactic relation. Here is a simple example:


**Example: “He shredded the document”**
```text
ID  FORM       LEMMA      UPOS   XPOS  FEATS  HEAD  DEPREL  DEPS  MISC
1   He         he         PRON   _     _      2     nsubj   _     _
2   shredded   shred      VERB   _     _      0     root    _     _
3   the        the        DET    _     _      4     det     _     _
4   document   document   NOUN   _     _      2     obj     _     _
```

As can be seen, CoNLL-U encodes syntactic relationships between words, and additionally records information such as the lemma and the part of speech (UPOS above) of each word. Not all columns are used, a full overview of the format is [available here](https://universaldependencies.org/format.html). 


### How CG3 enables dependency parsing

Just as CG3 disambiguation rules remove unwanted morphological readings, CG3 also allows for the assignment of dependencies within the grammar itself. This is done with rules such as `SETPARENT` and `SETCHILD`, which establish hierarchical relations between tokens.

It’s important to note that `SETPARENT` rules only create the structural links (links between words). To assign the actual dependency relation label (e.g., subject, object, determiner), a corresponding `ADD` rule is used. Together, the structural links, relation tags, and part-of-speech information give us a full dependency tree. From there, a post-processing module can be used to convert the CG3 output into the CoNLL-U format required for treebanks.
 

#### Full example (English)
The following example illustrates the way CG3 can be used for dependency parsing as explained above. The corresponding .cg3 file, with the full set of rules, can be found in [CG3_examples/simple_english_dependency.cg3](CG3_examples/simple_english_dependency.cg3).

The example sentence we will go through is *He shredded the document.*. The following shows the input and the output of the CG3, and only one pair of SETPARENT and ADD rules, for the object (parsed as @obj) dependency. 

**Input:**  
```cg3
"<He>"
    "he" PRON
"<shredded>"
    "shred" V
"<the>"
    "the" DET
"<document>"
    "document" N
```

**CG3 rule (for Object dependency):**  
```cg3
# Assign Object
SETPARENT (N) (-2 V) IF (-1 Det) ; # If a noun is preceded by a determiner, and two words to the left is a verb, set that verb as the parent of the noun.

# Object relation
ADD obj N IF (-1 DET) (-2 V) ;
```
**Output:**
```cg3
"<He>"
   "he" PRON @nsubj #1->2 SETPARENT:21 ADD:33
"<shredded>"
   "shred" V #2->2
"<the>"
   "the" DET @det #3->4 SETPARENT:18 ADD:30
"<document>"
   "document" N @obj #4->2 SETPARENT:24 ADD:36"<.>"
```


In the output, each token retains its morphological analysis, but now also carries dependency information. For example, *document* (token #4) has been linked to *shredded* (token #2) as its parent, indicated by `#4->2` tag. The dependency relation label is also present for each token for which a dependency was parsed, with exception to *shredded*, which will be given the relation label `root` in post-processing, since it has no dependency to any other token, and is therefore the root of the clause.

 The numbers represent the token indices, and the extra annotation records which rule applied (e.g., `SETPARENT:24`, `ADD:36`). With the part of speech, dependency link, and dependency relation labels present on each token, this CG3 output is ready to be converted into CoNLL-U format, which would result in the CoNLL-U table shown above in [What is CoNLL-U Format?](#what-is-conll-u-format) .

### Current focus and limitations

The end-goal of the dependency parsing model would be to build a complete Ojibwe treebank. However, the current stage of the project focuses mainly on argument structure, which consists of parsing the following two types of dependencies:

- linking verbs to their arguments, and

- ensuring that arguments (such as noun phrases) are parsed to completion.

At this stage, the grammar has less coverage for dependencies that are not directly relate to argument strcuture, such as dependencies for adverbs or for relationships between matrix and embedded clauses. These are important steps for the future, but for now the emphasis is on getting a reliable model of argument structure as the foundation for a larger treebank.

### Why build a treebank?

It might not be inherently obvious why building a Ojibwe treebank is a worthwhile task. Here is a small overview of the answer to this question. 

Treebanks are valuable resources for both computational and theoretical linguistics. An Ojibwe treebank would provide the following capabilities:

- A structured dataset to answer syntactic questions, such as how arguments are realized in Ojibwe (e.g., how often objects appear compared to subjects, or what the rate of overt arguments is).

- A way to compare Ojibwe syntax to other languages in the Universal Dependencies framework.

- A starting point for applications in natural language processing and language technology.

Our project’s immediate goal is a working grammar and treebank model. Once this is in place, it will open up opportunities to ask and test more theoretical questions about Ojibwe syntax.


## Sources and further reading

The following is a summary of links to the sources used in the creation of this part of the documentation, all of which are great resources for further reading. For detailed academic references and credits, see the [References & Credits](06_references_and_credits.md)
 section.

- [Ojibwe People’s Dictionary (OPD)](https://ojibwe.lib.umn.edu/) — Source for lexical entries and example words.  
- [OjibweMorph (ELF Lab GitHub repository)](https://github.com/ELF-Lab/OjibweMorph) — Finite-state transducer for Ojibwe morphology, used to generate word-level analyses.  
- [FSTmorph (ELF Lab GitHub repository)](https://github.com/ELF-Lab/FSTmorph) — Sister repository containing more detailed FST documentation.  
- [VISL CG-3 Manual](https://edu.visl.dk/cg3/single/) — Official documentation for the CG3 language.  
- [Universal Dependencies (UD) Homepage](https://universaldependencies.org/) — Homepage for the UD project, with much more specific information on UD.
- [Universal Dependencies (UD) Format Specification](https://universaldependencies.org/format.html) — Standard reference for the CoNLL-U format and guidelines for treebanking.  

