# Release checklist

This package is release-ready for the current frozen-data snapshot once the
changes are reviewed and committed.

## Automated gates

- `make VENVPATH=.venv-repro guard-frozen check-inputs`
- `make VENVPATH=.venv-repro analysis`
- `.venv-repro/bin/python scripts/14_check_notebook_hygiene.py`
- `make VENVPATH=.venv-repro check-numbers`
- `make VENVPATH=.venv-repro paper`
- `git diff --check`

The release artifact is `ms/ms.pdf`. Analytical handoffs are the typed RDS
files under `analysis/`; table and figure outputs are generated under `tables/`
and `figures/`.

## Scope and limitations to retain in release notes

- The observational unit is an email address, not a politician.
- Address coverage and HIBP's public incident coverage make prevalence estimates
  lower bounds; they are not population rates for all politicians.
- There is no stable person identifier linking official and personal addresses,
  so within-politician comparisons are not identified.
- The serious outcome is formative. Sensitivity definitions are reported instead
  of treating the data classes as reflective scale items.
- Country regressions are descriptive associations with estimated country fixed
  effects, not causal effects.

## Manual release steps

1. Review the final PDF and generated tables/figures.
2. Confirm the frozen-input manifest has not changed.
3. Commit the source, typed handoffs, and generated publication artifacts.
4. Tag the reviewed commit with the data snapshot date.
