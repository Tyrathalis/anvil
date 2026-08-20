# ADR-0065: M9 D3 rung 1 — engine capability audit: the engine CAN execute directed payments, including chained activation; the blind spot is one candidate-filter line in the auto-payer

- **Date:** 2026-08-19
- **Status:** accepted
- **Design-doc anchor:** [m9-plan.md](../design/m9-plan.md) D3 rung 1 +
  the D3 scope pins (same day); ADR-0064 (the artifact-stratum finding
  this explains mechanically); ADR-0062 (the veto-as-interface-artifact
  account)

## Question

Can the fork engine *execute* a directed mana payment it is handed —
including chained-activation payments (mana abilities that themselves
cost mana, e.g. Signets), which `ComputerUtilMana` cannot *construct*?
If yes, D3 rung 2's enumeration is archaeology over existing machinery;
if no, there is real engine work and the boundary bundle gets re-priced.
(Pre-registered fail routing: scope v1 to what the engine can execute;
executor funded only by a confirmed D5 mechanism.)

## Verdict: YES — the fail branch never fires

The game layer is chain-capable end to end. The chained-activation
blind spot is **one line of candidate filtering in the AI layer**, with
Forge's own comment naming it:

```java
// getAIPlayableMana, forge-ai/.../ComputerUtilMana.java:1668
// if a mana ability has a mana cost the AI will miscalculate
// if there is a parent ability the AI can't use it
if (cost.hasManaCost() || ...) continue;
```

Signet-class producers never enter `groupSourcesByManaColor` at all —
the blind spot lives in the **candidate set**, not the chooser, so both
construction and heuristic-path execution skip them.

## Findings (archaeology + empirical probe)

1. **The execution primitive is per-SA and generic.** The non-test body
   of `ComputerUtilMana.payManaCost` (lines ~769–777) is: pay the
   payment-SA's own costs via `CostPayment.payComputerCosts` →
   `stack.addAndUnfreeze(saPayment)` → `manapool.payManaFromAbility`.
   Nothing in the body cares where `saPayment` came from — a directed
   executor is this body with the heuristic chooser replaced.
2. **Nested payment chains are anticipated by the game layer.**
   `CostPartMana.payAsDecided` re-enters the *controller's*
   `payManaCost` for a payment ability's own mana cost, with an explicit
   `// restore old matrix during payment chains` and `costPaymentStack`
   push/pop re-entrancy bookkeeping. A Signet's `{1}` mid-payment is
   one-level recursion through the production flow.
3. **Color direction is controller-reachable.** Resolution-time color
   choices route through express choice (externally settable via
   `AbilityManaPart.setExpressChoice`) or the `chooseColor` /
   `specifyManaCombo` controller callbacks — all already overridden by
   `PlayerControllerAnvil`.
4. **Empirical probe: 4/4 green** —
   `forge-gui-desktop/src/test/java/forge/ai/simulation/DirectedPaymentAuditTest.java`
   (fork, standing regression asset, ConniveDiscardMapTest precedent):
   - heuristic REFUSES the arithmetically-payable chained board
     (I + I + Dimir Signet vs {1}{U}{B}) — the blind spot confirmed at
     engine level, with the Swamp positive control confirming it's the
     chain and nothing else;
   - **the directed chain executes and casts**: Island → float {U};
     Signet activation pays its own {1} from the float (the nested
     `payAsDecided` → controller `payManaCost` path); Island #2; the
     real AI cast path (`ComputerUtil.handlePlayingSpellAbility`) pays
     {1}{U}{B} entirely from the directed float; the spell resolves,
     pool empties.
   - express choice steers an any-color producer to the directed color.
5. **The trap has a concrete engine-side instance.** Legality-derived
   enumeration must build from `Card.getManaAbilities()` + `canPlay()`,
   NEVER from `getAIPlayableMana` — that helper *is* auto-payer-derived
   filtering (the exact interface trap the M9 design session named).
6. **`AI:RemoveDeck:All` discovery (Signet script line):** at match
   start `complainCardsCantPlayWell` only *reveals* AI-unplayable cards
   (the census `revealAISkipCards` records) — decks are NOT stripped;
   the cards sit in the library and then on the battlefield as dead
   weight to the auto-payer. Residual behavioral exclusions:
   `PlayEffect`/`CopyPermanentEffect` skip RemAIDecks cards when the AI
   resolves "play/copy a card" effects. The pool carries the class
   (Boros Signet = true chained producer; Arcane Signet/Talismans/Mind
   Stone/Fellwar in the wider artifact-mana family) — model-directed
   payment unlocks cards the heuristic treats as dead.

## Consequences

- **Rung 2 is funded as archaeology.** The fork delta stays as priced:
  consequential-payment flag + legality-derived class enumeration + one
  new answer shape. **Zero new engine execution code is needed** — the
  v1 executor strategy is *float-then-apply*: on the payment window,
  perform the directed mana-ability activations via the existing
  execution primitive (each self-contained, nested costs included),
  then let the cost pay from pool. The boundary bundle is NOT
  re-priced.
- **Payment-completion queue item 1 (directed-executor completion)
  RESOLVES AS MOOT** — it was conditional on the fail branch; the
  capability exists today. The queue's live items are the cousins
  (priority 2) and effect payments (priority 3).
- Class enumeration inherits finding 5 as a hard rule and finding 3 as
  its color-direction mechanism; yield-differing taps (the D2a-session
  pin) are expressible since each activation is directed individually.
- Finding 6 sharpens the D5 strength story: the payment head doesn't
  just collapse vetoes, it potentially activates a card class the
  auto-payer plays as blanks (and explains part of ADR-0064's
  artifact-stratum signal mechanically).
- `DirectedPaymentAuditTest` = the standing certification for the
  execution primitive; it rides every future engine bump like the
  connive pin.
