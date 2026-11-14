# Binance Vision use boundary

Status: restrictive source-specific policy for the personal, non-production research scope. This document does not grant rights beyond the published Binance Vision Dataset Terms.

## Approved scope (preliminary)

The current preliminary assessment is limited to one individual's private, non-commercial, non-production historical research, subject to the complete Vision Dataset Terms and incorporated CC BY-NC-SA 4.0 license.

The assessment is based on the published terms and the Binance Public Data repository clarification in Issue #502. It is not legal advice, a signed legal opinion, or written permission from Binance Legal.

## Prohibited until separate written authorization

Do not use Binance Vision datasets or material derived from them for:

- commercial products, paid services, subscriptions, or monetized distribution;
- public or multi-user dashboards, APIs, feeds, datasets, or hosted services;
- redistribution, sublicensing, sale, rental, or commercial exploitation of raw or derived data;
- live proprietary trading execution, automated commercial order generation, or compensated signal distribution;
- de-anonymization or attempts to identify Binance customers from trade identifiers or market records.

Do not assume that multi-device synchronization, cloud backups, third-party storage, public demonstrations, model sharing, or exports are permitted. Keep the dataset local to the individual research environment until each proposed transfer/storage/distribution path has been reviewed against the full terms.

## Derived artifacts inherit source restrictions

The Vision Dataset Terms state that data derived from, calculated with, or extracted from the datasets—including charts, models, and derivative analytical indicators—are governed by the terms.

Therefore, source restrictions must propagate to:
- normalized observations and event records;
- features, indicators, labels, and model inputs/outputs;
- historical research snapshots and backtest results;
- charts, reports, exports, caches, and backups.

A transformed or aggregated representation must not be presumed unrestricted merely because raw rows are not included.

## Required source metadata

Any future source registry entry for Binance Vision must retain at least:
- source identifier and exact dataset family (Spot aggTrades);
- canonical source URL and retrieval timestamp;
- terms URL, version/date reviewed, and license identifier;
- allowed purpose: PERSONAL_NON_PRODUCTION_RESEARCH;
- distribution: PROHIBITED_WITHOUT_WRITTEN_AUTHORIZATION;
- derived-data restrictions: INHERITED;
- retention and deletion policy;
- checksum, archive date, and archive SHA-256 for each validated file;
- review status and reviewer/evidence reference.

Unknown rights or an unreviewed destination must fail closed.

## Operational boundary

Until Issue #68 is fully implemented and the retention design is approved:
- no automated download, polling, backfill, or adapter activation;
- no cloud upload, third-party sync, public repository attachment, or redistribution;
- no use in public demos, commercial workflows, or shared datasets;
- no inference of participant identity from anonymous trade records.

The offline archive validator is a local validation tool only. It does not authorize downloading, retaining, using, or redistributing an archive.

## Change of scope

If IWFI is to be shared with another person, distributed as an app/service, hosted, monetized, or used for trading execution, block this source and obtain written authorization/licensing appropriate to that exact use, or replace it with a source whose terms explicitly permit the intended use.

## Official references

- Binance Vision Dataset Terms: https://github.com/binance/binance-public-data/blob/master/TERMS_AND_CONDITIONS.md
- Binance Public Data README: https://github.com/binance/binance-public-data/blob/master/README.md
- Binance Public Data Issue #502: https://github.com/binance/binance-public-data/issues/502