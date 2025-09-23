from pathlib import Path
import pytest

from src.disambiguation import disambiguate, load_fst_parser  
from tests.util import load_blocks, dump_blocks, normalise

# absolute paths (update if moving files around or changing directory/file names )
ROOT      = Path(__file__).resolve().parents[1]          # project root
DATA_DIR  = ROOT / "tests" / "data"

GRAMMAR   = (ROOT / "data" / "rules" / "disambiguation.cg3").as_posix() 
FST_BIN   = ROOT / "data" / "fst" / "ojibwe.att"

# load FST
FST = load_fst_parser(str(FST_BIN))

# load test cases
SOURCE   = load_blocks(DATA_DIR / "sentences.ojib")
EXPECTED = load_blocks(DATA_DIR / "expected.cg3")

# parametrised test
@pytest.mark.parametrize("case_id", sorted(SOURCE))
def test_disamb(case_id, request):
    got_cg3 = disambiguate(                   # returns one string
        sentence=SOURCE[case_id],
        cg3_grammar_filepath=GRAMMAR,
        fst=FST,
        verbose=False,
    )

    got  = normalise(got_cg3)
    want = normalise(EXPECTED.get(case_id, ""))

    if request.config.getoption("--update-gold"):
        EXPECTED[case_id] = got_cg3.strip()
        request.session.need_write_gold = True
        pytest.skip(f"gold updated for {case_id}")

    assert got == want, f"Mismatch with case # {case_id}"

# ----------------------------------------------------------------------
def pytest_sessionfinish(session, exitstatus):
    if getattr(session, "need_write_gold", False):
        (DATA_DIR / "expected.cg3").write_text(
            dump_blocks(EXPECTED), encoding="utf-8"
        )
        print("[gold rewritten]")