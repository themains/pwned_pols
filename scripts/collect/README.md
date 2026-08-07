# Collection adapters

One adapter per source. Each turns a published source into rows of the canonical
table and does nothing else.

Adapters are **frozen**: they are listed in `FROZEN_NOTEBOOKS` in the `Makefile`
and never run as part of a build. `make guard-frozen` fails if a numbered
notebook here makes network calls without being listed. Running one is a
deliberate act, taken when the corpus is deliberately being changed, and is
followed by `make manifest`.

## The contract

Every adapter does exactly four things, in this order:

1. **Fetch** the source.
2. **Snapshot** the untouched payload to `data/raw/<source_id>/` **before
   parsing anything.** A parser bug must never cost a refetch, and the snapshot
   is what makes a row's provenance checkable later.
3. **Normalise** the address with `clean_email_column_no_dedupe()` from
   `scripts/utilities.py`, and classify it with `classify_comm_gov_email()`.
   Do not write a new normaliser. Two of the defects found in this repo came
   from re-deriving a rule that already existed — most recently `1bbc95f`, where
   the verification script and the pipeline had drifted onto different
   normalisations and agreed with each other while both were wrong.
4. **Emit** canonical rows, appending to `data/politician_emails.csv`.

## Canonical schema

`data/politician_emails.csv`, one row per (source, person, email):

| column | meaning |
|---|---|
| `source_id` | matches a row in `data/sources/registry.csv` |
| `person_id` | the source's own person key, stable within that source |
| `wikidata` | QID where the source supplies one, else empty |
| `name` | as published |
| `cc3` | ISO-3166 alpha-3 |
| `level` | `national`, `state`, `local`, `supranational` |
| `chamber` | as published, may be empty |
| `term_start` | year, may be empty |
| `email` | normalised |
| `email_raw` | exactly as published, before normalisation |
| `ecategory` | `Official` or `Commercial`, from `classify_comm_gov_email()` |
| `retrieved_date` | ISO date the fetch ran |
| `source_url` | the specific URL this row came from |

`email_raw` is kept because normalisation is lossy and deliberately so: it strips
a leading `1.`/`2.`, which is right for the source data and wrong in general.
Keeping the original means that choice stays auditable.

## Adding a source

Add a row to `data/sources/registry.csv`, write one adapter here, add it to
`FROZEN_NOTEBOOKS`, run it, then `make manifest`. No other file should need to
change — if it does, the abstraction is leaking and is worth fixing before the
next source rather than after.

## What does not belong here

Analysis. Merging the corpus into the analysis sample, deduplicating across
sources and reporting coverage all happen in `scripts/23_merge_email_corpus.R`,
which touches no network and does run in the build.
