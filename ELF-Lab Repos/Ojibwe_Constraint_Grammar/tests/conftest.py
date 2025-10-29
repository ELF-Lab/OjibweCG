def pytest_addoption(parser):
    parser.addoption(
        "--update-gold",
        action="store_true",
        help="rewrite tests/data/expected.cg3 with current output",
    )

def pytest_sessionfinish(session, exitstatus):
    """Write updated gold file once, after all tests complete."""
    need = getattr(session, "need_write_gold", False)
    if not need:
        return

    from pathlib import Path
    from tests.util import dump_blocks

    ROOT = Path(__file__).resolve().parents[1]
    data_dir = ROOT / "tests" / "data"

    # EXPECTED is the in-memory dict we filled during tests
    from tests.test_disamb import EXPECTED        # import *inside* the hook

    out_path = data_dir / "expected.cg3"
    out_path.write_text(dump_blocks(EXPECTED), encoding="utf-8")
    print(f"[gold rewritten → {out_path}]")