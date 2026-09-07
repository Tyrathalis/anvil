#!/usr/bin/env python3
"""Generate CensusPlayerController.java from PlayerController's abstract methods.

Parses `public abstract ...;` declarations out of Forge's PlayerController.java and
emits a PlayerControllerAi subclass that logs every callback (method, turn, phase,
stack depth, cheap arg summaries) via Census, then delegates to super. Rerunnable
on engine bumps; the generated file is checked into the fork, this script into Anvil.

Usage: generate_census_controller.py [forge_dir]
Writes: <forge_dir>/forge-ai/src/main/java/forge/ai/anvil/CensusPlayerController.java
"""

import re
import sys
from pathlib import Path

FORGE = Path(sys.argv[1] if len(sys.argv) > 1 else Path.home() / "Everything/Projects/forge")
SRC = FORGE / "forge-game/src/main/java/forge/game/player/PlayerController.java"
DST = FORGE / "forge-ai/src/main/java/forge/ai/anvil/CensusPlayerController.java"

PRIMITIVE_LOG = {"int", "long", "byte", "boolean", "Integer", "Long", "Boolean", "String"}
SIZE_PREFIXES = (
    "List",
    "Collection",
    "Iterable",
    "Map",
    "Multimap",
    "ListMultimap",
    "Set",
    "CardCollection",
    "CardCollectionView",
    "FCollectionView",
    "PlayerZone",
)
NAME_TYPES = {"SpellAbility", "Card", "Player", "GameEntity", "WrappedAbility"}

# M1 D2: methods whose dec record needs more than the generic entry (Obs owns
# the implementation; the generator only swaps the call). Priority windows
# materialize the engine-legal option set into structured opts so the CastPlan
# label has a logged legality basis (replay drift forbids recomputing it later).
DEC_OVERRIDES = {
    "chooseSpellAbilityToPlay": "Obs.decPriority(getGame(), getPlayer())",
}

# M9 D3: methods whose CENSUS record routes through a hand-owned helper (the
# generated file stays logic-free). payManaCost carries the payment-surface
# flag telemetry when -paytelemetry is on (m9-payment-surface-spec.md §8).
REC_OVERRIDES = {
    "payManaCost": "PaymentTelemetry.rec(getGame(), getPlayer(), toPay, sa, prompt, effect)",
    # M11 mining-rung finding: 58% of these windows had an empty sa string —
    # the enriched record adds host card + api (attribution).
    "payCostToPreventEffect":
        "ChoiceDirective.recPrevent(getGame(), getPlayer(), cost, sa, alreadyPaid, allPayers)",
}

# M11-routing probes (m11-routing-probes-spec.md): methods with a
# -forcechoice directive hook — the generated wrapper asks ChoiceDirective
# BEFORE super and short-circuits when the directive fires (null = natural).
# The hook logic lives in ChoiceDirective; the generated file stays logic-free.
FORCE_OVERRIDES = {
    "chooseSingleEntityForEffect":
        "ChoiceDirective.forceEntity(getGame(), getPlayer(), optionList, sa, title)",
    "chooseSingleCardForZoneChange":
        "ChoiceDirective.forceZoneChange(getGame(), getPlayer(), fetchList, sa, selectPrompt)",
    "payCostToPreventEffect":
        "ChoiceDirective.forcePrevent(getGame(), getPlayer(), cost, sa)",
    # M10 cousins touch (2026-08-28): directed cousin commitments — the
    # payment window owner arms CousinDirective around the auto-completion;
    # unarmed (null) = natural heuristic play (ADR-0025 identity direction).
    "chooseCardsForConvokeOrImprovise":
        "CousinDirective.forceConvokeOrImprovise(getGame(), getPlayer(), sa,"
        " untappedCards, artifacts, creatures)",
    "chooseCardsToDelve":
        "CousinDirective.forceDelve(getGame(), getPlayer(), grave)",
}


# M12 Build 3 (ADR-0103): the decision SURFACES of design §3d′ as search
# tags. Each entry routes the wrapper's dec (named option list + unwalked
# option cards in the snapshot), an optional force hook (a SurfaceDirective
# armed on a search copy; null = natural) and an after-super trace hook (the
# heuristic's answer as indices, recorded on search copies for the monitor's
# expansion round). Logic lives in Surfaces; the generated file stays
# logic-free. A surface method must not also appear in FORCE_OVERRIDES.
SURFACES = {
    "chooseSingleEntityForEffect": {
        "kind": "Surfaces.ENTITY_ONE", "opts": "optionList",
        "force": "Surfaces.forceEntityOne(getGame(), getPlayer(), optionList, sa)",
        "after": "Surfaces.afterEntityOne(getGame(), getPlayer(), optionList, sa, __r)",
    },
    "chooseSingleCardForZoneChange": {
        "kind": "Surfaces.ENTITY_ONE", "opts": "fetchList",
        "force": "Surfaces.forceZoneChange(getGame(), getPlayer(), fetchList, sa)",
        "after": "Surfaces.afterEntityOne(getGame(), getPlayer(), fetchList, sa, __r)",
    },
    "chooseSingleSpellForEffect": {
        "kind": "Surfaces.ENTITY_ONE", "opts": "spells",
        "force": "Surfaces.forceSpellOne(getGame(), getPlayer(), spells, sa)",
        "after": "Surfaces.afterEntityOne(getGame(), getPlayer(), spells, sa, __r)",
    },
    "chooseEntitiesForEffect": {
        "kind": "Surfaces.ENTITY_SET", "opts": "optionList",
        "force": "Surfaces.forceEntitySet(getGame(), getPlayer(), optionList, min, max, sa)",
        "after": "Surfaces.afterEntitySet(getGame(), getPlayer(), optionList, min, max, sa, __r)",
    },
    "chooseCardsForEffect": {
        "kind": "Surfaces.ENTITY_SET", "opts": "sourceList",
        "force": "Surfaces.forceCardSet(getGame(), getPlayer(), sourceList, min, max, sa)",
        "after": "Surfaces.afterEntitySet(getGame(), getPlayer(), sourceList, min, max, sa, __r)",
    },
    "chooseCardsToDiscardFrom": {
        "kind": "Surfaces.ENTITY_SET", "opts": "validCards",
        "force": "Surfaces.forceCardSet(getGame(), getPlayer(), validCards, min, max, sa)",
        "after": "Surfaces.afterEntitySet(getGame(), getPlayer(), validCards, min, max, sa, __r)",
    },
    "chooseCardsToDiscardToMaximumHandSize": {
        "kind": "Surfaces.ENTITY_SET", "opts": "getPlayer().getCardsIn(ZoneType.Hand)",
        "force": "Surfaces.forceCardSet(getGame(), getPlayer(), getPlayer().getCardsIn(ZoneType.Hand),"
                 " numDiscard, numDiscard, null)",
        "after": "Surfaces.afterEntitySet(getGame(), getPlayer(), getPlayer().getCardsIn(ZoneType.Hand),"
                 " numDiscard, numDiscard, null, __r)",
    },
    "choosePermanentsToSacrifice": {
        "kind": "Surfaces.ENTITY_SET", "opts": "validTargets",
        "force": "Surfaces.forceCardSet(getGame(), getPlayer(), validTargets, min, max, sa)",
        "after": "Surfaces.afterEntitySet(getGame(), getPlayer(), validTargets, min, max, sa, __r)",
    },
    "choosePermanentsToDestroy": {
        "kind": "Surfaces.ENTITY_SET", "opts": "validTargets",
        "force": "Surfaces.forceCardSet(getGame(), getPlayer(), validTargets, min, max, sa)",
        "after": "Surfaces.afterEntitySet(getGame(), getPlayer(), validTargets, min, max, sa, __r)",
    },
    "chooseSpellAbilitiesForEffect": {
        "kind": "Surfaces.ENTITY_SET", "opts": "spells",
        "force": "Surfaces.forceSpellSet(getGame(), getPlayer(), spells, num, sa)",
        "after": "Surfaces.afterEntitySet(getGame(), getPlayer(), spells, 0, num, sa, __r)",
    },
    "orderSimultaneousSa": {
        "kind": "Surfaces.ORDER", "opts": "activePlayerSAs",
        "force": "Surfaces.forceOrderSa(getGame(), getPlayer(), activePlayerSAs)",
        "after": "Surfaces.afterOrder(getGame(), getPlayer(), activePlayerSAs, null, __r)",
    },
    "orderMoveToZoneList": {
        "kind": "Surfaces.ORDER", "opts": "cards",
        "force": "Surfaces.forceOrderCards(getGame(), getPlayer(), cards)",
        "after": "Surfaces.afterOrder(getGame(), getPlayer(), cards, source, __r)",
    },
    "orderBlockers": {
        "kind": "Surfaces.ORDER", "opts": "blockers",
        "force": "Surfaces.forceOrderCards(getGame(), getPlayer(), blockers)",
        "after": "Surfaces.afterOrder(getGame(), getPlayer(), blockers, null, __r)",
    },
    "orderAttackers": {
        "kind": "Surfaces.ORDER", "opts": "attackers",
        "force": "Surfaces.forceOrderCards(getGame(), getPlayer(), attackers)",
        "after": "Surfaces.afterOrder(getGame(), getPlayer(), attackers, null, __r)",
    },
    "arrangeForScry": {
        "kind": "Surfaces.SCRY", "opts": "topN",
        "force": "Surfaces.forceScry(getGame(), getPlayer(), topN)",
        "after": "Surfaces.afterScry(getGame(), getPlayer(), topN, __r)",
    },
    "arrangeForSurveil": {
        "kind": "Surfaces.SCRY", "opts": "topN",
        "force": "Surfaces.forceScry(getGame(), getPlayer(), topN)",
        "after": "Surfaces.afterScry(getGame(), getPlayer(), topN, __r)",
    },
    "chooseModeForAbility": {
        "kind": "Surfaces.MODE", "opts": "possible",
        "force": "Surfaces.forceMode(getGame(), getPlayer(), sa, possible, min, num, allowRepeat)",
        "after": "Surfaces.afterMode(getGame(), getPlayer(), sa, possible, min, num, __r)",
    },
    "chooseSomeType": {
        "kind": "Surfaces.NAME", "opts": "validTypes",
        "force": "Surfaces.forceName(getGame(), getPlayer(), validTypes, sa)",
        "after": "Surfaces.afterName(getGame(), getPlayer(), validTypes, sa, __r)",
    },
    "assignCombatDamage": {
        "kind": "Surfaces.DAMAGE", "opts": "blockers",
        "force": "Surfaces.forceDamage(getGame(), getPlayer(), attacker, blockers, damageDealt, defender,"
                 " overrideOrder)",
        "after": "Surfaces.afterDamage(getGame(), getPlayer(), attacker, blockers, damageDealt, defender,"
                 " overrideOrder, __r)",
    },
}
# chooseCardName is overloaded (faces list vs predicate); only the list form
# is a surface. Keyed by (name, first-param-type) below.
SURFACES_BY_SIG = {
    ("chooseCardName", "List<ICardFace>"): {
        "kind": "Surfaces.NAME", "opts": "faces",
        "force": "Surfaces.forceName(getGame(), getPlayer(), faces, sa)",
        "after": "Surfaces.afterName(getGame(), getPlayer(), faces, sa, __r)",
    },
}


def split_params(paramstr: str) -> list[tuple[str, str]]:
    """Split a parameter list at depth-0 commas; return (type, name) pairs."""
    params, depth, cur = [], 0, ""
    for ch in paramstr:
        if ch == "<":
            depth += 1
        elif ch == ">":
            depth -= 1
        if ch == "," and depth == 0:
            params.append(cur.strip())
            cur = ""
        else:
            cur += ch
    if cur.strip():
        params.append(cur.strip())
    out = []
    for p in params:
        p = re.sub(r"\bfinal\s+", "", p).strip()
        typ, name = p.rsplit(None, 1)
        out.append((typ, name))
    return out


def log_expr(typ: str, name: str) -> str | None:
    base = re.sub(r"<.*", "", typ)  # strip generics for classification
    if base in PRIMITIVE_LOG:
        return name
    if any(base == p or base.startswith(p) for p in SIZE_PREFIXES):
        return f"Census.sz({name})"
    if base in NAME_TYPES:
        return f"Census.str({name})"
    return None


def ai_return_types() -> dict[str, set[str]]:
    """Return types PlayerControllerAi declares per method name (it narrows some
    covariantly, e.g. chooseCardsToDiscardFrom -> CardCollection; our override
    must use the narrowed type or javac rejects it)."""
    ai_src = FORGE / "forge-ai/src/main/java/forge/ai/PlayerControllerAi.java"
    rets: dict[str, set[str]] = {}
    for line in ai_src.read_text().splitlines():
        m = re.match(r"\s*public\s+(?:final\s+)?(?:<[^>]+>\s+)?(.+?)\s+(\w+)\s*\(", line)
        if m and m[1] not in ("class", "return"):
            rets.setdefault(m[2], set()).add(m[1])
    return rets


def main() -> None:
    text = SRC.read_text()
    imports = [l for l in text.splitlines() if l.startswith("import ")]
    ai_rets = ai_return_types()

    methods = []
    for line in text.splitlines():
        line = line.strip()
        m = re.match(
            r"public abstract\s+(?P<tparams><[^>]+>\s+)?(?P<ret>.+?)\s+(?P<name>\w+)\s*\((?P<params>.*)\)\s*;",
            line.split("//")[0].strip(),
        )
        if m:
            methods.append(m)

    body = []
    for m in methods:
        tparams = (m["tparams"] or "").strip()
        ret, name, params = m["ret"], m["name"], split_params(m["params"])
        narrowed = ai_rets.get(name, set())
        if len(narrowed) == 1 and (n := next(iter(narrowed))) != ret:
            ret = n
        sig_params = ", ".join(f"{t} {n}" for t, n in params)
        call_args = ", ".join(n for _, n in params)
        kv = []
        for t, n in params:
            e = log_expr(t, n)
            if e is not None:
                kv.append(f'"{n}", {e}')
        kv_str = (", " + ", ".join(kv)) if kv else ""
        decl = f"public {tparams + ' ' if tparams else ''}{ret} {name}({sig_params})"
        # Obs (observation-schema-v1): observation at entry for every callback;
        # the answer joined at exit for non-void ones. Game passed to both so
        # stale threads (post hard-cap) can't write into the next game's frame.
        dec_call = DEC_OVERRIDES.get(name, f'Obs.dec(getGame(), getPlayer(), "{name}"{kv_str})')
        rec_call = REC_OVERRIDES.get(name, f'Census.rec(getGame(), getPlayer(), "{name}"{kv_str})')
        surf = SURFACES.get(name) or SURFACES_BY_SIG.get((name, params[1][0] if len(params) > 1 else None))
        if surf is not None:
            dec_call = (
                f'Surfaces.dec(getGame(), getPlayer(), "{name}", {surf["kind"]}, {surf["opts"]}{kv_str})'
            )
        if ret == "void":
            tail = f"        {dec_call};\n        super.{name}({call_args});\n"
        else:
            force = ""
            # M11 probe hook first (ChoiceDirective), then the surface force
            # hook (SurfaceDirective) — a copy arms at most one of them.
            hooks = [h for h in (FORCE_OVERRIDES.get(name), surf and surf.get("force")) if h]
            for hi, force_expr in enumerate(hooks):
                ftype = "Boolean" if ret == "boolean" else ret
                var = "__f" if hi == 0 else f"__f{hi}"
                force += (
                    f"        {ftype} {var} = {force_expr};\n"
                    f"        if ({var} != null) {{\n"
                    f"            Obs.ret(getGame(), __s, {var});\n"
                    f"            return {var};\n"
                    f"        }}\n"
                )
            after = f"        {surf['after']};\n" if surf and surf.get("after") else ""
            tail = (
                f"        long __s = {dec_call};\n"
                f"{force}"
                f"        {ret} __r = super.{name}({call_args});\n"
                f"{after}"
                f"        Obs.ret(getGame(), __s, __r);\n"
                f"        return __r;\n"
            )
        body.append(
            f"    @Override\n"
            f"    {decl} {{\n"
            f"        {rec_call};\n"
            f"{tail}"
            f"    }}\n"
        )

    # Keep only imports whose terminal class name is actually referenced in the
    # generated code (checkstyle rejects unused imports); star imports pass through.
    body_text = "\n".join(body)
    # Classes in PlayerController's own package are referenced without import in
    # the source; the generated file lives elsewhere and needs them explicitly.
    for f in sorted(SRC.parent.glob("*.java")):
        cls = f.stem
        if cls != "PlayerController" and re.search(rf"\b{cls}\b", body_text):
            imports.append(f"import forge.game.player.{cls};")
    extra = [
        "forge.ai.PlayerControllerAi",
        "forge.game.Game",
        "forge.game.player.Player",
        "forge.LobbyPlayer",
    ]
    kept = []
    for imp in imports:
        fqn = imp.removeprefix("import ").removesuffix(";").strip()
        if fqn in extra:
            continue
        cls = fqn.rsplit(".", 1)[-1]
        if cls == "*" or re.search(rf"\b{cls}\b", body_text):
            kept.append(imp)
    kept += [f"import {e};" for e in extra]

    DST.parent.mkdir(parents=True, exist_ok=True)
    DST.write_text(
        "// GENERATED by Anvil scripts/census/generate_census_controller.py — do not edit by hand.\n"
        f"// Source: PlayerController.java, {len(methods)} abstract methods.\n"
        "package forge.ai.anvil;\n\n" + "\n".join(sorted(kept)) + "\n\n"
        "public class CensusPlayerController extends PlayerControllerAi {\n"
        "    public CensusPlayerController(Game game, Player p, LobbyPlayer lp) {\n"
        "        super(game, p, lp);\n"
        "    }\n\n" + "\n".join(body) + "}\n"
    )
    print(f"{len(methods)} overrides -> {DST}")


if __name__ == "__main__":
    main()
