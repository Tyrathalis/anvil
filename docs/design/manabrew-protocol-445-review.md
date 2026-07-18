# manabrew protocol v1 (PR #445) — AI-decision-coverage review

2026-07-18. M3 plan D3(c): review manabrew's protocol against Anvil's
decision-surface census (109 PlayerController callbacks, 64 firing on the
competitive pool, [callback-census-results.md](callback-census-results.md))
and the traps catalogued in the field guide. Deliverable = the gap list
below, posted to their PR. Source: `feat/protocol-v1` branch,
`manabrew-protocol` crate (19 prompt types), extracted 2026-07-18.

## What the protocol gets right (worth saying on the PR)

- **Engine-legal advertised actions** (`ChooseAction.actions`, answers
  validated by `UnknownActionId`): the same foundation as our ADR-0005
  candidate basis — the agent picks from what the engine offers, never
  fabricates. Alt-cost modes baked into the *offered* action is clean.
- **Composite one-shot combat declarations** (full attacker/blocker maps in
  one message, whole-declaration re-prompt on invalid) — ahead of Forge's
  native human path, and exactly what combat heads want.
- **`PayManaCost.UseResource{Convoke|Improvise|Delve}`** — first-class
  resource payment; caps the AI re-evaluation loop our census caught at
  2,788 calls in one game.
- Stale-prompt rejection, typed response validation, out-of-band concede.

## Gap list (AI/training dimension)

1. **No decision provenance on responses.** Nothing marks an answer as
   agent-made vs bot-takeover vs engine auto-fill (`Pay{auto}` is the one
   per-prompt exception; `queued_responses`/bot substitution leave no
   trace). This is the silent-fallback corpus-poisoning trap (Austinio's
   "fake wins" bug; our standing `by=bridge` provenance rule + 0-fallback
   gates). Suggestion: an `answered_by` (or `provenance`) field on
   `Response` or in the observation envelope. Cheapest high-value addition
   on the list.
2. **No per-game determinism seed in the protocol.** Only draft/sealed
   lobby seeds exist; `GameStarted` carries no engine seed and the replay
   cache is a reconnect snapshot, not a re-simulation log. For training
   harnesses (including their own parity suite), a seed field on game start
   plus a documented "same seed + same responses ⇒ same game" contract
   would make trajectories reproducible at the protocol level. (Pairs with
   the determinism-hooks PR / #11260 work engine-side.)
3. **Casting is fully micro-step with no mid-cast abort or atomic commit.**
   `Act{action_id}` carries no targets/X/modes; each arrives as a follow-up
   prompt. Workable for AI (we micro-step mid-resolution choices too), but
   two consequences worth designing for: (a) the factored-decision coupling
   problem — the agent commits to the spell before seeing what targets it
   will be offered (the "choose spell, then forced into a bad target" trap
   several community RL projects hit); (b) `ChooseBoardTargets` has no
   Cancel, so a cast can't abort once started (PayManaCost can). Suggestion:
   an optional Cancel on mid-cast prompts now; optionally, later, a
   composite cast envelope (action + targets + X in one answer) as an
   opt-in for agents that plan jointly — our CastPlan exists for exactly
   this and we're happy to share the shape.
4. **`GameOver` input is empty.** Winner/termination reason live only in
   the observed state stream (`ObservedOutcome` is server-internal). For
   headless training, explicit outcome + termination-reason (win/concede/
   draw/timeout) on `GameOver` removes a fragile state-diff join — and
   winner-attribution bugs are quietly catastrophic for value learning (we
   lost a corpus-worth of value labels to one; ADR-0013).
5. **Noncombat amount allocation has no prompt.** Divided-as-you-choose
   effects (Fireball-class splits, distribute counters) have no obvious
   home — `ChooseCombatDamageAssignment` is combat-shaped. If the engine
   handles division internally today, fine; otherwise the combat-assignment
   shape generalizes (`assignments: Vec<{assignee, amount}>` + source).
6. **`prompt_id` semantics for trajectory joins.** If `prompt_id` is unique
   and monotonic per game (across reconnects/re-prompts), (game_id,
   prompt_id) is a sound trajectory key for training-data joins; worth
   documenting as a guarantee. The `ChooseBlockers.error` re-prompt and the
   `ChooseBoardTargets.chosen_targets` running counter suggest re-issues —
   fresh ids per re-issue is the join-safe choice (it's what our re-ask
   machinery does).

## Census-coverage spot checks (no action needed, recorded for us)

- Simultaneous-trigger ordering (12.6/game) → `Reorder` ✓; replacement/
  static choice family (9.6 + 9.1/game) → `ChooseFromSelection` ✓; optional
  costs (29/game) → follow-up Boolean/Number prompts, micro-step ✓; X →
  `ChooseNumber` ✓; London put-back → `MulliganPutBack` (bottom *order*, if
  it ever matters, would route through `Reorder`).
- `RestoreSnapshot{checkpoint_id}` on ChooseActionOutput = the undo path —
  the snapshot-restore consumer noted in the consolidation follow-up
  context (their correctness rides GameSnapshot restore).

## Disposition

Comment POSTED 2026-07-18 (user's voice, all six items + CastPlan offer):
https://github.com/witchesofthehill/manabrew/pull/445#issuecomment-5012708413. Interop remains optional per the M3 plan — this review is
the committed deliverable.
