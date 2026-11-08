"""The reference reader against SPEC.md, and the shipped terminals.toml against both."""

import sys
import textwrap
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import terminal_facts as tf  # noqa: E402

ROWS = tf.load()


def identify(xtversion=None, environ=None, os_name="linux"):
    return tf.identify(ROWS, xtversion=xtversion, environ=environ or {}, os_name=os_name)


# The shipped file ----------------------------------------------------------------------


@pytest.mark.parametrize(
    "answer, row, version",
    [
        ("kitty(0.50.0)", "kitty", "0.50.0"),
        ("ghostty 1.4.0", "ghostty", "1.4.0"),
        ("rex 0.0.1793072516-g956d74", "rex", "0.0.1793072516-g956d74"),
        ("WezTerm 20240203-110809-5046fc22", "wezterm", "20240203-110809-5046fc22"),
        ("iTerm2 3.7.7", "iterm2", "3.7.7"),
    ],
)
def test_recorded_xtversion_answers(answer, row, version):
    """The answers pixcell recorded from real terminals (tests/answers/*.bin there)."""
    found = identify(answer)
    assert (found.id, found.version, found.recognised_by) == (row, version, "xtversion")


def test_ghostty_before_1_4_lacks_frame_edits():
    old, dev, new = identify("ghostty 1.3.1"), identify("ghostty 1.3.2-main+22f100c63"), identify("ghostty 1.4.0")
    assert old.rows == ("ghostty", "ghostty-1.3") and old.get("kitty.frame_edit") is False
    assert dev.rows == ("ghostty",) and dev.get("kitty.frame_edit") is True  # 1.3.2-main > 1.3.1
    assert new.get("kitty.frame_edit") is True
    assert old.get("kitty.placeholders") is True  # the rest from the base row


def test_unknown_version_gets_the_base_row():
    found = identify(environ={"TERM_PROGRAM": "ghostty"})
    assert found.rows == ("ghostty",) and found.version == ""


def test_os_rows():
    assert identify("WezTerm 20240203", os_name="macos").get("kitty.shm") is False
    assert identify("WezTerm 20240203", os_name="linux").get("kitty.shm") is None  # unknown there


def test_unknown_facts_and_terminals():
    assert identify("iTerm2 3.7.7").get("kitty.shm") is None
    assert identify("iTerm2 3.7.7").get("kitty.shm", "probe") == "probe"
    assert identify("foot(1.18.0)") is None
    assert identify(environ={"TERM": "xterm-256color"}) is None
    with pytest.raises(KeyError):
        identify("kitty(0.50.0)").get("kitty.typo")


def test_evidence_order_xtversion_beats_inherited_environment():
    """WezTerm started from a Rex pane inherits TERM_PROGRAM=rex and REX_SESSION."""
    environ = {"TERM_PROGRAM": "rex", "REX_SESSION": "session:1"}
    assert identify("WezTerm 20240203", environ=environ).id == "wezterm"
    assert identify(environ=environ).id == "rex"  # without asking, the environment wins


def test_environment_fallbacks():
    assert identify(environ={"KITTY_WINDOW_ID": "1"}).recognised_by == "env"
    found = identify(environ={"TERM_PROGRAM": "iTerm.app", "TERM_PROGRAM_VERSION": "3.7.7"})
    assert (found.id, found.version, found.recognised_by) == ("iterm2", "3.7.7", "term_program")
    assert identify(environ={"TERM": "xterm-kitty"}).id == "kitty"
    assert identify(environ={"TERM": "wezterm"}).id == "wezterm"  # term_substring


def test_every_shipped_fact_has_evidence():
    for row in ROWS:
        assert set(row.facts) <= set(row.evidence), row.id


# Versions and parsing ---------------------------------------------------------------


def test_version_order():
    key = tf.version_key
    assert key("1.3.1") < key("1.3.2-main+22f100c") < key("1.3.2") < key("1.4.0")
    assert key("v2") == key("2.0.0")
    assert key("20240203-110809-5046fc22") < key("20240203")
    assert key("main") is None


def test_parse_xtversion():
    assert tf.parse_xtversion("kitty(0.50.0)") == ("kitty", "0.50.0")
    assert tf.parse_xtversion("iTerm2 3.7.7") == ("iterm2", "3.7.7")
    assert tf.parse_xtversion("WezTerm 20240203-110809-5046fc22") == ("wezterm", "20240203-110809-5046fc22")


# The checker ----------------------------------------------------------------------------


def load_text(tmp_path, text):
    path = tmp_path / "terminals.toml"
    path.write_text(textwrap.dedent(text))
    return tf.load(path)


BASE = """
schema = 1
[[terminal]]
id = "t"
name = "T"
match.xtversion = ["t"]
"""


@pytest.mark.parametrize(
    "extra, message",
    [
        ('kitty.typo = true\n', "unknown fact"),
        ('kitty.shm = "yes"\n', "isn't bool"),
        ('kitty.storage_bytes = true\n', "isn't int"),
        ('kitty.fastest_format = "jpeg"\n', "isn't"),
        ('[[terminal]]\nid = "t"\nname = "T"\nmatch.env = ["X"]\n', "id used twice"),
        ('[[terminal]]\nid = "u"\nextends = "nope"\nmatch.os = ["linux"]\n', "isn't an earlier row"),
        ('[[terminal]]\nid = "u"\nextends = "t"\n', "needs a condition"),
        ('[[terminal]]\nid = "u"\nextends = "t"\nmatch.xtversion = ["u"]\n', "adds"),
        ('[[terminal]]\nid = "u"\nextends = "t"\nmatch.os = ["amiga"]\n', "match.os"),
        ('[[terminal]]\nid = "u"\nextends = "t"\nmatch.version_max = "latest"\n', "version string"),
        ('[[terminal]]\nid = "u"\nname = "U"\n', "identity matcher"),
        ('[terminal.evidence]\n"kitty.typo" = "x"\n', "evidence for unknown"),
    ],
)
def test_checker_rejects(tmp_path, extra, message):
    with pytest.raises(tf.FactsError, match=message):
        load_text(tmp_path, BASE + extra)


def test_checker_rejects_other_schemas(tmp_path):
    with pytest.raises(tf.FactsError, match="schema must be 1"):
        load_text(tmp_path, BASE.replace("schema = 1", "schema = 2"))


def test_rows_stack_in_file_order(tmp_path):
    rows = load_text(
        tmp_path,
        BASE
        + """
kitty.shm = true
kitty.frame_edit = true
[[terminal]]
id = "t-old"
extends = "t"
match.version_max = "2.0"
kitty.frame_edit = false
[[terminal]]
id = "t-old-mac"
extends = "t-old"
match.os = ["macos"]
kitty.shm = false
""",
    )
    found = tf.identify(rows, xtversion="t 1.0", environ={}, os_name="macos")
    assert found.rows == ("t", "t-old", "t-old-mac")
    assert found.facts == {"kitty.shm": False, "kitty.frame_edit": False}
    assert tf.identify(rows, xtversion="t 3.0", environ={}, os_name="macos").rows == ("t",)
