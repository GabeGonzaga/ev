from __future__ import annotations

from ev.router.static import LearnedPhrase, StaticRouter, normalise, prepare

# --- normalisation --------------------------------------------------------


def test_whitespace_is_collapsed_and_case_is_kept() -> None:
    assert prepare("  open   GitHub.com  ") == "open GitHub.com"


def test_normalise_casefolds_but_keeps_accents() -> None:
    # Accents carry meaning in pt-PT. Stripping them to "simplify" matching
    # would quietly change the words.
    assert normalise("Abre a Página") == "abre a página"


# --- tier 0 ---------------------------------------------------------------


def test_a_learned_phrase_is_matched_exactly() -> None:
    router = StaticRouter(
        phrases={"work stuff": LearnedPhrase(tool="browser.open_url", arguments={})}
    )

    resolution = router.resolve("Work Stuff!")

    assert resolution is not None
    assert resolution.tool == "browser.open_url"
    assert resolution.confidence == 1.0


def test_a_learned_phrase_wins_over_a_pattern() -> None:
    # Tier 0 is what the user taught. It outranks a regex that happens to fit.
    router = StaticRouter(
        phrases={
            "open github.com": LearnedPhrase(
                tool="browser.open_url", arguments={"url": "https://github.com/ev"}
            )
        }
    )

    resolution = router.resolve("open github.com")

    assert resolution is not None
    assert resolution.arguments == {"url": "https://github.com/ev"}


def test_an_unlearned_phrase_falls_through() -> None:
    router = StaticRouter(phrases={"work stuff": LearnedPhrase(tool="a.b")})

    assert router.resolve("home stuff") is None


# --- tier 1 ---------------------------------------------------------------


def test_a_bare_domain_gets_https_not_http() -> None:
    router = StaticRouter()

    resolution = router.resolve("open example.com")

    assert resolution is not None
    assert resolution.arguments == {"url": "https://example.com"}


def test_an_explicit_scheme_is_left_alone() -> None:
    router = StaticRouter()

    resolution = router.resolve("open http://example.com")

    assert resolution is not None
    assert resolution.arguments == {"url": "http://example.com"}


def test_the_captured_argument_keeps_its_case() -> None:
    # Matching is case-insensitive; the argument is not. Proper nouns are the
    # arguments, and lowercasing them is how a route silently becomes wrong.
    router = StaticRouter()

    resolution = router.resolve("OPEN Example.com/Docs")

    assert resolution is not None
    assert resolution.arguments == {"url": "https://Example.com/Docs"}


def test_both_languages_are_live_at_once() -> None:
    # Nothing tags the utterance with a language before it gets here, and real
    # input is mixed anyway.
    router = StaticRouter()

    assert router.resolve("abre example.com") is not None
    assert router.resolve("open example.com") is not None


def test_a_filename_is_not_a_website() -> None:
    router = StaticRouter()

    assert router.resolve("open report.pdf") is None
    assert router.resolve("abre o relatório.pdf") is None


def test_an_explicit_scheme_beats_the_filename_guard() -> None:
    # The guard exists for ambiguity. There is none here.
    router = StaticRouter()

    resolution = router.resolve("open https://example.com/report.pdf")

    assert resolution is not None
    assert resolution.arguments == {"url": "https://example.com/report.pdf"}


def test_an_application_name_is_not_routed() -> None:
    router = StaticRouter()

    assert router.resolve("open Safari") is None


def test_an_unknown_utterance_returns_none() -> None:
    # None is "not mine", not "no": phase 1 hands this to the model router.
    router = StaticRouter()

    assert router.resolve("play the album Blonde") is None
