from textkit.slug import slugify


def test_accents_and_punctuation():
    assert slugify("Crème Brûlée -- Recipe!") == "creme-brulee-recipe"


def test_edges_and_repeats():
    assert slugify("  --Hello,   World!!--  ") == "hello-world"


def test_digits_kept():
    assert slugify("Top 10 Tips (2026)") == "top-10-tips-2026"


def test_plain_unchanged():
    assert slugify("already-a-slug") == "already-a-slug"
