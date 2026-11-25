# ADR-0137: The attack-target head scores only legal defenders

- **Date:** 2026-11-24
- **Status:** accepted
- **Design-doc anchor:** anvil-design-v2 §4 (heads); the invariant "detection is the engine's job; response is the model's"; [ADR-0135](ADR-0135-m13-build3-arms.md), third addendum; [ADR-0122](ADR-0122-union-target-mask.md) (the target decoder's mask, the precedent)

## Context

**The control arm halted on the divergence guard at iteration 60.** The iteration's mean `kl_mu` was 0.062 against a line of 0.06. The running record of 11-24 holds the attribution in full.

**A handful of attack decisions tripped it.** A replay of iteration 60's training with a per-decision dump reproduces the halt. Seven attack decisions of 6,191 carry 266 to 5,820 nats each. Without decisions over 50 nats the iteration reads 0.039. A replay of iteration 50 has no attack decision over 1.5 nats; iteration 57 has five over 50.

**All of them are in the attack-target head, and the model was attacking permanents that cannot be attacked.** The head scored every entity row and both players, with no legality mask. Its docstring said serving masked "exactly via the executor"; nothing did. In game 28901 the model declared six attackers at Monumental Henge, the opponent's land, with probability 1, and the engine ended combat with no damage.

**The behavior starts at iteration 57.** Counted on the self-play store of each iteration, about 2,100 attack declarations each:

| Iteration | 0 | 20 | 40 | 50 | 53 | 54 | 55 | 56 | 57 | 60 |
|---|---|---|---|---|---|---|---|---|---|---|
| Declarations at a planeswalker | 87 | 68 | 107 | 95 | 98 | 108 | 90 | 111 | 86 | 89 |
| Declarations at an illegal permanent | 0 | 0 | 1 | 2 | 2 | 0 | 1 | 0 | 12 | 8 |

The illegal targets are lands, creatures and the creature face of flip-walkers. Why the model starts choosing them at iteration 57 is not established.

## Decision

1. **The encoder marks each entity row as a legal attack target or not** (`attack_target_ok` in `anvil/encoder/transform.py`; `assemble` returns `atk_tgt_ok`). A row is legal when it is on the battlefield and carries a defense counter, or carries a loyalty counter and an opponent controls it. The obs record has no type line; the counter is what defines a planeswalker or a battle on the battlefield, and it separates a flip-walker's two faces.
2. **The model masks the rest** (`_combat_outputs` in `anvil/policy/model.py`). Players are always legal. Serving and the learner share the code path, so the recorded log-probability and its recompute agree.
3. **The learner drops a game whose recorded attack names a masked row** (skip reason `atk_tgt_illegal`). Such a label would sit on a masked logit. These are games recorded before the mask.
4. **`ANVIL_NO_ATK_TGT_MASK=1` restores the unmasked head** for a control run. A batch without the field is also left unmasked.
5. **The legality test is an approximation held in Python.** The engine's own list of legal defenders in the declare-attackers request is the durable form. It needs a fork commit and is routed below.

## The proof

- **The mask removes no legal choice.** On the stores above, every declaration at a planeswalker lands on a row the encoder marks legal (0 masked of 87 at iteration 0; 0 of 111 at iteration 56).
- **Before iteration 57 it changes almost nothing.** It would have removed 0, 0, 1, 2, 2, 0, 1 and 0 declarations on iterations 0, 20, 40, 50, 53, 54, 55 and 56. A pick among legal rows is the same pick with the illegal rows removed, under argmax and under the sampler's per-key noise.
- **On a real checkpoint the logits are exact.** On `iter-056`, legal rows and players are identical with the mask on and off, every other row is masked, and a batch without the field equals the unmasked head.
- **A paired read sits inside serving noise.** `iter-056`, network alone, 400 games on one seed set: mask off 0.5750, mask off again 0.5750, mask on 0.5775. The two unmasked runs differ in 49 games; the masked run differs from them in 58 and 45. The first difference in each pair is a priority decision on an identical observation, which is the server's batch numerics and not the mask. A game-for-game identity proof is therefore not available on this instrument.
- **Tests:** two unit tests on the rule and its row order; the suite passes (499).

## Consequences

- **This is not a dataset boundary.** The engine is unchanged and the mask alters under one declaration in a thousand before iteration 57.
- **The control resumes from `iter-056` with the mask** (ADR-0135, third addendum). The search-off and soft-target arms run with it from `iter-405`.
- **The mask treats where the fault showed, not why it began.** The ordinary divergence also doubled by iteration 60, and the in-loop reads' priority vetoes tripled from iteration 54. Both are watched on the resumed control.
- **A standing rule is born:** a head's candidate set is the engine's legal set, in serving and in the learner alike; a superset "the engine will reject" is a training hazard.
- **Routed:** the engine's legal-defender list on the declare-attackers request, to the fork's next boundary. An audit of the other pointer heads for the same gap (block, the target decoder outside ADR-0122's mask, the surfaces), to the desk before the search-off arm. The guard's sensitivity to single decisions (a per-decision cap in the measure), to the loop config prune after the arms.

## Addendum (2026-11-25): the audit of the other heads

No other head has the attack-target head's gap. Two combat heads score a superset of the engine's legal set, at steady and small rates; their masks need the engine's lists and are routed with the defender list. Nothing here holds the search-off launch.

- **What made the attack-target head dangerous** was a softmax over every entity row, most of them rows the head never trained on. No other head has that shape.
- **The block pointer scores every attacker, legal to block or not.** The candidates are the attacking rows; whether this blocker can block that attacker (flying, menace, protection) is not known to the Python side. The engine drops an illegal block and counts it. In the control arm it dropped 36 to 55 of 764 to 1,005 declared blocks per iteration (4.7% to 5.7%) at iterations 0, 20, 40, 56, 61 and 64, with no trend. A dropped block is no block.
- **The attack yes-or-no head scores every untapped, unsick creature.** The engine drops a creature that cannot attack. It dropped 12 to 35 of about 7,000 attack assignments per iteration (0.2% to 0.5%), no trend, and as many behind the attack-target mask as before it.
- **Masked to the engine's own set, in serving and in the learner alike:** the priority choice (the wire's options), the target decoder (ADR-0122's legal-target union, keyed by the mu row's flag), the surfaces (the wire's options), the payment head (the wire's plans), the count heads and the number head (their ranges).
- **Not re-measured:** how often a target decision arrives without its legal-target union. ADR-0122 measured it.
- **Routed, with the defender list, to the fork's next boundary:** the engine's legal blockers per attacker and legal attackers on the combat requests, so both heads mask to them.
- **Instrument:** the per-iteration counts are the census rows of `declareAttackers` and `declareBlockers` answered by the bridge (`assign`, `dropped`).
