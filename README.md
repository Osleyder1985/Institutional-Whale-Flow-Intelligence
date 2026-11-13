# Institutional & Whale Flow Intelligence (IWFI)

**IWFI is a predictive market-intelligence platform for cryptocurrency prices.**

Its primary objective is to estimate future price direction, magnitude, target ranges, probable price zones, and time-to-target for a selected asset and forecast horizon. Every forecast must expose its evidence, uncertainty, data coverage, model version, and later measured outcome.

## Initial scope

- Pilot assets: BTC and ETH.
- Evidence families: market prices and liquidity, derivatives, on-chain activity, exchange and institutional flows, whale/entity attribution, news, and macro context when authorized and available.
- Forecasts are probabilistic and evidence-backed; no model is assumed predictive until it beats appropriate baselines in chronological out-of-sample tests.
- Forecast generation is user-initiated. No autonomous trading, background polling, or scheduled market analysis is enabled by default.

## Product definition

See [the official predictive objective](docs/product/predictive-objective.md) and [Issue #23: predictive requirements](https://github.com/Osleyder1985/Institutional-Whale-Flow-Intelligence/issues/23).

## Engineering principles

- Preserve source provenance, timestamps, quality, licensing, and retention limits.
- Do not equate transfers with trades, exchange flows with executed buys/sells, or correlation with causation.
- Prevent look-ahead/data leakage and validate with walk-forward, out-of-sample evaluation.
- Keep forecasts and outcome assessments immutable and reproducible.
- Do not invent probabilities, accuracy, performance thresholds, or causal explanations.
- Implement through reviewed pull requests; do not commit directly to `main`.
