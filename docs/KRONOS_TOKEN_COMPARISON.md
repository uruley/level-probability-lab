# Actual versus approximate dollar amount: token diagnostic

Ran on May 1, 2026 development data only. Twelve matching origins, spaced
20 minutes apart, used Base, 120 completed bars, 25 sampled paths, seed 42,
temperature 1.0 and top-p 0.9. No model training or July evaluation.

The diagnostic intercepts the tokenizer's actual encode call during normal
forecast inference. It saves the normalized inputs, both token components,
and complete sampled OHLC paths. Assertions verify identical normalized OHLCV
inputs and identical replicated input sequences across paths.

Results:

- Eleven of twelve input pairs produced identical token sequences and identical
  sampled OHLC paths. The dollar-input differences therefore did not reach the
  forecasting transformer as different tokens for those windows.
- At the remaining origin (12:09 New York bar start, 12:10 forecast cutoff),
  one token position changed in the second component; the first was unchanged.
  The maximum difference in median predicted closes was $0.0009765625, about
  one tenth of a cent.

This explains the near-identical paired forecasts observed in the development
check. It does not show that Kronos ignores dollar amount in general, that
time-and-sales has no value, or that either input mode has superior accuracy.
Token components are learned representations, not verified semantic labels.

Reproduce: `.venv/Scripts/python.exe scripts/compare_kronos_amount_tokens.py`.
Artifacts: `data/trade_amount_v1/token_comparison/report.json` and
`captured_tokens_and_paths.npz`. The report records pinned model/tokenizer
revisions, sampling settings, and amount-file/adapter hashes.
