# Synchronized input records

Kronos Lab writes version-1 JSON records under `data/kronos_lab/input_packages/`
when Base or Small forecasts are requested, including cached forecasts. The
saved August demo is excluded. Existing forecast ledgers are not rewritten.

Each content-addressed record contains:

- The simulated availability cutoff (last input bar start plus one minute).
- The exact frozen OHLCV window and supplied dollar amounts, with the amount mode.
- Separate companion trade measurements for those same minutes, when available.
- Model revision, seed, sample count, target timestamps, and raw sampled paths.
- Candle source name and checked trade-feature/raw-trade hashes.

Trade summaries currently come only from the audited May/June development file.
They are not additional Kronos inputs. July trade features are never loaded.
Missing trade minutes are marked missing; late, nonfinite, quality-rejected, or
OHLCV-mismatched minutes expose no feature values. Other dates remain usable for
candle replay but have unavailable companion trade data.

The eight existing trade measurements are trade count, mean size, maximum-size
fraction, size coefficient of variation, VWAP-relative-to-close basis points,
within-minute realized variation, known signed fraction, and unknown fraction.
New indicator columns await review of the feature specification.

Outcome snapshots are saved separately under `data/kronos_lab/outcomes/` after
replay steps. They reference the package ID and contain only revealed closes;
future closes remain null and missing outcomes retain their status. Input
records never gain labels or actual outcomes after creation.

These records describe replay-time availability, not a claim that historical
cached forecasts were generated on their original market date. Candle publication
lag is still assumed zero. Trade summaries use receive-time minutes. The package
ID identifies record content; it is not a cryptographic certification of the
entire raw candle file. A frozen forecast's input window remains authoritative.

Verification: 11 focused package/replay/amount tests pass. A cached May 1 Base
forecast produced a complete package with 120 candles and 120 trade minutes.
Revealing five outcomes left its input record byte-for-byte unchanged.
Token comparison, random-seed stability, and a full historical exposure audit
remain separate next steps; no companion model was trained here.
