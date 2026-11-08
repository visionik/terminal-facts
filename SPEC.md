# terminals.toml, schema 1

One TOML file of **facts about terminals**: how to recognise each one, and what it
really does, with the evidence. Several programs read it (pixcell in Python, sdl-kitty
in C), so a finding recorded once reaches all of them.

## What goes in, and what doesn't

**In:** properties of a terminal that don't depend on the program reading them, and
that can't simply be asked at run time. Ghostty 1.3.1 doesn't implement `a=f`;
WezTerm's `a=f` never redraws; Kitty ignores escape codes over 256 KiB; Rex's
`TIOCGWINSZ` pixel sizes are wrong.

**Out:**

- **What can be asked.** The Kitty graphics query (`a=q`), iTerm2's `ReportCellSize`,
  Sixel in device attributes, cell sizes: ask the terminal at run time.
- **A program's own choices.** Framebuffer caps, coalescing gaps, drain timings, memory
  budgets: each program derives these from facts, in its own code or config, keyed by
  the same `id`.

A fact that's left out is **unknown**. Readers probe, or use their own default; they
never read a missing fact as `false`.

Environment variables a program defines (`SDL_KITTY_*`, `PIXCELL_*`) still override
everything, as each program documents.

## Layout

```toml
schema = 1

[[terminal]]            # a base row: one terminal
id = "ghostty"
name = "Ghostty"
match.xtversion = ["ghostty"]
match.env = ["GHOSTTY_RESOURCES_DIR"]
match.term_program = ["ghostty"]
match.term_substring = ["ghostty"]
kitty.frame_edit = true

[terminal.evidence]     # free text per fact: what showed it, and when
"kitty.frame_edit" = "1.4.0 release notes; soak 2026-10-27"

[[terminal]]            # an extending row: what differs under a condition
id = "ghostty-1.3"
extends = "ghostty"
match.version_max = "1.3.1"
kitty.frame_edit = false
```

| Top-level key | Meaning |
|---|---|
| `schema` | `1`. Readers refuse other values. |
| `terminal` | The rows, in order. Order matters (see Resolving). |

### Row keys

| Key | Type | Meaning |
|---|---|---|
| `id` | string | Unique; lower case, digits, `.` and `-`. Programs key their own tuning by it. |
| `name` | string | Display name. Required on base rows. |
| `extends` | string | Makes this an **extending row** of an earlier row. |
| `match.*` | see below | How to recognise the terminal (base rows) or when the row applies (extending rows). |
| `evidence` | table | Fact key to a short note: what showed it (eye, probe, source, release notes), version, date, project. Readers may ignore it. |
| `notes` | string | Anything else. Readers ignore it. |
| facts | see below | Dotted keys such as `kitty.frame_edit`. |

## Recognising the terminal

Base rows carry **identity** matchers; each is a list of strings.

| Matcher | Matches when |
|---|---|
| `match.xtversion` | The name in the terminal's XTVERSION answer (`CSI > 0 q`) equals one of these. |
| `match.env` | One of these environment variables is set and non-empty. |
| `match.term_program` | `TERM_PROGRAM` equals one of these, ignoring case. |
| `match.term` | `TERM` equals one of these exactly. |
| `match.term_substring` | `TERM` contains one of these. |

**XTVERSION name.** The answer is the text inside `DCS > | … ST`. The name is its first
word, up to a space or `(`, in lower case, and the version is what follows:
`kitty(0.50.0)` → `kitty`, `0.50.0`; `WezTerm 20240203-110809-5046fc22` → `wezterm`;
`iTerm2 3.7.7` → `iterm2`, `3.7.7`.

**Order of evidence.** Readers try these in order and stop at the first that names a
row, taking the first matching base row in file order:

1. **XTVERSION**, when the reader asked the terminal and it answered. It's the only
   evidence that can't be inherited: a terminal started from another, or a session over
   SSH, still carries the first one's environment.
2. **`match.env`**: variables only that terminal sets (`KITTY_WINDOW_ID`).
3. **`match.term_program`**.
4. **`match.term`, `match.term_substring`**.

No row matched: the terminal is unknown, and every fact is unknown.

**Version.** The XTVERSION version when the terminal answered; otherwise
`TERM_PROGRAM_VERSION`, when `TERM_PROGRAM` matches the recognised row; otherwise
unknown.

## Extending rows

An extending row names an earlier row in `extends` and adds **conditions**; it never
has identity matchers or a `name`.

| Condition | Type | Holds when |
|---|---|---|
| `match.version_min` | string | The version is known and ≥ this. |
| `match.version_max` | string | The version is known and ≤ this. |
| `match.os` | list | The operating system is one of `macos`, `linux`, `windows`, `bsd`. |

Conditions are AND'd. **A version bound never holds for an unknown version**, so a
terminal whose version can't be found gets its base row's facts, normally those of
current releases.

**Comparing versions.** Take the first run of dotted numbers (skipping any non-digit
prefix), padding with zeros. A `-suffix` straight after the numbers sorts **below** the
same numbers: `1.3.2-main+22f100c` is after `1.3.1` and before `1.3.2`. Anything else
after the numbers is ignored.

## Resolving

1. Recognise the base row (above).
2. Start from its facts.
3. Go through the file in order. Apply every row whose `extends` names a row already
   applied and whose conditions hold, overriding the facts it sets.

Rows therefore stack: put an extending row after the row it extends, and a later row
wins where two set the same fact.

## Facts

| Key | Type | Meaning |
|---|---|---|
| `kitty.placeholders` | bool | Draws Kitty Unicode placeholders (`U=1` virtual placements, U+10EEEE cells). |
| `kitty.frame_edit` | bool | An in-place frame edit (`a=f` with `r=`) shows on screen. |
| `kitty.frame_edit_reply` | bool | Answers an `a=f` sent without `q=2`. `false`: silence isn't failure. |
| `kitty.animation` | bool | Plays Kitty animations itself (`a=f` frames, `a=a` to run). |
| `kitty.shm` | bool | Shared-memory transmission (`t=s`) works. |
| `kitty.max_escape_bytes` | int | Longest escape code it accepts; longer ones are dropped (and their payload may show as text). |
| `kitty.storage_bytes` | int | Image memory it keeps before evicting images. |
| `kitty.fastest_format` | `"zlib"`, `"png"`, `"raw"` | Frame format it takes in fastest: raw pixels with `o=z`, PNG (`f=100`), or raw pixels. |
| `iterm2.gif_animation` | bool | Plays animated GIFs sent as iTerm2 inline images (`OSC 1337 ; File=`). |
| `window.ioctl_pixels` | bool | `TIOCGWINSZ` pixel sizes can be trusted. |
| `keyboard.kitty_protocol_config` | string | What the user must configure before the Kitty keyboard protocol works. |

New facts are added to this table, and to `FACTS` in `terminal_facts.py`, before
they're used. Readers reject keys they don't know, so a typo can't silently become an
unknown fact. A change in a fact's meaning needs a new schema number.

## Readers

- `terminal_facts.py` here: the reference, standard library only (Python 3.11+).
  `python terminal_facts.py check` checks a file.
- pixcell vendors `terminal_facts.py` and `terminals.toml`.
- sdl-kitty reads the file in C (tomlc17), with these rules.
