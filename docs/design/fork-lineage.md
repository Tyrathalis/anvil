# Research fork lineage — every tip, newest first

**Doc status:** living · the research fork's commit chain with each tip's ADR-0025 proof (the current pin lives in CLAUDE.md)

Moved out of CLAUDE.md's state-of-record table on 2026-09-23 (the fluency pass); the cell as it
stood is in [status-archive.md](../status-archive.md) verbatim. Add a row on every fork commit that
reaches the pin. Checkout `../forge`; branch `master` (fast-forwarded, unpushed).

**How to read a proof.** Every tip below is ADR-0025-exempt (behavior-identical on the game path):
the same seed set on both jars gives identical `forkcheck` trace hashes. The misses that recur are
known, not regressions:

- **20260969** — the standing seed (a crash in the previous era); misses on every run.
- **The identity-hash residual** — 20260739 / 20260744 / 20260853 occasionally flip; each proof
  replays the flipped seed on the same jar to the baseline hash.
- **Fidelity 451/48/1** — the merge baseline's (`run-20260916-merge-baseline`); tips from the alloc
  tip on match it.

"Scope" says where the change can act: *off* = flag-gated and byte-identical when off;
*recording* / *search-copy* / *serve* / *replay* = only on that path.

## Era 2 — engine `97535e047f` (upstream 09-16, [ADR-0110](../decisions/ADR-0110-m12-upstream-merge-20260916.md))

| Tip | What | Scope | Forkcheck | PASS | ADR |
|---|---|---|---|---|---|
| `cd4b9d9951` | the pin + a test-only commit: the CI order-immunity pin in `CardMockTestCase` | tests only | — | — | — |
| **`05fea7938d` ← THE PIN** | certifier merge: `-replay`, the certifier's front over search copies (the pick hook, `replayNatural`, the pay SurfaceDirective's exec record, `trueLine` / `playRng` on runCopy) | recording / replay; off | `run-20260923-certmerge` 499/500, fidelity 451/48/1 | 09-23 12:33 | [0117](../decisions/ADR-0117-certifier-merge.md) |
| `cbe386d2c6` | census: `vr` unconditional, `act_vr` on the mainline's forced ask, `copy:true` on search-copy census rows | recording | `run-20260921-build4-census` 499/500, fidelity 451/48/1 | 09-21 11:53 | [0115](../decisions/ADR-0115-m12-shakedown-scoping.md), [0107](../decisions/ADR-0107-run-launcher-and-checkin.md) addendum |
| `57337a7e38` | void rescue: `-searchvoidrescue` + the `vr` void reason + `Obs.planJson` | search-copy / recording; off in the recipe | `run-20260919-build4-voidrescue` 499/500, fidelity 451/48/1 | 09-19 21:16 | [0114](../decisions/ADR-0114-m12-route-b-rescoped-void-rescue.md) |
| `a37bc6a8b4` | allocation: `-searchalloc` / `-searchfloor` + the `anvil.alloc` ask | off | `run-20260917-build4-alloc` 499/500, fidelity 451/48/1 | 09-17 15:45 | [0112](../decisions/ADR-0112-m12-build4-allocation-head-served.md) |
| `d734937c56` | `-vetofallback heuristic` | serve; off | `run-20260917-build4-vetofb` 499/500 (20260739 flip = the residual, replayed clean) | 09-17 05:45 | [0111](../decisions/ADR-0111-m12-build4-opening-targets-surface-site.md) |
| `7343c40d84` | the ability key on recorded stack entries | recording | `run-20260916-build4-stackak` 499/500 (20260853 flip replayed clean + identical) | 09-16 17:20 | [0111](../decisions/ADR-0111-m12-build4-opening-targets-surface-site.md) |
| `a36975497b` | `-modegate off` (the 09-16 evening's read jar) | serve | `run-20260916-build4-gate` 499/500 | 09-16 16:27 | [0111](../decisions/ADR-0111-m12-build4-opening-targets-surface-site.md) |
| `5dd8ab3ede` | target surface: `PlayerControllerAi.preparedTrigger` + `playTriggerTargets` | serve | `run-20260916-build4-targets` 499/500 | 09-16 15:50 | [0111](../decisions/ADR-0111-m12-build4-opening-targets-surface-site.md) |
| `23b8e36c03` | target surface: the callback hooks | serve | (proved with `5dd8ab3ede`) | — | [0111](../decisions/ADR-0111-m12-build4-opening-targets-surface-site.md) |
| `8137d0c41c` | the flip: views default on + headless console modes | — | `run-20260916-merge-flip` 499/500 vs the merge baseline (views-flag proof 499/500) | 09-16 12:24 | [0110](../decisions/ADR-0110-m12-upstream-merge-20260916.md) |
| `1db054ade4` | the riders | — | — | — | [0110](../decisions/ADR-0110-m12-upstream-merge-20260916.md) |
| `4112a89563` | **the merge** onto upstream 09-16 — a dataset boundary; baseline `run-20260916-merge-baseline` 451/48/1 | boundary | — | — | [0110](../decisions/ADR-0110-m12-upstream-merge-20260916.md) |

Tag `pre-merge-20260916` = era 1's tip `5e333e96930`.

## Era 1 — engine `23c3d2a85d`

Each tip sits on the one below it.

| Tip | What | Scope | Forkcheck | PASS |
|---|---|---|---|---|
| `5e333e96930` | deep: the partial-expansion slot, `-searchdeep` + the deep stage of the acting rule (requires `-searchact`) | search-copy / recording | `run-20260915-build3-deep` 499/500 | 09-15 22:15 |
| `e63a0cac20` | salt: `-searchrollsalt` — the copies' per-roll determinization seed salted, the rate draw unsalted | search-copy | `run-20260915-build3-e5salt` 497/500 (20260739 + 20260853 replay to baseline; 20260853's third replay: three distinct hashes over four runs) | 09-15 18:13 |
| `abec2b2982` | evening 5, mainline surface acting: the two-stage acting rule over the (option, answer) pair, `SurfaceDirective.armMainline` to the seat's next quiescent window, label-guarded, `-searchactkinds`; served trace label = the ability label. On the leaf plumb `de9745d089`: `-searchleaf next\|eot\|h<N>\|end` on the priority slot, the surface slot following, `snap` per roll | search-copy / recording; off | `run-20260914-build3-e5b` 498/500 (20260739 → baseline hash `9e0365815606ddf6`) | 09-15 00:30 |
| `1dd36f7342` | mana-source memo: `ComputerUtilMana.groupSourcesByManaColor` built once per `AnvilOptions` scan | bridged scan | `run-20260914-memo` 499/500; identity gate 32/32 games / 32,306 windows at one worker | 09-14 19:25 |
| `287e8cca45` | Build 3 e4 calibration: the pay slot's leaf family `-searchpayleaf next\|eot\|h<N>\|end` + the per-roll certify-axes `snap` + `-searchclock` | search-copy / recording | `run-20260909-build3-paycal` 499/500 | 09-09 19:54 |
| `15863de0b4a` | e4 probe: `quietProbe` — the payment probe (M9 enumeration + the auto-payability test) RNG- and memory-neutral on every bridged window | bridged path | `run-20260909-build3-e4p` 498/500 (20260744 → baseline hash) | 09-09 16:05 |
| `c26e99824b8` | e4 rescue: the ADR-0102 rescue class behind `-payrescue` | off | `run-20260908-build3-e4r` 499/500 | 09-08 20:55 |
| `e44d83a8327` | e4: the payment surface kind + the copy-side pay gate + the eot leaf + the pay expansion slot + the resolution-effect census row | serve / recording / search-copy | `run-20260908-build3-e4` 499/500 | 09-08 20:15 |
| `41ac60d6b21` | e3: the ordering + damage serve wire, the modern-rule damage enumerator family, the snapshot null guard | serve / recording / search-copy | `run-20260908-build3-e3` 498/500 (20260853 → `6ec06cb75d96f2b2` twice) | 09-08 14:30 |
| `bc01efe1609` | the mode playability gate | serve | `run-20260908-build3-gate` 499/500 | 09-08 11:30 |
| `1e17923c82c` | key fix: `AbilityKey.stripRuntime` | recording | `run-20260908-build3-keyfix` 498/500 (20260744 → `dbf25ab99ce90dee` twice) | 09-08 00:20 |
| `950f318a9e6` | e2: the mode enumerator fix + `Surface.repeat` + the sub-row frame + `mtg.surface.mode` | — | `run-20260907-build3-mode` 498/500 vs the 08-21 seeds (20260853 → `6ec06cb75d96f2b2` twice) | 09-07 20:50 |
| `1ac2ec8dc0b` | Build 3: the served-surface trace fix on `a0ed9e314b5` (= ability keys `b0567608938` + the surface serve wire) | — | 498/500 on `1ac2ec8dc0b` (20260739 → baseline); 497/500 on `a0ed9e314b5` (+ 20260853 → baseline) | 09-07 |
| `b4825285529` | Build 2: the acting rule `103747691cc` → the control arm `1d4b2d817c3` → the loop guard. The day-zero read ran on the `103747691cc` snapshot, the control arms on `b4825285529` | — | 498/500 vs the 08-21 seeds on both `103747691cc` (09-06) and `b4825285529` (09-07); 20260739 → baseline twice each | 09-07 |
| `6eb64b6c538` | Build 3 enumerators | — | 498/500 vs the 08-21 seeds (both misses the residual; 20260739 → baseline twice) | 09-06 s5 |
| `aac9f808bcf` | **Build 0 boundary tip** (ADR-0102; obs sv=3) — a dataset boundary | boundary | 497/500 vs the 08-21 seeds on the final jar (3 misses = the residual); the recording jar's ADR-0025 proof discharged by transitivity | 09-06 |

ADRs for era 1: Build 0 = [ADR-0102](../decisions/ADR-0102-m12-build0-pins.md); Builds 2–3 = the m12 plan's Build order and the
[running record](m12-running-record.md).
