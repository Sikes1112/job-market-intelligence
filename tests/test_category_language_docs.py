from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DOCS = REPO_ROOT / "docs"

REQUIRED_DOCS = (
    "CATEGORY_LANGUAGE.md",
    "LAYER_19_CATEGORY_OWNERSHIP.md",
    "PUBLIC_REPORT_METHODOLOGY.md",
    "BENCHMARK_METHODOLOGY.md",
)

REQUIRED_CATEGORY_TERMS = (
    "opportunity geography",
    "career market intelligence",
    "company-region presence",
    "early-career access",
    "market fit",
    "regional opportunity density",
    "career-market signal",
)


def _doc_text(name: str) -> str:
    return (DOCS / name).read_text().lower()


def test_layer19_category_docs_exist() -> None:
    for name in REQUIRED_DOCS:
        assert (DOCS / name).exists(), f"missing docs/{name}"


def test_category_language_defines_required_vocabulary() -> None:
    text = _doc_text("CATEGORY_LANGUAGE.md")

    for term in REQUIRED_CATEGORY_TERMS:
        assert term in text

    assert "not as a\njob board" in text
    assert "batch 19a only\ndefines vocabulary and public explanation surfaces" in text


def test_layer19_methodology_docs_preserve_batch_boundary() -> None:
    layer = _doc_text("LAYER_19_CATEGORY_OWNERSHIP.md")
    public_report = _doc_text("PUBLIC_REPORT_METHODOLOGY.md")
    benchmark = _doc_text("BENCHMARK_METHODOLOGY.md")

    assert "create report rankings" in layer
    assert "create benchmark scoring" in layer
    assert "change recommendation ranking" in layer
    assert "change market coverage" in layer
    assert "change billing" in layer
    assert "change institutional permissions" in layer
    assert "change personalization controls" in layer

    assert "batch 19a does not create report rankings" in public_report
    assert "they do\nnot create a new ranking system or scoring formula" in public_report

    assert "batch 19a does not create benchmark scoring" in benchmark
    assert "they are not\nweights, formulas, score components, or ranking rules" in benchmark
