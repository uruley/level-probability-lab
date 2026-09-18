# History file validation

File: `data/raw/XNAS_ITCH_a0bdd1f87cd3.ohlcv-1m.parquet`  
Request: `XNAS.ITCH` `ohlcv-1m` NVDA/QQQ/TSLA, 2018-05-01T00:00:00Z → 2026-09-01T00:00:00Z exclusive.  
Machine-readable: `data/reports/history_validation.json`  
**Nasdaq-feed research.** Not SIP/consolidated. Not fills. Models not fit.

## Verdict

The file is **usable for the frozen experiment**. Every NYSE regular session in range has bars for all three names. Same-session 15-minute labels **do not overlap** train → val → holdout → August development.

Treat the issues below as **documented exceptions**, not silent fills.

## Integrity

| Check | Result |
|---|---|
| Rows | 5,044,735 (matches quote) |
| UTC timestamps | yes; 2018-05-01 08:07Z → 2026-08-31 23:59Z |
| Duplicates | 0 |
| Sorted per symbol | yes |
| Volume null / negative / zero | 0 / 0 / 0 |
| RTH OHLC | clean |
| After-hours NaN OHLC | **6 rows** (see degraded days) |

The 6 NaN OHLC rows are QQQ/TSLA **outside regular hours** on Databento degraded days. They will be dropped before labeling (`dropna` on OHLC). They are not RTH prediction bars.

## Calendar coverage (NYSE regular session)

2,095 NYSE sessions in range, including 18 early closes. **0 missing sessions** for NVDA, QQQ, and TSLA.

| Symbol | RTH bars | Expected RTH minutes | Short sessions |
|---|---:|---:|---:|
| NVDA | 813,745 | 813,810 | 10 |
| QQQ | 813,740 | 813,810 | 14 |
| TSLA | 813,557 | 813,810 | 66 |

Shortfalls are missing **minutes**, not missing days. Databento `ohlcv-1m` omits minutes with no Nasdaq print (halts / LULD). Examples:

- **2020-03-09/12/16/18:** 376/390 minutes for all three (COVID circuit-breaker open; QQQ 2020-03-16 missing 09:31–09:44 ET as one block).
- **2018-08-07 TSLA:** 294/390; gap 14:09–15:44 ET (trading halt). That day also makes TSLA as-of context stale for some QQQ bars (96 QQQ RTH bars with TSLA lag > 60s; max 96 minutes). NVDA as-of: 0 missing, 0 stale > 60s.

Those blocks are longer than `max_no_trade_gap_minutes = 5`, so the labeler must mark affected horizons **`incomplete` / `coverage_gap`**, not `neither`.

## Degraded days (vendor)

| Date | RTH complete for QQQ/NVDA/TSLA? |
|---|---|
| 2021-07-07 | yes (390/390) |
| 2021-10-26 | yes (390/390) |
| 2022-09-19 | yes (390/390) |

The 6 NaN bars sit in **extended hours** on those dates. Keep the vendor flag; do not treat RTH as missing.

## Corporate actions (unadjusted Nasdaq prices)

Confirmed in the tape (open vs previous RTH close):

| Event | Open / prev close | Matches unadjusted split |
|---|---|---|
| TSLA 5-for-1 2020-08-31 | 444.55 / 2212.90 ≈ 0.201 | yes |
| TSLA 3-for-1 2022-08-25 | 302.38 / 891.34 ≈ 0.339 | yes |
| NVDA 10-for-1 2024-06-10 | 120.36 / 1208.65 ≈ 0.100 | yes |

QQQ has one overnight move ≥ 8% log: **2020-03-16** open 174.15 vs prior close 193.96 (crash, not a split). NVDA/TSLA have additional large overnight moves (earnings/crash); only the three split days match split ratios.

Same-session QQQ labels do not cross those overnight prints. **Do not use raw NVDA/TSLA price levels** as features across the split dates. NVDA’s split is inside **validation**.

## Cross-symbol as-of (QQQ RTH vs NVDA/TSLA)

No future leaks. NVDA is present for every QQQ RTH bar (median lag 0s). TSLA is present for every QQQ RTH bar; 96 bars (halt day) exceed the 60s stale threshold and must set `context_stale`.

## Partition overlap (same-session 15-minute horizon)

| Cut | Last left close UTC | Next open UTC | Overlap? |
|---|---|---|---|
| Train → val | 2023-12-29 21:00 | 2024-01-02 14:30 | no |
| Val → holdout | 2024-12-31 21:00 | 2025-01-02 14:30 | no |
| Holdout → August dev | 2026-07-31 20:00 | 2026-08-03 13:30 | no |

Still enforce `horizon_end <= next_partition_open` in code.

## Next

Label the history at frozen **k ∈ {2, 3, 4}**, then baselines and trees on the spec splits. Do not score August 2026 as holdout.
