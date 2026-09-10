from __future__ import annotations

from collections import Counter, defaultdict
from pathlib import Path

from conllu import parse_incr


VERB_PARADIGMS = ("VAIO", "VAIPL", "VIIPL", "VTA", "VTI", "VAI", "VII")
VERB_ORDERS = ("Ind", "Cnj", "Imp", "Pcp")
VERB_MODES = ("Neu", "Prt", "Dub", "DubPrt", "Sim", "Del", "Prb")
POLARITIES = ("Pos", "Neg")

ORDER_SYMBOLS = {
    "nsubj": "S",
    "obj": "O",
    "iobj": "I",
}


def get_token_statistics(corpus_path):
    upos_counts = Counter()
    word_forms = set()
    lemmas = set()
    token_count = 0
    word_count = 0

    with open(corpus_path, encoding="utf-8") as corpus_file:
        for sentence in parse_incr(corpus_file):
            for token in sentence:
                if not is_real_token(token):
                    continue

                token_count += 1
                upos = token.get("upos") or "_"
                upos_counts[upos] += 1

                if upos != "PUNCT":
                    word_count += 1
                    form = token.get("form")
                    lemma = token.get("lemma")
                    if form:
                        word_forms.add(form.casefold())
                    if lemma and lemma != "_":
                        lemmas.add(lemma.casefold())

    return {
        "token_count": token_count,
        "word_count": word_count,
        "punctuation_count": upos_counts["PUNCT"],
        "unique_word_forms": len(word_forms),
        "unique_lemmas": len(lemmas),
        "upos_counts": upos_counts,
    }

def is_real_token(tok) -> bool:
    return isinstance(tok.get("id"), int)

def xpos_parts(tok) -> set[str]:
    return set((tok.get("xpos") or "").split("|"))

def build_children(sent):
    children = defaultdict(list)
    for tok in sent:
        if is_real_token(tok) and isinstance(tok.get("head"), int):
            children[tok["head"]].append(tok)
    return children

def token_index(sent):
    return {tok["id"]: tok for tok in sent if is_real_token(tok)}

def get_subtree(tok_id, children):
    descendants = []
    for child in children.get(tok_id, []):
        descendants.append(child)
        descendants.extend(get_subtree(child["id"], children))
    return descendants


def get_argument_expression(argument_tok, children):
    return [argument_tok] + get_subtree(argument_tok["id"], children)


def expression_text(expression) -> str:
    return " ".join(
        tok.get("form", "")
        for tok in sorted(expression, key=lambda tok: tok["id"])
    )

def argument_relative_position(argument_tok, argument_expression) -> str:
    """Return position label of argument relative to its predicate."""
    predicate_id = argument_tok.get("head")
    token_ids = [tok["id"] for tok in argument_expression if is_real_token(tok)]
    if max(token_ids) < predicate_id:
        return "BEFORE"
    if min(token_ids) > predicate_id:
        return "AFTER"
    return "DISCONTINUOUS"

def _agreement_value(parts: set[str], role_suffix: str) -> str | None:
    values = [
        part.removesuffix(role_suffix)
        for part in parts
        if part.endswith(role_suffix)
    ]
    return values[0] if len(values) == 1 else None


def predicate_representation(predicate_tok) -> dict:
    parts = xpos_parts(predicate_tok)
    verb_paradigm = next(
            (tag for tag in VERB_PARADIGMS if tag in parts),
            None,
        )
    verb_order = next(
            (tag for tag in VERB_ORDERS if tag in parts),
            None,
        )
    verb_mode = next(
            (tag for tag in VERB_MODES if tag in parts),
            None,
        )
    verb_polarity = next(
            (tag for tag in POLARITIES if tag in parts),
            None,
        )
    return {
        "verb_paradigm": verb_paradigm,
        "order": verb_order,
        "mode": verb_mode,
        "polarity": verb_polarity,
        "subject_agreement": _agreement_value(parts, "Subj"),
        "object_agreement": _agreement_value(parts, "Obj"),
    }


def predicate_head_order(predicate_tok, arguments: list[dict]) -> str:
    items = [(predicate_tok["id"], "V")]

    items.extend(
        (
            argument["argument_token"]["id"],
            ORDER_SYMBOLS.get(
                argument["relation"],
                f"[{argument['relation']}]",
            ),
        )
        for argument in arguments
    )

    return "".join(
        symbol
        for _, symbol in sorted(items)
    )


def predicate_representation(predicate_tok) -> dict:
    parts = xpos_parts(predicate_tok)
    verb_paradigm = next((tag for tag in VERB_PARADIGMS if tag in parts), None)
    order = next((tag for tag in VERB_ORDERS if tag in parts), None)
    mode = next((tag for tag in VERB_MODES if tag in parts), None)
    polarity = next((tag for tag in POLARITIES if tag in parts), None)
    subject_agreement = _agreement_value(parts, "Subj")
    object_agreement = _agreement_value(parts, "Obj")

    return {
        "verb_paradigm": verb_paradigm,
        "order": order,
        "mode": mode,
        "polarity": polarity,
        "subject_agreement": subject_agreement,
        "object_agreement": object_agreement,
    }

def _argument_observation(
    argument_tok,
    predicate_tok,
    children,
    sent_id,
    text: str,
    eng: str,
) -> dict:
    relation = argument_tok["deprel"]
    expression = get_argument_expression(argument_tok, children)

    return {
        "sent_id": sent_id,
        "text": text,
        "eng": eng,

        "predicate_id": (sent_id, predicate_tok["id"]),
        "argument_as_predicate_id": (
            (sent_id, argument_tok["id"])
            if argument_tok.get("upos") == "VERB"
            else None
        ),

        "relation": relation,
        "argument_token": argument_tok,
        "argument_expression": expression,

        "argument_text": expression_text(expression),
        "head_token": predicate_tok,
        "relative_position": argument_relative_position(
            argument_tok,
            expression,
        ),
    }

def get_predicate_tokens(sent):
    """
    In-line with the CG, assuming that only tokens w VERB are predicates.
    """
    return [
        tok
        for tok in sent
        if is_real_token(tok)
        and tok.get("upos") == "VERB"
    ]

def _analyze_sentence(sent, sent_index: int, relations: tuple[str, ...],):
    children = build_children(sent)
    by_id = token_index(sent)

    sent_id = sent.metadata.get("sent_id", f"sent_{sent_index}")
    text = sent.metadata.get("text", "")
    eng = sent.metadata.get("eng", "")

    predicate_tokens = get_predicate_tokens(sent)
    predicate_token_ids = {
        tok["id"]
        for tok in predicate_tokens
    }

    arguments = []
    arguments_by_predicate = defaultdict(list)

    for argument_tok in sent:
        if not is_real_token(argument_tok):
            continue

        if argument_tok.get("deprel") not in relations:
            continue

        predicate_token_id = argument_tok.get("head")

        if predicate_token_id not in predicate_token_ids:
            continue

        observation = _argument_observation(
            argument_tok=argument_tok,
            predicate_tok=by_id[predicate_token_id],
            children=children,
            sent_id=sent_id,
            text=text,
            eng=eng,
        )

        arguments_by_predicate[predicate_token_id].append(observation)

        arguments.append(observation)

    predicates = []

    for predicate_tok in predicate_tokens:
        predicate_id = (sent_id, predicate_tok["id"])

        predicate_arguments = arguments_by_predicate[predicate_tok["id"]]

        governor = by_id.get(predicate_tok.get("head"))

        governing_predicate_id = (
            (sent_id, governor["id"])
            if (governor is not None and governor["id"] in predicate_token_ids)
            else None
        )

        predicates.append({
            "predicate_id": predicate_id,
            "sent_id": sent_id,
            "text": text,
            "eng": eng,
            "predicate_token": predicate_tok,
            "predicate": predicate_representation(predicate_tok),
            "arguments": predicate_arguments,
            "head_order": predicate_head_order(predicate_tok, predicate_arguments),
            "relation_to_governor": predicate_tok.get("deprel"),
            "governing_predicate_id": (governing_predicate_id),
        })

    sentence = {
        "sent_id": sent_id,
        "text": text,
        "eng": eng,
        "predicate_ids": [
            predicate["predicate_id"]
            for predicate in predicates
        ],
    }

    return sentence, predicates, arguments

def analyze_corpus(
    corpus_path: str | Path,
    relations: tuple[str, ...] = ("nsubj", "obj", "iobj"),
) -> dict:
    """Three views are provided: sentence-based, predicate-based, and argument-based."""
    sentences = []
    predicates = []
    arguments = []

    with open(corpus_path, encoding="utf-8") as corpus_file:
        for sent_index, sent in enumerate(parse_incr(corpus_file), start=1):
            sentence, sentence_predicates, sentence_arguments = _analyze_sentence(
                sent,
                sent_index,
                relations,
            )

            sentences.append(sentence)
            predicates.extend(sentence_predicates)
            arguments.extend(sentence_arguments)

    return {
        "sentences": sentences,
        "predicates": predicates,
        "arguments": arguments,
    }

def get_argument_observations(
    corpus_path: str | Path,
    relations: tuple[str, ...] = ("nsubj", "obj", "iobj"),
) -> list[dict]:
    return analyze_corpus(corpus_path, relations=relations)["arguments"]


def get_predicate_observations(
    corpus_path: str | Path,
    relations: tuple[str, ...] = ("nsubj", "obj"),
) -> list[dict]:
    return analyze_corpus(corpus_path, relations=relations)["predicates"]

__all__ = [
    "analyze_corpus",
]