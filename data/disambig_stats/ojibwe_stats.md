|-------------------|---------|
| total words       | 208     |
| readings before   | 309     |
| readings after    | 248     |
| analyses removed  |  61     |
| ambiguity removed |   0.457 |
| ambiguous before  |   0.389 |
| ambiguous after   |   0.212 |

| type    |   words b |   words a |   readings b |   readings a |   removed |   avg b |   avg a |
|---------|-----------|-----------|--------------|--------------|-----------|---------|---------|
| verb    |        81 |        78 |          152 |          110 |        42 |    1.88 |    1.41 |
| pronoun |        27 |        27 |           41 |           34 |         7 |    1.52 |    1.26 |
| noun    |        50 |        47 |           71 |           60 |        11 |    1.42 |    1.28 |
| adverb  |        33 |        33 |           34 |           33 |         1 |    1.03 |    1    |
| other   |        24 |        24 |           24 |           24 |         0 |    1    |    1    |

|--------------|----|
| lemma amb.   |  4 |
| preverb amb. | 12 |
| POS amb.     |  0 |
| morpho amb.  | 28 |

| top tokens                |   count |
|---------------------------|---------|
| iniwen                    |       3 |
| iniw                      |       3 |
| dazhwegisidoon            |       1 |
| ji-baateg                 |       1 |
| ji-bengwashkising         |       1 |
| gichi-mandaamini-gitigaan |       1 |
| gaa-izhinamogwen          |       1 |
| gaa-ozhibii'igaadeg       |       1 |
| niijikiwenh               |       1 |
| ogii'-ondamiikawaan       |       1 |
| odoodaabaanan             |       1 |
| gaa-onji-bezikaad         |       1 |
| bakwezhiganan             |       1 |
| gii-izhise                |       1 |
| gaa-izhi-gawised          |       1 |
| ji-o-miigaazod            |       1 |
| owaazakonendamowaan       |       1 |
| aaba'amaw                 |       1 |
| gaa-bwaanawichiged        |       1 |
| obwaamaan                 |       1 |
| ji-manisaagod             |       1 |
| odawemaan                 |       1 |
| miginaad                  |       1 |
| ini                       |       1 |
| makwan                    |       1 |
| gaa-ategin                |       1 |
| ozaagi'aan                |       1 |
| ookomisan                 |       1 |
| ogii-aabiinji'aawaan      |       1 |
| obimibizoni'aan           |       1 |
| daashkiboojiganan         |       1 |
| ogii-oninaan              |       1 |
| waabiganan                |       1 |
| gaa-biboong               |       1 |
| ji-o-ganawendaawasod      |       1 |
| owiidanokiimaan           |       1 |
| ininiwan                  |       1 |
| odasabiin                 |       1 |
| gaa-onji-bwaanawitooyaan  |       1 |
| ji-gopiiyaan              |       1 |

# POS-level patterns

# Lemma patterns

| POS   | pattern                   |   tokens | examples ≤3      |
|-------|---------------------------|----------|------------------|
| verb  | izhinam vs izhinan        |        1 | gaa-izhinamogwen |
| verb  | asab vs odasabii          |        1 | odasabiin        |
| noun  | iijikiwenhy vs iijikiweny |        1 | niijikiwenh      |
| noun  | dawemaa vs dawemaaw       |        1 | odawemaan        |

# Preverb patterns

| POS   | pattern                                                |   tokens | examples ≤3                                              |
|-------|--------------------------------------------------------|----------|----------------------------------------------------------|
| verb  | PVSub/gaa vs PVTense/gii                               |        6 | gaa-ozhibii'igaadeg, gaa-onji-bezikaad, gaa-izhi-gawised |
| verb  | PVTense/daa vs PVTense/ga                              |        4 | ji-bengwashkising, ji-o-miigaazod, ji-o-ganawendaawasod  |
| verb  | PVTense/daa vs PVTense/daa vs PVTense/ga vs PVTense/ga |        2 | ji-baateg, ji-manisaagod                                 |

# Morphological patterns

| POS     | pattern                         |   tokens | examples ≤3                                         |
|---------|---------------------------------|----------|-----------------------------------------------------|
| verb    | 3PlObvObj | 3SgObvObj           |        9 | ogii'-ondamiikawaan, owaazakonendamowaan, obwaamaan |
| noun    | ObvPl | ObvSg                   |        7 | odoodaabaanan, bakwezhiganan, makwan                |
| pronoun | ObvPl | ObvSg                   |        7 | iniwen, iniw, ini                                   |
| verb    | 0PlObj | 0SgObj                 |        2 | dazhwegisidoon, gaa-onji-bwaanawitooyaan            |
| verb    | 0SgSubj | 3SgProxSubj           |        1 | gii-izhise                                          |
| verb    | 3PlProxObj | 3SgProxObj         |        1 | aaba'amaw                                           |
| noun    | 2SgPoss,PNLex/chi | PNLex/gichi |        1 | gichi-mandaamini-gitigaan                           |