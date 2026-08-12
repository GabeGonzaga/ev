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

    assert router.resolve("empty the trash") is None


def test_a_play_without_a_kind_escalates() -> None:
    # "play Blonde" is an album or a track. Tier 1 will not pick one.
    router = StaticRouter()

    assert router.resolve("play Blonde") is None
    assert router.resolve("toca Blonde") is None


def test_the_kind_word_becomes_the_argument() -> None:
    router = StaticRouter()

    resolution = router.resolve("põe o disco Cantigas do Maio")

    assert resolution is not None
    assert resolution.tool == "music.play"
    assert resolution.arguments == {"name": "Cantigas do Maio", "kind": "album"}


# --- macros ---------------------------------------------------------------


def test_a_macro_name_is_captured_verbatim() -> None:
    # The name is the user's, matched against the saved list later. Capturing
    # it verbatim is what lets "Segunda-feira" survive to the service.
    resolution = StaticRouter().resolve("corre a macro Segunda-feira")

    assert resolution is not None
    assert resolution.tool == "macro.run"
    assert resolution.arguments == {"name": "Segunda-feira"}


def test_a_macro_needs_a_name() -> None:
    assert StaticRouter().resolve("run the macro") is None


def test_a_word_starting_like_macro_is_not_one() -> None:
    assert StaticRouter().resolve("run the marathon") is None


# --- notes ----------------------------------------------------------------


def test_a_bare_title_is_routed() -> None:
    resolution = StaticRouter().resolve("cria uma nota chamada Compras")

    assert resolution is not None
    assert resolution.tool == "notes.create"
    assert resolution.arguments == {"title": "Compras"}


def test_a_title_with_a_body_after_it_escalates() -> None:
    # A greedy capture would title the note "Boiler saying it was serviced in
    # March" and lose the body entirely -- a wrong argument that looks like a
    # success, which is the failure mode tier 1 exists to avoid.
    assert (
        StaticRouter().resolve("take a note called Boiler saying it was serviced")
        is None
    )


def test_a_folder_in_the_sentence_escalates() -> None:
    assert (
        StaticRouter().resolve("guarda uma nota chamada Ata na pasta Trabalho") is None
    )


# --- reminders ------------------------------------------------------------


def test_a_reminder_with_no_date_is_routed() -> None:
    resolution = StaticRouter().resolve("lembra-me de comprar pão")

    assert resolution is not None
    assert resolution.tool == "reminders.create"
    assert resolution.arguments == {"title": "comprar pão"}


def test_a_hyphen_is_optional_in_portuguese() -> None:
    # Whisper writes "lembra me" as often as "lembra-me".
    assert StaticRouter().resolve("lembra me de comprar pão") is not None


def test_anything_with_a_time_in_it_escalates() -> None:
    """A date is computed, not quoted.

    "amanhã às nove" is not in the utterance as a value: it depends on what
    day it is, which is the model's job. Tier 1 answering would set the
    reminder with the words as its title.
    """
    router = StaticRouter()

    for utterance in (
        "remind me to call the dentist tomorrow",
        "remind me to call at 15",
        "remind me to pay the rent on the 15th",
        "remind me to water the plants at noon",
        "lembra-me de ligar ao médico às 15",
        "lembra-me de pagar a renda no dia 15",
        "lembra-me de regar as plantas logo",
        "lembra-me de comprar pão amanhã",
    ):
        assert router.resolve(utterance) is None, utterance


def test_a_named_list_escalates_too() -> None:
    assert StaticRouter().resolve("remind me to buy milk in the Shopping list") is None
