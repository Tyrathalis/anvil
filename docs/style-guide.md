# Documentation style guide

**Status: adopted 2026-11-09 (the user), as drafted.** It binds every edit from that day. The review that produced
it is in the running record (2026-11-09, 19:45). CLAUDE.md's "Writing style" bullet is its summary.

## The one idea

Every document is one of three kinds, and each kind is updated in one way. Most of the errors the 11-09 review found
came from updating one kind the way another is updated: a state document appended to like a log, or a reference
document that had turned into a changelog.

| Kind | What it answers | How it is updated | Examples |
|---|---|---|---|
| **State** | What is true now? | Rewritten in place. Never appended to. | CLAUDE.md's Now block and state table, the root README's Status, the map's Now panel and tables, a plan's status line |
| **Record** | What happened, and why did we decide it? | Appended to. Never rewritten. | ADRs, the running record, devlogs, the status archive, fork lineage |
| **Reference** | How does this work, and how do I use it? | Edited to describe the present. | The quickstart, the design doc, the field guide, standing rules, `docs/ops/`, code comments and docstrings, `--help` text |

When a fact changes, the state document is rewritten, the record gets a new entry, and the reference is edited if
the behaviour it describes changed.

## State documents

1. **Rewrite, do not append.** When a run closes, its "running" sentence is replaced by its result. A state document
   never holds two sentences about the same thing from different days.
2. **Say each fact once.** If the state table holds a number, the Now block links to the table and does not repeat it.
3. **Closed work leaves.** A Now bullet covers what is running, what is next, what waits on the user, and the pins.
   Once a thing is closed and nothing depends on reading it here, its text moves verbatim to the status archive
   and the bullet keeps one sentence and a link.
4. **Stay inside the cap.** The Now block is at most 800 words and a bullet at most 120. The README's Status is at
   most 80 words. A bullet that needs more is carrying history.
5. **Date the document, not the sentences.** One "as of" date in the header, updated with every edit.
6. **A copy says it is a copy.** The README's Status and the map's Now panel either are generated from CLAUDE.md or
   carry their own "as of" date and a pointer to it. They never claim to be current without one.

## Records

1. **Append, newest last.** An entry is dated, and timed when the hour matters.
2. **Correct with a new entry.** A wrong entry is not edited. The correction is a new entry that names the old one.
3. **One edit is allowed:** a single line at the top of a superseded section that says what superseded it and where.
4. **Lead with the verdict.** The first sentence of an entry or an ADR says what was decided or found. The evidence
   follows.
5. **An ADR's status is one of** `proposed`, `accepted`, `superseded by ADR-NNNN`, or
   `partly superseded by ADR-NNNN (§x–y)`. Later changes go in a dated addendum at the end.

## Reference documents

1. **Describe the present.** No "since 10-29", no "was X until". If the reader needs the history, link the record.
2. **Name the reader and write for them.** The quickstart's reader is an outsider with none of our data, banks or
   checkpoints. The field guide's reader is another Forge AI project. Neither knows our labels.
3. **Commands run as written.** Every command in the quickstart is a complete line that can be pasted. A comment
   never follows a line continuation. A placeholder is in `<angle brackets>` and is explained once.
4. **Check commands against the code at every user-facing change:** flags, defaults and paths against the argparse
   definitions. Defaults sized for our box are called out where an outsider's box differs.
5. **Organize by what the reader does,** not by the order features landed.
6. **A dated measurement is fine.** "Measured on a 7950X + 4090" or "62.1% as of 2026-11-07" is a fact with a date,
   not history.

## Code comments and docstrings

1. **Say what the code does now and why.** The incident that motivated it belongs in an ADR or the running record.
   The comment carries at most a pointer: `(ADR-0124)`.
2. **No amendments in place.** When behaviour changes, rewrite the docstring. Do not append "09-27: now it also…".
3. **A module's first line says what the module is,** not which milestone built it.
4. **No dates, run names or iteration numbers** in comments or `--help` text. A threshold's rationale is stated as a
   reason ("the learner holds about 35 GB at a step"), not as a story.
5. **Keep a comment proportionate.** If a constant needs more than three lines, the explanation belongs in a
   docstring or an ADR.
6. **A script's header names its ADR, or says it is a utility.**
7. **Free-prose docstrings stay.** State the contract, the units and shapes, and the non-obvious trap. No
   `Args:` / `Returns:` boilerplate is required.

Three comments already in the tree are the model: the module docstring of `anvil/training/rl.py`, the generator
note at `rl.py:1028`, and `stratified_draw` in `anvil/training/value_pretrain.py`.

## Sentences

These apply to every kind. The first four are the existing rule in CLAUDE.md.

1. Lead with the verdict.
2. One claim per sentence.
3. Say what changed and why it matters before the evidence.
4. Commit hashes and run ids appear only where they are the pin or the proof.
5. At most one parenthetical per sentence, and none nested. A second aside is a second sentence.
6. A semicolon joins two clauses at most. A list of three or more things is a list.
7. No chains of arrows. An arrow is for a literal before-and-after value, such as `0.374 → 0.256`.
8. Bold marks the verdict of a bullet or entry, once. A bold span opens and closes within one sentence.
9. Status words (closed, cleared, passed, promoted) are lowercase in prose. Capitals are allowed only as the first
   word of a verdict line.
10. A number carries its uncertainty and its basis: `0.6210 ± 0.0108` with the game count, and "paired" or
    "unpaired" when two are compared. Two figures for one comparison are each labelled.
11. A file is a link, not a bare path, in any document a person reads.

## Vocabulary

Project labels are fine in records. In reference documents and code comments, a label is either in the glossary
below or replaced by a description. Session ordinals ("evening 4", "session 3", "task #12") are never used outside
records.

One word, one meaning. Where a word has several today, the comment or sentence says which.

| Label | Meaning | Note |
|---|---|---|
| M*n* | A milestone | The table is in the root README |
| D*n* | A deliverable inside a milestone | Always written with its milestone outside records: "M9 D4" |
| Build *n* | A stage of M12's staged build | Build 4½ is the shakedown |
| arm | One configuration in a comparison at equal box time | |
| cell | One run inside a settings pass | |
| read | A winrate measurement over a fixed set of seeded games | A paired read plays two checkpoints on the same seeds |
| network-alone, with-lookahead | The checkpoint playing without and with the search | |
| day-zero | The checkpoint a run starts from, before its first iteration | |
| segment | One weekly slice of the big run, ended by `--wall-hours` | |
| boundary | An engine or data change after which earlier numbers are not comparable | |
| era | The span between two boundaries | Winrates are never compared across eras |
| promote | Make a checkpoint the checkpoint of record | |
| raw, corrected | A winrate before and after the Ante luck correction | |
| forkcheck | The fidelity test that proves a fork change is behaviour-identical | |
| pin | (1) The fork commit a run is tied to. (2) A numbered scoping decision in a plan | Two meanings: say "fork pin" or "scoping pin" |
| fork | (1) The Forge fork. (2) A lettered design alternative in a plan ("fork J") | Two meanings: say "the Forge fork" or "design fork J" |
| rung | (1) The rung-1 heads of M1. (2) M9's payment rungs. (3) A step of the ADR-0119 value-recipe ladder | Three meanings: always say which |
| the box | The one training machine | |

The meanings of "pin", "fork" and "rung" are my reading of the docs and need the user's confirmation.

## Applying it

- **Forward:** every new edit follows the guide from the day it is adopted.
- **Backfill, once:** CLAUDE.md's Now block was rewritten under the state rules on 2026-11-09, with the displaced
  text moved to the status archive. Still to do: reorganize the quickstart from §7 on for the outside reader; rewrite the module
  headers of `server.py`, `model.py`, `dataset.py`, `selfplay.py` and `value_pretrain.py`; fix the nine stale
  comments the review found. Code edits wait for a stop of the run.
- **At the closeout documentation pass:** the design doc, the field guide and the standing-rules prune, as already
  routed.
- **Never:** ADRs, the running record, devlogs and the status archive are not rewritten to match.

## Settled at adoption, and still open

The guide was adopted as drafted, so the draft's defaults stand until the user changes them.

1. **The caps** are 800 words for the Now block, 120 per bullet and 80 for the README's Status.
2. **Copies** carry an "as of" date and a pointer to CLAUDE.md. A script that stamps them is allowed and not built.
3. **Status words** are lowercase in prose, with capitals only as the first word of a verdict line.
4. **The guide lives here,** with its summary in CLAUDE.md.
5. **Still open: the dated comments.** About 370 exist. They are removed as files are touched; whether to do one
   pass at the closeout is the user's call then.
6. **Still open: the glossary's "pin", "fork" and "rung" rows** need the user's confirmation.
7. **Not yet brought inside the rules:** CLAUDE.md's state table (several cells carry history) and the map's
   tables. They are state documents and are rewritten at the next state-of-record change.
