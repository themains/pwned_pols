"""14_check_notebook_hygiene.py
Fail the build when a pipeline notebook's stored outputs cannot be trusted.

The analysis stages here are notebooks, which means they can carry state a
script cannot: a cell can error while later cells hold outputs from an earlier
kernel, and cells can be executed out of order. That is not hypothetical.
10_breach_rate_evolution.ipynb shipped with a `ValueError` stored at
execution_count 2 while every cell after it held full outputs at counts 3, 4,
5..., with an execution order ending 29, 47, 39, 40, 41, 43. Every number in it,
including the fixed-cohort rate the abstract's "more than half" rests on, came
from a kernel holding a different version of the input file. Nothing failed,
because nothing was checking.

Three assertions, each a direct signature of that failure:

    errors      no code cell stores an output_type == "error"
    order       execution_count is strictly increasing across executed cells
    executed    no cell holds outputs with execution_count == null

Run after `jupyter nbconvert --execute`, which always starts a fresh kernel and
runs top to bottom -- a notebook that passes these three immediately after a
headless execute is as trustworthy as a script.

Usage: python 14_check_notebook_hygiene.py [notebook ...]
       (defaults to every numbered notebook except the network-acquisition ones)
"""

import glob
import json
import os
import re
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))

# Exempt only the notebooks that acquire data over the network. They cannot be
# re-executed on demand -- 04 alone is ~12,900 HIBP calls at 7-10s each -- and
# their results would not reproduce if they were, because the upstream service
# has moved on. They are frozen inputs, so demanding clean execution state from
# them would be a gate nobody can satisfy.
#
# Everything else is local-file processing and must re-run cleanly, including
# 03 and 05, which only read files on disk despite sitting below the acquisition
# stages numerically. Verified by grepping for requests.get/post,
# EveryPolitician(), dns.resolver and webdriver: hits in 01/02/04/06, none in
# 03/05/07/09/10.
#
# 99_ is an archived one-off. Pass paths explicitly to check anything else.
PIPELINE = re.compile(r"^\d{2}_.*\.ipynb$")
SKIP_PREFIXES = ("99_",)
NETWORK_ACQUISITION = {
    "01_everypol_walkthrough.ipynb",                        # EveryPolitician API
    "02_everypol_download_csvs.ipynb",                      # requests.get per term
    "04_download_hibp_everypol_india_eur_breaches.ipynb",   # HIBP API
    "06_validate_email_domains.ipynb",                      # DNS MX lookups
}


def is_checked(path):
    name = os.path.basename(path)
    if not PIPELINE.match(name) or name.startswith(SKIP_PREFIXES):
        return False
    return name not in NETWORK_ACQUISITION


def code_cells(nb):
    return [c for c in nb.get("cells", []) if c.get("cell_type") == "code"]


def check(path):
    """Return a list of problem strings for one notebook."""
    with open(path) as fh:
        nb = json.load(fh)
    problems = []
    cells = code_cells(nb)

    for i, c in enumerate(cells):
        for out in c.get("outputs", []):
            if out.get("output_type") == "error":
                ename = out.get("ename", "?")
                evalue = " ".join(str(out.get("evalue", "")).split())[:90]
                problems.append(
                    f"cell {i} (execution_count={c.get('execution_count')}) "
                    f"stores {ename}: {evalue}"
                )

    counts = [(i, c.get("execution_count")) for i, c in enumerate(cells)]
    executed = [(i, n) for i, n in counts if n is not None]
    for (i_prev, n_prev), (i_cur, n_cur) in zip(executed, executed[1:]):
        if n_cur <= n_prev:
            problems.append(
                f"cell {i_cur} ran at {n_cur} after cell {i_prev} ran at "
                f"{n_prev} -- out of order, so later cells may hold stale state"
            )
            break  # one report per notebook is enough; the rest cascade

    for i, c in enumerate(cells):
        if c.get("execution_count") is None and c.get("outputs"):
            problems.append(
                f"cell {i} holds outputs but was never executed in this session"
            )

    return problems


def main():
    targets = sys.argv[1:]
    if not targets:
        targets = sorted(
            p for p in glob.glob(os.path.join(_HERE, "*.ipynb")) if is_checked(p)
        )
    if not targets:
        print("no pipeline notebooks found")
        return 1

    bad = 0
    for path in targets:
        name = os.path.basename(path)
        problems = check(path)
        if problems:
            bad += 1
            print(f"  FAIL  {name}")
            for p in problems:
                print(f"          {p}")
        else:
            print(f"  ok    {name}")

    print()
    if bad:
        print(
            f"{bad} notebook(s) carry untrustworthy stored output.\n"
            "Re-run with: jupyter nbconvert --to notebook --execute --inplace <nb>"
        )
        return 1
    print(f"{len(targets)} notebook(s) clean.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
