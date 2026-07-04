# DC card pool / decklist pipeline

**Status:** v0 spec, 2026-07-04. Implements design §8 source #2 (tournament decklists: "~80% of 'current meta' value for ~2% of the work") for the project's initial scope: 1v1 Duel Commander, curated ~1–2K card pool = union of DC meta decklists + flex slots.

**What it feeds:** the census re-run (M1 tag coverage), the M1 BC corpus (deck population the harness plays), and eventually Tutor's candidate pool (§5).

## Shape: two layers, acquisition vs derivation

1. **Acquisition** (network, incremental, append-only): fetchers download raw artifacts into `data/pool/raw/` and never interpret them. Every artifact keeps its source URL and fetch date. Re-running a fetcher only downloads what's new (deck IDs already on disk are never re-fetched). Politeness: ≥2s between requests, plain `urllib` with a browser UA, no parallelism.
2. **Derivation** (offline, deterministic): `build` reads the raw dir + curated inputs and emits the pool manifest, Forge `.dck` files, and an exclusions report. Same raw dir → same output, bit-for-bit (manifest content hash is the **pool version**).

This mirrors the harness's pinning discipline: raw acquisition is the messy boundary; everything downstream is reproducible from the raw dir. Per repo convention `data/` stays outside git (the manifest hash is the provenance anchor future `run.json`s reference), with two exceptions force-tracked because they are hand-curated *config*, not data: `data/pool/flex.txt` and `data/pool/overrides.json`.

## Sources

- **mtgtop8, format `f=EDH` ("Duel Commander")**: format page → event links (`event?e=<ID>&f=EDH`) → per-deck IDs (`e=<ID>&d=<DID>`) → decklist via the MTGO export endpoint (`mtgo?d=<DID>`). **Convention: the export's "Sideboard" section is the command zone** (DC has no sideboard) — one commander, or two for partner pairs; anything else fails validation and flags the deck for review. Partner-pairing legality is not re-checked (engine adjudicates). Exports decode with the server's declared charset (mtgtop8 serves iso-8859-1 — assuming utf-8 mangles Théoden et al.). Event metadata (name, date, player, rank) scraped from event pages into per-deck sidecar JSON.
- **duelcommander.com/banlist/**: banned/restricted cards are static HTML `data-card-name` attributes (117 at spec time) with section context (banned vs banned-as-commander). Snapshotted to `data/pool/raw/banlist-<date>.json`; the *newest* snapshot is authoritative at build time and its hash goes into the manifest.
- **Flex slots**: `data/pool/flex.txt`, hand-curated card names (one per line, `#` comments). Unioned into the pool, tagged `source: flex` in the manifest.

## Validation gates (derivation, in order)

1. **Parse/shape**: deck = 100 cards (99 + commander); singleton except basic lands (violations → deck excluded, reported).
2. **Name resolution vs Forge**: the supported-name universe is the `Name:` lines of the fork's `forge-gui/res/cardsfolder/` (cached keyed by fork commit). Resolution ladder: exact → case/diacritic-insensitive → split/DFC handling (`A // B` and front-face forms) → manual overrides file `data/pool/overrides.json` (`"printed name": "Forge name"`). Unresolvable card → deck excluded (a deck the engine can't load is worthless for BC), card listed in the report so an override or upstream card-script gap can be assessed.
3. **Banlist**: decks containing banned cards (or banned-as-commander commanders) are excluded *if the deck postdates the ban is unknowable from here* — so the rule is simply: current banlist applies to everything; historical decks with now-banned cards are excluded and counted. (Meta history matters for Tutor someday; the M1 pool wants currently-legal cards.)
4. Color identity / DC-specific legality is **not** re-implemented; Forge adjudicates at game setup (design invariant: the engine adjudicates). A smoke-load gate (below) catches what static checks miss.

## Outputs (all under `data/pool/`)

- **`pool-<hash8>.json` manifest**: pool card list (name, sources: which decks/flex, first-seen event date); deck list (id, source URL, event, date, commander, validation status); banlist snapshot hash; fork commit whose cardsfolder validated names; counts + exclusion tallies. The manifest hash is the pool version referenced by future `run.json`s (dataset-boundary discipline).
- **`decks/<deck-id>.dck`**: Forge deck files (`[metadata]/[Commander]/[Main]` sections, names only — no set pins; Forge picks printings). `install` copies them into the Forge profile's `decks/commander/` dir where the harness's `-d <name>.dck` resolution looks.
- **`report.md`**: exclusions with reasons, unresolved names ranked by frequency (the override/upstream-gap worklist), pool size trajectory.

## Smoke-load gate

`build` output isn't done until a sample of emitted decks (default: every commander at least once, capped) loads in the fork and plays one seeded game per pair via the existing harness (`launch --games 1`). A deck Forge rejects at load → back to the report. This is the pipeline's equivalent of the harness's zero-progress guard: static validation trusted only after the engine has eaten the output.

## CLI

`uv run python -m anvil.pool fetch [--since YYYY-MM] [--limit-decks N]` · `banlist` · `build` · `install` · `status`

## Known v0 limitations

- The mtgtop8 fetcher walks only the format landing page's event list (~30 most recent events + featured); the year archives ("All 2025 Decks" etc.) paginate through separate meta pages the fetcher doesn't crawl yet. Fine for a meta-current pool; extend before building a historical corpus.
- Event dates are scraped with a loose `dd/mm/yy` regex; events whose date doesn't parse are kept regardless of `--since` (fail-open, counted in sidecars as `date: null`).
- The smoke-load gate is manual at v0 (run one seeded game via `forge anvil` on a pair of built decks); wiring it into `build` as an automatic sample comes when the census re-run needs it anyway.

## Non-goals (v0)

- No archetype clustering, no meta-share weighting (Tutor-era concerns).
- No video/MTGO log sources (§8 sources 3–4 are separate tracks).
- No automatic upstream card-script gap filing — the report is the worklist, filing is manual.
