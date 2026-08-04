.DEFAULT_GOAL := help

########################################################################\
Make gitignore file
########################################################################
.PHONY: giti
giti: ## Make .gitignore from gitignore.io
	@echo "==> $@"
	rm -rf .gitignore
	echo "venv*" > .gitignore
	echo "Copy*.ipynb" >> .gitignore
	echo "scratch/*" >> .gitignore
	echo "*xlsx" >> .gitignore
	echo "**/*.tar.gz" >> .gitignore
	echo "**/*.csv*" >> .gitignore
	echo "**/*.xls" >> .gitignore
	echo "**/*.xlsx" >> .gitignore
	curl https://www.toptal.com/developers/gitignore/api/python >> .gitignore
	curl https://www.toptal.com/developers/gitignore/api/jupyternotebooks >> .gitignore
	curl https://www.toptal.com/developers/gitignore/api/tex >> .gitignore


# ============================================================================
# Set up the Python virtual environment and prepare the Jupyter distribution
# Installs packages from requirements.txt
# ============================================================================
.PHONY: setup
VENVPATH ?= venv
ifeq ($(OS),Windows_NT)
	VENVPATH :=  c:/users/admin/$(VENVPATH)
	ACTIVATE_PATH := $(VENVPATH)/Scripts/activate
else
	ACTIVATE_PATH := $(VENVPATH)/bin/activate
endif
REQUIREMENTS := requirements.txt
setup: ## Set up venv	
setup: $(REQUIREMENTS)
	@echo "==> $@"
	@echo "==> Creating and initializing virtual environment..."
	rm -rf $(VENVPATH)
	python -m venv $(VENVPATH)
	. $(ACTIVATE_PATH) && \
		pip install --upgrade pip && \
		which pip && \
		pip list && \
		echo "==> Installing requirements" && \
		pip install -r $< && \
		jupyter contrib nbextensions install --sys-prefix --skip-running-check && \
		echo "==> Packages available:" && \
		which pip && \
		pip list && \
		which jupyter && \
		deactivate
	@echo "==> Setup complete."


# ============================================================================
# Open Jupyter notebook in the venv
# ============================================================================
.PHONY: jn
jn: ## Launch jupyter notebook in venv
	@echo "==> $@"
	if [ -f $(VENVPATH)/Scripts/activate ]; then \
		. $(VENVPATH)/Scripts/activate && jupyter notebook; \
	elif [ -f $(VENVPATH)/bin/activate ]; then \
		. $(VENVPATH)/bin/activate && jupyter notebook; \
	else \
		@echo "No venv found"; \
	fi


########################################################################
# Data collection and assembly are OUT OF BOUNDS
########################################################################
# These notebooks acquire or assemble the data and NONE may run as part of a
# build. Numbering follows the post-merge scheme:
#
#   01_everypol_walkthrough                 EveryPolitician API
#   02_everypol_download_csvs               requests.get per legislature term
#   03_download_hibp_everypol_..._breaches  HIBP API, ~12,900 addresses @ 7-10s
#   04_hibp_everypol_ind_eur_combine        HIBP JSON -> the combined CSVs
#   05_validate_email_domains               DNS MX lookups
#   10_country_covariates                   World Bank, CEPII, V-Dem downloads
#
# guard-frozen checks BOTH directions, because the first version did not. A
# renumbering left it guarding four names that no longer existed, so it passed
# vacuously while the real HIBP notebook went unguarded. It now fails if a
# guarded name resolves to no file, AND if any numbered notebook makes network
# calls without being listed -- the second check is what caught
# 10_country_covariates.
#
# 01/02/03/05/10 cannot reproduce: HIBP has ingested new breaches since January
# 2025, EveryPolitician has moved on, and 150 of the 154 domains 05 rejects
# failed on transient DNS timeout rather than NXDOMAIN, so sample membership
# shifts run to run.
#
# 04 touches no network, but it rewrites the assembled inputs, and it writes
# scraped_pol_combined_legislature_data.csv BEFORE it can fail, so a mid-run
# error clobbers it. Re-running it also yields 6,715x98 against the shipped
# 6,660x101 (it gains 55 rows and drops four pagination columns that an
# uncommitted combine_ls_dat.ipynb had merged in). Downstream output is
# equivalent either way, but the analysis conditions on the shipped file, so
# nothing regenerates it.
#
# The analysis therefore starts from these frozen inputs:
FROZEN_INPUTS := \
	data/everypol/everypol_combined_legislature_data.csv \
	data/scraped_pol_combined_legislature_data.csv \
	data/everypol_hibp.csv \
	data/scraped_pol_hibp.csv \
	data/breaches_01_2025.csv \
	data/edomain_validation.csv \
	data/popsize.csv \
	data/country_fes_covariates.csv \
	data/benchmark/YGOV1058_pwned.csv \
	data/benchmark/YGOV1058_profile.csv \
	data/benchmark/yougov_breaches.json \
	data/benchmark/florida_breaches.json

FROZEN_NOTEBOOKS := 01_everypol_walkthrough 02_everypol_download_csvs \
	03_download_hibp_everypol_india_eur_breaches \
	04_hibp_everypol_ind_eur_combine 05_validate_email_domains \
	10_country_covariates

.PHONY: guard-frozen
guard-frozen: ## Assert no build target runs a data collection/assembly notebook
	@echo "==> $@"
	@fail=0; \
	for nb in $(FROZEN_NOTEBOOKS); do \
		if [ ! -f scripts/$$nb.ipynb ]; then \
			echo "  FAIL: $$nb is guarded but no such notebook exists."; \
			echo "        A rename left this guard pointing at nothing, which is"; \
			echo "        how it silently stops protecting anything. Update the list."; \
			fail=1; continue; \
		fi; \
		if grep -n "nbconvert.*$$nb\|execute.*$$nb" $(MAKEFILE_LIST) | grep -qv '^\s*#'; then \
			echo "  FAIL: a target would execute $$nb"; fail=1; \
		fi; \
	done; \
	for nb in scripts/[0-9][0-9]_*.ipynb; do \
		b=$$(basename $$nb .ipynb); \
		case " $(FROZEN_NOTEBOOKS) " in *" $$b "*) continue;; esac; \
		if grep -lq "requests\.get\|requests\.post\|EveryPolitician(\|dns\.resolver\|webdriver" $$nb 2>/dev/null; then \
			echo "  FAIL: $$b makes network calls but is not in FROZEN_NOTEBOOKS"; fail=1; \
		fi; \
	done; \
	if [ $$fail -eq 1 ]; then exit 1; fi; \
	echo "  ok: no target executes a collection/assembly notebook"

.PHONY: manifest
manifest: ## Record checksums of the frozen inputs (run once, after a deliberate data change)
	@echo "==> $@"
	@shasum -a 256 $(FROZEN_INPUTS) > data/FROZEN_INPUTS.sha256
	@echo "  wrote data/FROZEN_INPUTS.sha256"

.PHONY: check-inputs
check-inputs: ## Fail if a frozen input changed since the manifest was recorded
	@echo "==> $@"
	@if [ ! -f data/FROZEN_INPUTS.sha256 ]; then \
		echo "  no manifest; run 'make manifest' first"; exit 1; fi
	@shasum -a 256 -c data/FROZEN_INPUTS.sha256 --status \
		&& echo "  ok: all $(words $(FROZEN_INPUTS)) frozen inputs unchanged" \
		|| { echo "  FAIL: a frozen input changed --"; \
		     shasum -a 256 -c data/FROZEN_INPUTS.sha256 2>&1 | grep -v ': OK$$' | sed 's/^/    /'; \
		     echo "    If deliberate, re-run 'make manifest'."; exit 1; }

########################################################################
# Manuscript
########################################################################
# Everything below is local-file processing only -- verified no requests.get,
# dns.resolver, webdriver or EveryPolitician() in the analysis stages 06/07/08/
# 09/11. (The numbers here used to name 03/05/10, which are the *frozen*
# collection notebooks -- a renumbering artefact. guard-frozen is the machine
# check; this comment is only the human-readable half.) These rebuild every
# table, figure and manuscript number from the frozen inputs.

# The notebooks carry a "python3" kernelspec that resolves to whatever python3
# kernel is registered globally -- on at least one machine that is a deleted
# anaconda env, so nbconvert dies with FileNotFoundError before running a cell.
# Register a kernel inside the venv (--sys-prefix, so it lives in
# $(VENVPATH)/share/jupyter and not in the user's global kernel list) and name
# it explicitly on every execute.
KERNEL := pwned_pols
NBEXEC = $(abspath $(VENVPATH))/bin/jupyter nbconvert --to notebook --execute \
	--ExecutePreprocessor.kernel_name=$(KERNEL) --inplace

.PHONY: kernel
kernel: ## Register the venv's Jupyter kernel (idempotent, venv-local)
	@$(abspath $(VENVPATH))/bin/python -m ipykernel install --sys-prefix \
		--name $(KERNEL) --display-name "$(KERNEL)" >/dev/null 2>&1

.PHONY: analysis first-stage crosscountry benchmark
analysis: ## Re-run analysis stages 06/07/08/09/11/17/18
analysis: benchmark
	@echo "==> $@ complete"

first-stage: guard-frozen kernel
	@echo "==> $@"
	@# 06_everypol_summ.R is the R port; it builds email_lvl_cov.csv and five
	@# table fragments, and it carries three correctness fixes the notebook does
	@# not (order-independent dedup, symmetric case normalisation, a pruned
	@# DELINQUENTS list). The .ipynb of the same number is kept for reference.
	cd scripts && Rscript 06_everypol_summ.R
	cd scripts && for nb in 07_breach_summ 09_breach_rate_evolution; do \
		$(NBEXEC) --ExecutePreprocessor.timeout=2400 $$nb.ipynb || exit 1; \
	done
	cd scripts && Rscript 08_breach_prob.R && rm -f Rplots.pdf

crosscountry: first-stage
	@echo "==> $@"
	cd scripts && Rscript 11_crosscountry.R

benchmark: crosscountry
	@echo "==> $@"
	@# 17 classifies every breach by how the data got out; 18 compares the
	@# politician sample against the YouGov (and, once retrieved, Florida)
	@# population samples on a common catalogue and a common construct. 18
	@# depends on 17's analysis/breach_taxonomy.rds, so the order is fixed.
	cd scripts && Rscript 17_breach_taxonomy.R
	cd scripts && Rscript 18_three_sample_comparison.R
	@# 19 collapses EveryPolitician to one row per person and reports the
	@# address coverage that determines whether a within-politician comparison
	@# is identified. It reads a frozen input and touches no network.
	cd scripts && Rscript 19_person_key.R

.PHONY: check-notebooks
check-notebooks: ## Fail if an analysis notebook carries stale or errored output
	@echo "==> $@"
	cd scripts && $(abspath $(VENVPATH))/bin/python 14_check_notebook_hygiene.py

.PHONY: tables-ms
tables-ms: ## Wrap pipeline fragments into the table_*/regtab files ms.tex inputs
	@echo "==> $@"
	cd scripts && $(abspath $(VENVPATH))/bin/python 12_format_ms_tables.py

.PHONY: check-numbers
check-numbers: ## Assert every headline number in ms.tex still matches the data
	@echo "==> $@"
	cd scripts && $(abspath $(VENVPATH))/bin/python 13_check_ms_numbers.py --verbose

.PHONY: paper
paper: ## Compile ms/ms.pdf (runs tables-ms first)
paper: tables-ms
	@echo "==> $@"
	-@BIBINPUTS="ms:" TEXINPUTS=".:ms:" BSTINPUTS="ms:" latexmk -pdf -f \
		-interaction=nonstopmode -outdir=ms ms/ms.tex >/dev/null 2>&1
	@# latexmk's exit code is not the gate. A missing figure that a co-author
	@# has yet to supply should not fail the build, but an undefined reference
	@# or citation always should -- those mean the prose and the artifacts have
	@# come apart, which is the failure this whole pipeline exists to catch.
	@test -f ms/ms.pdf || { echo "  FAIL: no PDF produced"; exit 1; }
	@cites=$$(grep -c 'Citation.*undefined' ms/ms.log || true); \
	 refs=$$(grep -cE "Reference \`" ms/ms.log || true); \
	 missing=$$(grep -oE "File \`[^']+' not found" ms/ms.log | sort -u); \
	 if [ -n "$$missing" ]; then \
		echo "  pending inputs (not fatal):"; echo "$$missing" | sed 's/^/    /'; \
	 fi; \
	 if [ "$$cites" != "0" ] || [ "$$refs" != "0" ]; then \
		echo "  FAIL: $$cites undefined citation(s), $$refs undefined reference(s)"; \
		exit 1; \
	 fi; \
	 echo "  ok: 0 undefined citations, 0 undefined references"
	@echo "==> wrote ms/ms.pdf"

.PHONY: paper-clean
paper-clean: ## Remove LaTeX build artifacts
	@echo "==> $@"
	latexmk -C -outdir=ms ms/ms.tex

.PHONY: verify
verify: ## Full rebuild from frozen inputs: inputs -> analysis -> tables -> numbers -> paper
verify: guard-frozen check-inputs analysis check-notebooks tables-ms check-numbers paper
	@echo "==> $@ complete"

########################################################################
# Other utilities
########################################################################
.PHONY: clean
clean: ## Clean all symlinks aux reports
clean: clean_sl clean_sl_task

.PHONY: help
help: ## Show this help message and exit
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-16s\033[0m %s\n", $$1, $$2}'
