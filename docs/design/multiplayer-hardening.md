# Forge multiplayer hardening — what we contributed, and what the trust model actually guarantees

Between 2026-07-26 and 2026-07-30 the playable-fork track picked up a question
that started as a one-line note ("the multiplayer wire deserializes anything")
and ended as nine findings, four private reports to upstream, and three merged
fixes on public Forge master.

This document is the public record. It exists for two audiences: anyone hosting
Forge multiplayer who wants to know what the protocol does and does not
guarantee, and future-us, who will otherwise re-derive all of it.

**Scope note.** None of this is on the Anvil research path. It came out of the
[playable-fork worklist](playable-fork-worklist.md) — a human-facing
distribution build for a Commander night — and the engine changes are
upstream-shaped, not fork-shaped. The pinned research fork is untouched by all
of it.

## Outcome

Four reports went to upstream privately through GitHub security advisories.
Three were fixed and merged; two findings were declined, with reasoning, and
remain live in shipping builds.

| Report | Substance | Outcome |
|---|---|---|
| 1 | Lobby slot-type authorization; pre-login lobby disclosure | **Merged** `3e01055378` |
| 2 | Unrestricted Java deserialization on the wire | **Merged** `49e4bca114` |
| 3 | Host applies unvalidated amounts from a remote client | **Declined** |
| 4 | Connection/login limits; log and chat text injection | **Merged** `2df8aaab07` |

A fifth piece — chat rate limiting — was split out of report 4 at the
maintainer's request as anti-spam policy rather than a security fix, and went up
as an ordinary public PR ([#11457](https://github.com/Card-Forge/forge/pull/11457)).

All four advisories were closed without being published. The maintainer's
reason is a distribution-model one rather than a dismissal: advisories mainly
serve to tell users of old versions to upgrade, and Forge ships rolling
snapshots with no supported old releases, so there is nobody for an advisory to
notify. Every fix he agreed with was merged within about two days of
disclosure, one of them same-day.

## What the multiplayer trust model guarantees

The short version: **Forge multiplayer assumes every peer is friendly, and
that assumption is load-bearing in both directions.** This is not a criticism —
it is a reasonable design for a feature built to play with people you know, and
upstream has said as much. But it is worth stating plainly, because the hosting
flow can expose a port to the internet via UPnP, at which point "people you
know" stops being enforced by anything.

Two properties survive the fixes above and are, per upstream, working as
intended:

**A modified client can cheat, and the host will believe it.** The host asks
the client questions — how much combat damage to assign where, how to divide an
effect, how much shield to allocate — and applies the answers. We bounded the
four sites where the host hands out a budget and the client returns a split of
it, but upstream declined the patch on the grounds that this is one instance of
a much larger pattern: *"PlayerController has plenty of other methods that also
don't validate, this one isn't enough to matter."* That is true. Roughly 35
`getGui()` call sites take the client's word, and validating things like
`chooseSingleEntityForEffect` or `order` would mean re-deriving the rules
host-side. The honest summary is that **the host is not an authoritative
referee**, and a single bounds patch does not make it one.

**A disconnected seat can be reclaimed by anyone who knows the username.**
There is no reconnect secret; sharing a username is the reclaim mechanism.
Upstream considers this intended: *"simply sharing username in case another
remote player wants to take over instead is the way more likely scenario given
that we don't even have any global lobby."* We built a capability-token version
and it was declined as a feature question rather than a bug — the maintainer's
framing being that generated keys are annoying compared to a host-controlled
password.

Also unchanged, and known: **there is no transport security.** No TLS, no
authentication, plaintext TCP both directions. A hostile network path can read
and inject.

For a game among friends none of this matters much. For a publicly reachable
host, it is the whole picture.

## What the fixes actually do

**Report 2 — wire deserialization.** The transport handed the decompressed peer
payload straight to `readObject()`, with `resolveClass` accepting any class
name and no `ObjectInputFilter` anywhere in the tree. Now: a name allowlist
inside `CObjectInputStream`, outright refusal of proxy classes, and a cap on
decompressed bytes.

Three things about this were only learnable by building it:

- **There are two deserialization sinks, not one.** `TrackableSerializer`
  builds its own `CObjectInputStream` for the inner event layer. The obvious
  remediation — an `ObjectInputFilter` on the decoder — would have left that
  sink entirely unguarded. Filtering inside `CObjectInputStream` covers both by
  construction.
- **`resolveProxyClass` bypasses a name-based filter completely.** A proxy
  class descriptor carries no class name, so the JDK reads the interface list
  and never calls `resolveClass`. Our first filter had a hole exactly where the
  best-known gadget chains start.
- **The filter is a name check rather than JEP 290** because
  `ObjectInputFilter` is Android API 33 while `forge-gui-android` targets
  minSdk 26; using the API directly would have dropped Android 8–12.

The allowlist was derived from measurement, not guesswork: instrumenting the
stream and running upstream's own network harness produced 131 distinct wire
classes across real games — 87 `forge.*` plus JDK collections and Guava
collections, nothing exotic. Nineteen allowlist entries cover it, of which
three are prefixes, so new `forge.*` classes are free forever. One deliberate
soft spot is documented rather than quietly allowed: `SerializedLambda` is
admitted, because the protocol genuinely ships lambdas.

**Report 1 — lobby authorization.** The server accepted slot state it should
own (`type`, `aiOptions`, `aiProfile`) from clients, and pushed full lobby
state — including every slot's decklist — to peers that had merely completed a
TCP connect. Now the server strips server-owned fields from client updates, and
lobby state goes only to peers holding a slot.

**Report 4 — connection limits and text injection.** Every accepted channel
allocated a client object and a decoder before the peer proved anything, with
no cap on how many one source could hold open or how long they could sit
unregistered. Separately, remote text reached log lines and other players' chat
panes unescaped, so a newline in a chat message or a username forged log
records and a carriage return painted fake system messages in someone else's
client. Now: global and per-host connection caps, a login deadline, and a
`LogSafe` helper with two shapes — `forLog` escapes so a reader can still see
what was sent, `forDisplay` strips outright since a UI has no use for control
characters. Deliberately narrower than `StringEscapeUtils.escapeJava`, which
would render a CJK player's name unreadable in every log line.

**Not fixed, deliberately.** After login, every player still receives every
other player's full deck. It cannot simply be nulled — clients legitimately
read other slots' decks for sleeve art, and the lobby event ships live data by
reference — so redaction needs a per-recipient copy. That is its own patch.

## Method notes worth keeping

**Every claim carried a test that was watched to fail first.** Reverting each
fix before counting it caught four defects that would otherwise have shipped as
green ticks: a reconnect test that never reached the reconnect path, an
"overflow" test that could not overflow, a gadget stand-in declared inside the
test class and therefore named `forge.…` and allowlisted by the very prefix
under test, and a chat drain loop written as `while (allowChatMessage())` —
which terminates only if the limiter works, so under the fail-watch it spun for
hours and read as "still running" rather than failing.

**Standing rule from that last one: a test that can hang is worse than a test
that fails.** Bound the loop; put a timeout on every test in a security suite.

**False-rejection risk was measured, not hoped.** The worry about any allowlist
is that it rejects legitimate traffic and gets reverted. The stress-gated
network suite — draft, sealed, 100-game delta sync — ran 115 games with zero
legitimate classes rejected.

**A third-party audit was integrated, and its CVE table was dropped.** A friend
commissioned an audit (GPT-5.6 Sol Codex) that independently confirmed all nine
findings and added six we had not scoped, several cheaper and more practically
relevant than the deserialization one we started from. Its 64-advisory
dependency CVE table, however, was unverified and mostly 2026-dated, and its
own conclusion was that no listed CVE was reachable. It was never forwarded:
one hallucinated CVE ID sitting next to eight verified findings discredits the
findings. Take the findings, leave the table.

**Size is a review currency.** Report 1 was first offered at 14 files / +769,
mostly tests, and came back *"that's rather large."* Re-cut to 2 files / +46
with the surviving unit test as a separate droppable commit, it was taken
whole — test included. The useful datum: this maintainer takes tests when they
are cheap and unit-level.

**A dependent branch inherits its parent's rejected content.** Report 4 was
built on the full report 1, including the reconnect capability that had since
been declined. Pushing it as-is would have silently re-submitted 32 lines of a
fix the maintainer had explicitly rejected, buried in an unrelated patch —
the fastest available way to spend the credibility the first merge earned. The
check that works is mechanical: rebuild the dependent from current upstream and
grep the diff for the removed content **by name**.

**A guard keyed on file presence decays into a false positive.** A `pre-push`
hook refused pushes whose tree contained any of four marker files. It worked —
until report 4 merged, at which point a wholly public branch rebased onto the
new master tripped it, because the marker file was now a public file. Narrowed
on evidence (`git cat-file -e upstream/master:<path>` per marker), then
re-exercised in all four directions. A guard that cries wolf teaches you to
reach for its override.

## Where the code lives

The engine work was authored on clean upstream master in a separate worktree,
per the `#11203`/`#11285` pattern, and is now either upstream or fork-local:

- **Upstream:** reports 1, 2 and 4, merged as above.
- **Fork-local, on the `playable` distribution branch:** the report-3 amount
  bounds and the report-1 reconnect capability — the two declined findings.
  Both are ours to keep; neither is on the pinned research fork.
- **Public PR:** [#11457](https://github.com/Card-Forge/forge/pull/11457), chat
  rate limiting, switchable off outright since it is policy rather than
  correctness.

A longer-form internal note (`security/playable-multiplayer` branch) retains
the disclosure-process record: the private-contact sequence, the advisory-fork
mechanics, and the push-safety machinery used while the findings were unfixed.
None of that is needed to understand the outcome, which is what this document
is for.

## If this gets picked up again

The obvious next piece is the one upstream's own reasoning points at: not
another bounds patch, but a considered answer to *"the host is not an
authoritative referee."* That is a real design conversation about where
validation belongs, and it would want to start on Discord rather than as a
surprise PR. Nothing about it is urgent for a private Commander night, which is
why it is written down here rather than scheduled.
