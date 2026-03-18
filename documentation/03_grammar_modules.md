# Grammar Modules  

In the following sections, we will take a close look at both grammar modules, and introduce their concrete structure and functionality. 

## The Ojibwe disambiguation grammar  

We will start by giving a brief overview of the disambiguation module, and then take a deeper dive into what each section accomplishes in terms of the larger goal of morphological disambiguation. 

The disambiguation grammar can be split into 4 sections.

1. Set definitions
2. Initial blanket (context-independent) constraints
3. Context-dependent constraints
4. Final blanket constraints

We will go through each of the 4 sections in detail.

### Set definitions

The grammar begins with set definitions, which group morphological tags outputted by the FST parser into natural groups that the CG can make reference to. 

For instance, it may be useful to reference all verbs that encode an animate subject. This set is created by the following CG code:

```
LIST SG_AN_SUBJECT = 3SgProxSubj 3SgObvSubj ;
LIST PL_AN_SUBJECT = 3PlProxSubj 3PlObvSubj ;
SET AN_SUBJECT = SG_AN_SUBJECT OR  PL_AN_SUBJECT ;
```

Intuitively, the set of verbs that encode animate subjects is a combination of those that encode singular animate subjects and those that encode plural animate subjects. Note that this set does not make reference to non-third person animates, as the set is currently only used to disambiguate verbs that show animacy ambiguity in the third person, as in the case of a VAI/VII ambiguity. 

### Initial blanket constraints

Blanket constraints are defined before context-dependent constraints to remove spurious analyses from the FST that may cause issues in disambiguation downstream. For instance, an impersonal VII verb *waabang* `it is tomorrow' is superficially ambiguous between a singular and plural inanimate subject, but such impersonal verbs can only semantically take a singular subject. The rule that disambiguates these is the following:

```
REMOVE:rem_pl_for_impersonal_verbs (0PlSubj) IF (0 IMPERSONAL_VERB)  ;
```
Where `IMPERSONAL_VERB` is a set defined in the above set definitions.



### Context-dependent constraints
The context-dependent constraints is by far the most substantial section in the disambiguation grammar, and these can be further split into context-dependent constraints for verbs, nouns, demonstratives, and adverbs.

A canonical context-dependent constraint is one of verb paradigm disambiguation. The intransitive verb *bapangigaa* 'it leaks' is ambiguous between a VAI (animate subject) and VII (inanimate subject) reading. With the subject overtly realized, we can use it to disambiguate between these readings, as shown in the following case:

**Input:**  
```cg3
"<bapangigaa>"
    "bapangigaa" VAI Ind Pos Neu 3SgProxSubj
;   "bapangigaa" VII Ind Pos Neu 0SgSubj
"<’aw>"
    "’aw" PRONDem NA ProxSg
"<akik>"
    "akik" NA ProxSg
```

The sentence *bapangigaa 'aw akik* meaning 'that pail leaks' has the subject ('that pail' = *'aw akik*) overtly realized, thus allowing us to remove the VII reading and successfully disambiguate the verb.


### Final blanket constraints

Final blanket constraints are specified in cases where we want the contextual disambiguation to run first, and then do a final "clean-up" of unresolved ambiguities. One such example is selecting the maximally lexicalized form of verbs/nouns. 

One such example is *ishkodens*, being the diminuitive form of *ishkode* meaning 'fire'. While the FST outputs a `Dim` analysis, there is also a separate fully lexicalized form of *ishkodens*, as its literal interpretation is 'match'. 

The reason we place these constraints at the end is to avoid edge cases where we may have a verb-noun ambiguity, where we want the disambiguation to select the correct POS before choosing the maximally lexicalized form.


## The Ojibwe dependency grammar

The dependency module adds another layer of functionality to the system, taking the morphological information in words and assigning dependencies to model syntactic structure. 


The dependency grammar can be split into 5 sections: 

1. Set definitions and tag additions
2. Nominal dependency parsing
3. Verbal dependency parsing
4. Other dependencies
5. Post-processing

We will go through each section briefly. 

### Set definitions and tag additions

Dependency grammar set definitions mostly parallel those of the disambiguation grammar, as there are natural classes of tags that we want to refer to in the constraints. One extra set defined here is the mapping of FST tags to the UD-designed CoNLL-U tags, as we align the output of the dependency grammar with the UD format. 

### Nominal dependency parsing

Nominal dependencies are parsed before verbal dependencies as these are more local, and so we take a "smaller constituent first" approach, which improves the accuracy of the grammar. 

For example, here we parse the dependency between demonstratives and nouns, which function similarly to an English demonstrative and noun. One example is the nominal phrase *awedi mitig* 'that tree over there', which is parsed as follows:

```
"<awedi>"
    "awedi" PRONDem NA ProxSg @det DET #1->2
"<mitig>"
    "mitig" NA ProxSg #2->2
```

We also parse nominal dependencies linking numerals and RCs to their head nouns in this section.

### Verbal dependency parsing

The verbal dependency parsing section links nominal arguments to agreeing verbs. This is perhaps the most common type of dependency. For instance, the sentence *nimiijinan ziinzibaakwadoonsan* 'I'm eating some candies' is parsed as follows.

```
"<nimiijinan>"
	"miijin" VTI Ind Pos Neu 1SgSubj 0PlObj VERB #1->1
"<ziinzibaakwadoonsan>"
	"ziinzibaakwadoons" NI Pl @obj NOUN #2->1
```

Here the inanimate plural noun is linked to the verb with the `@obj` relation.

### Other dependencies

Other dependencies we currently handle are linking certain adverbials to verbs, linking negative particles to verbs, and linking sentential particles to verbs. 

### Post-processing

In the post-processing stage we add a mapping of the POS tags outputted by the FST to those specified by the UD format. This mapping is summarized in the table below:

| CoNLL-U Column | Source in CG Output |
| --- | --- |
| ID  | Token index |
| FORM | Surface form |
| LEMMA | FST lemma |
| UPOS | From FST + post-processing |
| XPOS | From FST tags |
| HEAD | From SETPARENT |
| DEPREL |  From ADD |
| FEATS | n/a |
| DEPS | n/a |
| MISC | n/a |