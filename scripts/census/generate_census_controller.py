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
    "List", "Collection", "Iterable", "Map", "Multimap", "ListMultimap", "Set",
    "CardCollection", "CardCollectionView", "FCollectionView", "PlayerZone",
)
NAME_TYPES = {"SpellAbility", "Card", "Player", "GameEntity", "WrappedAbility"}


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
        if ret == "void":
            tail = (
                f'        Obs.dec(getGame(), getPlayer(), "{name}"{kv_str});\n'
                f"        super.{name}({call_args});\n"
            )
        else:
            tail = (
                f'        long __s = Obs.dec(getGame(), getPlayer(), "{name}"{kv_str});\n'
                f"        {ret} __r = super.{name}({call_args});\n"
                f"        Obs.ret(getGame(), __s, __r);\n"
                f"        return __r;\n"
            )
        body.append(
            f"    @Override\n"
            f"    {decl} {{\n"
            f'        Census.rec(getGame(), getPlayer(), "{name}"{kv_str});\n'
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
    extra = ["forge.ai.PlayerControllerAi", "forge.game.Game", "forge.game.player.Player", "forge.LobbyPlayer"]
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
        "package forge.ai.anvil;\n\n"
        + "\n".join(sorted(kept))
        + "\n\n"
        "public class CensusPlayerController extends PlayerControllerAi {\n"
        "    public CensusPlayerController(Game game, Player p, LobbyPlayer lp) {\n"
        "        super(game, p, lp);\n"
        "    }\n\n" + "\n".join(body) + "}\n"
    )
    print(f"{len(methods)} overrides -> {DST}")


if __name__ == "__main__":
    main()
