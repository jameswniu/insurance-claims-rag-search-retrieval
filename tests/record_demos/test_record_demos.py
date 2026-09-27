"""The demo recorder's pure logic: how long a reading pause lasts, how long a caption may be, which files each clip
writes and what each may weigh. Recording itself needs the stack and a browser, so it is checked by the recorder's
own assertions, not here."""

import json
import re
from pathlib import Path

import pytest

from tools import demo_stage as stage
from tools import record_demos as rd

VIDEO_CLIPS = list(rd.OUTPUTS)
HAIL = "How much did we pay on hail claims in Colorado in Q2 2025?"
ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def storyboard(monkeypatch: pytest.MonkeyPatch) -> None:
    """The pacing block's own times, long enough to read every word as it plays, as PACE 1.0 spends them."""
    monkeypatch.setattr(rd, "PACE", 1.0)


@pytest.mark.usefixtures("storyboard")
def test_a_pause_is_never_shorter_than_its_storyboard_minimum() -> None:
    assert rd.reading_hold(8.0, 12, "Read the returned figure") == 8.0
    assert rd.reading_hold(8.0, 0, "") == 8.0


@pytest.mark.usefixtures("storyboard")
def test_a_pause_grows_with_the_words_on_screen_and_in_the_caption() -> None:
    # 40 words on screen and 4 in the caption: 2.0 + 0.30 * 44.
    assert rd.reading_hold(2.0, 40, "Read the returned figure") == pytest.approx(15.2)
    assert rd.reading_hold(2.0, 41, "Read the returned figure") > rd.reading_hold(2.0, 40, "Read the returned figure")


@pytest.mark.usefixtures("storyboard")
def test_a_table_is_read_cell_by_cell_when_that_takes_longer() -> None:
    # 10 numbers, 5 header words and a 2-word caption: 2.0 + 0.6 * 10 + 0.30 * 7, longer than 2.0 + 0.30 * 9.
    assert rd.reading_hold(0.0, 7, "Check shares", cells=10, labels=5) == pytest.approx(10.1)
    assert rd.reading_hold(0.0, 40, "Check shares", cells=1, labels=5) == pytest.approx(2.0 + 0.3 * 42)


def test_pace_is_the_one_knob_that_retimes_every_pause_evenly(monkeypatch: pytest.MonkeyPatch) -> None:
    pauses = [(8.0, 12, "Read the returned figure", 0, 0), (2.0, 40, "Read the returned figure", 0, 0)]
    pauses += [(0.0, 7, "Check shares", 10, 5), (18.0, 50, "Trace the figure to its source", 0, 0)]

    def holds() -> list[float]:
        return [rd.reading_hold(least, words, caption, cells=n, labels=m) for least, words, caption, n, m in pauses]

    monkeypatch.setattr(rd, "PACE", 1.0)
    slow = holds()
    monkeypatch.setattr(rd, "PACE", 0.5)
    assert holds() == pytest.approx([hold / 2 for hold in slow], abs=0.005)
    assert rd.paced(rd.CLICK_BEAT_S) == rd.CLICK_BEAT_S / 2


def test_a_question_types_at_pace() -> None:
    # The recorder types at its mean key pause times PACE, so a question takes about that long a key.
    mean = rd.paced(rd.TYPE_DELAY_MS)
    assert sum(stage.typing_delays(HAIL, mean)) == pytest.approx(mean * len(HAIL), rel=0.05)
    slow = sum(stage.typing_delays(HAIL, rd.TYPE_DELAY_MS))
    assert sum(stage.typing_delays(HAIL, mean)) == pytest.approx(rd.PACE * slow)


def test_sql_is_read_in_names_placeholders_and_operators() -> None:
    sql = "SELECT SUM(amount) AS value FROM sem.v_payments_net WHERE (paid_date BETWEEN %s AND %s) AND state = ANY(%s)"
    # SELECT SUM amount AS value FROM sem.v_payments_net WHERE paid_date BETWEEN %s AND %s AND state = ANY %s
    assert rd.sql_units(sql) == 18


def test_a_caption_is_one_to_eight_words() -> None:
    rd.check_caption("one two three four five six seven eight")
    for bad in ("one two three four five six seven eight nine", "", "   "):
        with pytest.raises(ValueError):
            rd.check_caption(bad)


def test_every_caption_fits_the_word_limit() -> None:
    for clip, beats in rd.CAPTIONS.items():
        for beat, caption in beats.items():
            text = caption.format(claim=105964)
            assert rd.caption_words(text) <= rd.CAPTION_MAX_WORDS, f"{clip}.{beat}: {text!r}"
            rd.check_caption(text)


def test_every_video_clip_has_captions_and_opens_on_who_is_asking() -> None:
    assert set(rd.CAPTIONS) == set(VIDEO_CLIPS)
    for clip in VIDEO_CLIPS:
        assert "who" in rd.CAPTIONS[clip], clip


def test_outputs_and_clips_name_the_same_clips() -> None:
    assert set(rd.OUTPUTS) == set(rd.CLIPS)
    assert len(VIDEO_CLIPS) == 14


def test_each_clip_writes_an_mp4_and_the_readme_gifs_are_ask_permissions_devmode_and_dashboard() -> None:
    for clip in VIDEO_CLIPS:
        files = rd.OUTPUTS[clip]
        assert f"{clip}.mp4" in files, clip
        assert set(files) <= {f"{clip}.mp4", f"{clip}.gif", f"{clip}.poster.png"}, clip
    gifs = [clip for clip in VIDEO_CLIPS if f"{clip}.gif" in rd.OUTPUTS[clip]]
    assert gifs == ["ask", "permissions", "devmode", "dashboard"]
    # The two newest clips beside the devmode one are mp4s alone.
    assert rd.OUTPUTS["ocr-flag"] == ("ocr-flag.mp4",) and rd.OUTPUTS["live"] == ("live.mp4",)


def test_a_run_records_the_live_clip_alone_and_every_other_clip_with_no_key() -> None:
    no_key = rd.clips_for([], live=False)
    assert "live" not in no_key and no_key[-1] == "dashboard" and len(no_key) == len(rd.OUTPUTS) - 1
    assert rd.clips_for([], live=True) == ["live"]
    # Named clips keep the recording order, whatever order they were named in.
    assert rd.clips_for(["devmode", "ocr-flag"], live=False) == ["ocr-flag", "devmode"]
    with pytest.raises(ValueError, match="needs live mode"):
        rd.clips_for(["ask", "live"], live=False)
    with pytest.raises(ValueError, match="recorded with no key"):
        rd.clips_for(["live", "devmode"], live=True)


LIVE_MODE = {"backend": "anthropic", "models": {"main": "claude-sonnet-5", "fast": "claude-haiku-4-5", "check": "g-3"}}
ANSWERED = {
    "mode": "anthropic",
    "fallback": None,
    "models": ["claude-sonnet-5", "g-3"],
    "verifier": {"kept": 2, "cut": 0, "retried": False},
}


def test_a_live_request_counts_only_when_the_models_answered_and_nothing_fell_back() -> None:
    assert rd.live_problems(ANSWERED, LIVE_MODE) == []
    # A reply that names its model with a date after it is still that model.
    assert rd.live_problems({**ANSWERED, "models": ["claude-sonnet-5-20260101", "g-3"]}, LIVE_MODE) == []
    assert rd.live_problems(None, LIVE_MODE) == ["the request log has no row for it"]
    [fell_back] = rd.live_problems({**ANSWERED, "fallback": "reading"}, LIVE_MODE)
    assert "fell back" in fell_back and "reading" in fell_back
    [unchecked] = rd.live_problems({**ANSWERED, "models": ["claude-sonnet-5"]}, LIVE_MODE)
    assert "check model, g-3" in unchecked
    assert len(rd.live_problems({**ANSWERED, "mode": "none", "models": [], "verifier": None}, LIVE_MODE)) == 4
    # A model whose name only starts the same way is another model.
    assert rd.live_problems({**ANSWERED, "models": ["claude-sonnet-50", "g-3"]}, LIVE_MODE)


def test_the_app_mode_probe_never_reads_a_credential() -> None:
    assert "KEY" not in rd.MODE_PY and "key" not in rd.MODE_PY.lower().replace("no-key", "")
    assert "environ.get('LLM_BACKEND')" in rd.MODE_PY


def test_a_flagged_answer_may_state_the_ledger_amount_but_never_the_misread_one() -> None:
    flagged = (
        "The scanned total on the proof of loss for claim 103747 couldn't be read reliably: what was read isn't in the"
        " form a total takes. The payment record shows $5,957.79 paid on this claim."
    )
    assert rd.wrong_amounts(flagged, "$595779", ("$5,957.79",)) == []
    stated = "The total on the proof of loss for claim 103747 is $595,779.00."
    assert rd.wrong_amounts(stated, "$595779", ("$5,957.79",)) == ["$595,779.00", "595,779.00"]
    assert rd.wrong_amounts("It reads 595779 on the page.", "$595779", ()) == ["595779"]
    assert rd.wrong_amounts("It came to $12.50.", "$595779", ("$5,957.79",)) == ["$12.50"]


def test_a_number_reads_as_the_page_script_writes_it() -> None:
    assert rd.js_number(112.0) == "112" and rd.js_number(111.1) == "111.1" and rd.js_number(7) == "7"


def test_only_the_devmode_clip_turns_dark_and_every_special_clip_is_recorded() -> None:
    assert set(rd.DARK_CLIPS) == {"devmode"} and set(rd.LIVE_CLIPS) == {"live"}
    assert set(rd.DARK_CLIPS) | set(rd.LIVE_CLIPS) <= set(rd.OUTPUTS)
    assert not set(rd.DARK_CLIPS) & set(rd.LIVE_CLIPS)


def test_the_console_text_is_raised_to_the_floor_like_the_evidence() -> None:
    rule = rd.DEMO_CSS.split(".devconsole .console-rows", 1)[1].split("}", 1)[0]
    assert f"font-size: {rd.FONT_FLOOR_PX}px !important" in rule and ".devconsole .console-empty" in rule


def test_the_readme_plays_every_gif_and_names_only_files_the_recorder_writes() -> None:
    for readme in (ROOT / "README.md", ROOT / "docs" / "templates" / "README.md"):
        named = set(re.findall(r"docs/demo/([\w.-]+)", readme.read_text()))
        assert named <= set(rd.NAMED), f"{readme.name}: {named - set(rd.NAMED)}"
        assert {name for name in rd.NAMED if name.endswith(".gif")} <= named, readme


def test_no_file_is_written_by_two_clips_and_retired_files_are_gone() -> None:
    names = [name for files in rd.OUTPUTS.values() for name in files]
    assert len(names) == len(set(names))
    assert not {"edges.mp4", "dashboard.png", "permissions.poster.png"} & set(names)


def test_the_dashboard_is_recorded_after_every_chat_clip() -> None:
    # Its UI filter counts the chat clips' own requests, so it comes last.
    assert list(rd.OUTPUTS)[-1] == "dashboard"


def test_every_output_has_a_budget() -> None:
    assert set(rd.BUDGETS) == {name for files in rd.OUTPUTS.values() for name in files}


def test_the_budgets_follow_the_storyboard() -> None:
    for clip in ("ask", "permissions", "dashboard"):
        assert rd.BUDGETS[f"{clip}.gif"] == rd.Budget(4 * rd.MB, 5 * rd.MB, 52)
    assert rd.BUDGETS["ask.mp4"].limit_bytes == 10 * rd.MB
    for clip in rd.BOUNDARY_CLIPS:
        assert rd.BUDGETS[f"{clip}.mp4"] == rd.Budget(3 * rd.MB, 6 * rd.MB, 120)
    for clip in rd.EVIDENCE_CLIPS:
        assert rd.BUDGETS[f"{clip}.mp4"] == rd.Budget(8 * rd.MB, 15 * rd.MB, 120)
    assert rd.BUDGETS["dashboard.poster.png"] == rd.Budget(rd.POSTER_TARGET_BYTES, 1 * rd.MB, None)


def test_a_file_over_its_limit_fails_and_one_over_its_target_warns() -> None:
    assert rd.check_budget("ask.gif", 4 * rd.MB, 45.0) == (None, None)
    failed, warned = rd.check_budget("ask.gif", 5 * rd.MB + 1, 45.0)
    assert failed and "limit" in failed and warned is None
    failed, warned = rd.check_budget("ask.gif", 3 * rd.MB, 52.5)
    assert failed and "52 s" in failed
    failed, warned = rd.check_budget("injection.mp4", 4 * rd.MB, 25.0)
    assert failed is None and warned and "target" in warned
    assert rd.check_budget("ask.poster.png", 400_000, None) == (
        None,
        "ask.poster.png is 0.40 MB, over its 0.25 MB target",
    )


def test_amounts_read_the_way_the_answers_write_them() -> None:
    assert rd.dollars("4108452.79") == "$4,108,453"
    assert rd.dollars("0.50") == "$1"
    assert rd.cents("45028.54") == "$45,028.54"


def test_eval_ids_are_the_cases_that_ask_exactly_that_question() -> None:
    known = [{"id": "b-2", "q": "Is flood damage covered?"}, {"id": "a-1", "q": "Is flood damage covered?"}]
    known.append({"id": "c-3", "q": "Is flood damage coverde?"})
    assert rd.eval_ids("Is flood damage covered?", known) == ["a-1", "b-2"]
    assert rd.eval_ids("What's a good recipe for banana bread?", known) == []


def test_the_manifest_keeps_other_clips_and_lists_clips_in_recording_order(tmp_path: Path) -> None:
    rd.write_manifest(tmp_path, {"why": {"length_s": 95.0}, "ask": {"length_s": 42.0}})
    rd.write_manifest(tmp_path, {"why": {"length_s": 96.0}})
    manifest = json.loads((tmp_path / rd.MANIFEST).read_text())
    assert list(manifest["clips"]) == ["ask", "why"]
    assert manifest["clips"]["why"] == {"length_s": 96.0}
    assert manifest["pacing"]["pace"] == rd.PACE
    assert manifest["pacing"]["seconds_per_word"] == pytest.approx(rd.SECONDS_PER_WORD * rd.PACE)


def test_the_page_script_gets_every_setting_it_names() -> None:
    assert "__" not in rd.demo_js()


def test_every_video_clip_opens_on_a_title_line() -> None:
    assert set(rd.TITLES) == set(VIDEO_CLIPS)
    for clip, title in rd.TITLES.items():
        assert 0 < rd.caption_words(title) <= rd.CAPTION_MAX_WORDS, clip


def test_on_screen_text_keeps_the_voice_rules() -> None:
    shown = [text for beats in rd.CAPTIONS.values() for text in beats.values()] + list(rd.TITLES.values())
    for text in shown:
        for banned in ("\u2014", "\u2013", "--", "\u2192", "showcase", "production-grade", "golden", "source of truth"):
            assert banned not in text.lower(), text


def test_each_output_comes_out_its_own_width() -> None:
    # The README's column shows the GIFs, and the posters share their framing.
    assert rd.width_of("ask.mp4") == rd.width_of("policy.mp4") == 1920
    assert rd.width_of("ask.gif") == rd.width_of("permissions.gif") == rd.width_of("dashboard.gif") == 900
    assert rd.width_of("ask.poster.png") == rd.width_of("dashboard.poster.png") == 900


def test_every_token_the_injected_css_reads_is_in_the_app_stylesheet() -> None:
    token = r"-{2}[\w-]+"  # a CSS custom property's name, such as --background
    declared = set(re.findall(rf"({token})\s*:", (ROOT / "frontend" / "src" / "styles.css").read_text()))
    read = set(re.findall(rf"var\(({token})", rd.DEMO_CSS))
    assert read and read <= declared, read - declared


def test_the_injected_css_leaves_answers_and_chart_labels_alone() -> None:
    assert ".answer-text" not in rd.DEMO_CSS and ".notice" not in rd.DEMO_CSS
    assert "svg.chart" not in rd.DEMO_CSS
    assert f"font-size: {rd.FONT_FLOOR_PX}px !important" in rd.DEMO_CSS
