"""24_check_classifier.py -- guard the email classifier against the two ways it
has actually gone wrong in this repository.

The Official/Commercial split is the paper's key explanatory variable, and it is
produced by a hand-maintained regex list duplicated across two languages. That
arrangement has failed twice here, both times silently:

  * 1bbc95f -- the verification script and the pipeline drifted onto different
    address normalisations. They agreed with each other and both were wrong, so
    every gate passed.
  * The US patterns added alongside this file were nearly written as loose token
    matches. A bare "house" rule classifies arkansashouse.org correctly and
    werahobhouse.co.uk incorrectly -- the personal domain of a sitting UK MP
    whose surname is Hobhouse.

So two assertions, both of which must be able to fail:

  1. The classifier is a NO-OP on the frozen analysis sample. Extending the
     pattern list for new data must never silently reclassify a published
     address. If it does, published numbers have moved and the build stops.

  2. Python and R agree exactly. utilities.R is a port of utilities.py; a port
     that has drifted is worse than no port, because both halves keep running.

Run: python scripts/24_check_classifier.py
"""

import os
import subprocess
import sys
import tempfile

import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, ".."))
sys.path.insert(0, HERE)

from utilities import classify_comm_gov_email  # noqa: E402

FROZEN = os.path.join(REPO, "data", "email_lvl_cov.csv")
CORPUS = os.path.join(REPO, "data", "politician_emails.csv")


def check_frozen_unchanged():
    """The published sample's classification must be untouched."""
    df = pd.read_csv(FROZEN).drop_duplicates("email")[["email", "ecategory"]]
    got = classify_comm_gov_email(df[["email"]].copy()).reset_index(drop=True)
    want = df.reset_index(drop=True)
    diff = want.ecategory != got.ecategory
    if diff.any():
        print(f"  FAIL: {int(diff.sum())} published addresses would be reclassified:")
        for _, r in want[diff.values].head(10).iterrows():
            print(f"    {r.email}  was {r.ecategory}")
        return False
    print(f"  ok: classification unchanged for all {len(want):,} published addresses")
    return True


def check_python_r_parity():
    """utilities.R must classify identically to utilities.py."""
    frames = [pd.read_csv(FROZEN, usecols=["email"])]
    if os.path.exists(CORPUS):
        frames.append(pd.read_csv(CORPUS, usecols=["email"]))
    emails = pd.concat(frames, ignore_index=True).drop_duplicates("email")

    py = classify_comm_gov_email(emails.copy()).reset_index(drop=True)
    with tempfile.TemporaryDirectory() as tmp:
        src = os.path.join(tmp, "emails.csv")
        dst = os.path.join(tmp, "r_class.csv")
        py[["email"]].to_csv(src, index=False)
        script = f"""
suppressPackageStartupMessages({{
  library(dplyr); library(readr); library(stringr); library(tidyr)
}})
source("{os.path.join(HERE, 'utilities.R')}")
d <- read_csv("{src}", show_col_types = FALSE)
write_csv(classify_comm_gov_email(d), "{dst}")
"""
        proc = subprocess.run(
            ["Rscript", "-e", script], capture_output=True, text=True, cwd=HERE
        )
        if proc.returncode != 0:
            print("  SKIP: Rscript unavailable or failed:")
            print("   ", proc.stderr.strip().splitlines()[-1] if proc.stderr else "")
            return True
        r = pd.read_csv(dst)

    diff = py.ecategory.values != r.ecategory.values
    if diff.any():
        print(f"  FAIL: Python and R disagree on {int(diff.sum())} of {len(py):,} addresses:")
        for e, a, b in zip(py.email[diff], py.ecategory[diff], r.ecategory[diff]):
            print(f"    {e}: python={a} r={b}")
        return False
    print(f"  ok: Python and R agree on all {len(py):,} addresses")
    return True


def main():
    print("==> classifier checks")
    ok = all([check_frozen_unchanged(), check_python_r_parity()])
    if not ok:
        sys.exit(1)


if __name__ == "__main__":
    main()
