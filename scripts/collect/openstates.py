"""Collection adapter: Open States people (US state legislators).

Adds the United States to a sample that currently excludes it entirely. That is
the point of this source, more than its size: both population benchmarks the
manuscript compares against -- the YouGov survey and the Florida voter file --
are US samples, while EveryPolitician holds zero US addresses. The comparison is
therefore confounded by national coverage of breach corpora in a direction we
cannot sign. This closes it.

Source: https://data.openstates.org/people/current/{abbr}.csv
        Nightly bulk CSVs, one per jurisdiction, CC0, no API key.
        Columns include `email` and, usefully, `wikidata` -- so these rows
        arrive already keyed to the same person identifier 19_person_key.R uses
        for EveryPolitician.

FROZEN. Listed in FROZEN_COLLECTORS in the Makefile; never runs in a build.
Running it is a deliberate act, followed by `make manifest`.

Usage:  python scripts/collect/openstates.py
"""

import os
import sys
import time
from datetime import date

import pandas as pd
import requests

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from utilities import clean_email_column_no_dedupe, classify_comm_gov_email  # noqa: E402

REPO = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
RAW = os.path.join(REPO, "data", "raw", "openstates")
OUT = os.path.join(REPO, "data", "politician_emails.csv")
BASE = "https://data.openstates.org/people/current/{}.csv"

# 50 states, DC and Puerto Rico. Open States also publishes territories; they
# are excluded because they do not send voting members to a state legislature
# in the sense the rest of the sample uses.
JURISDICTIONS = """
al ak az ar ca co ct de fl ga hi id il in ia ks ky la me md ma mi mn ms mo
mt ne nv nh nj nm ny nc nd oh ok or pa ri sc sd tn tx ut vt va wa wv wi wy
dc pr
""".split()

CANONICAL = [
    "source_id", "person_id", "wikidata", "name", "cc3", "level", "chamber",
    "term_start", "email", "email_raw", "ecategory", "retrieved_date",
    "source_url",
]


def fetch(abbr):
    """Fetch one jurisdiction and snapshot it before anything parses it.

    The snapshot is written first and never touched again. A parser bug then
    costs a rerun of this file rather than a refetch, and the provenance of any
    row stays checkable against exactly what the source served.
    """
    os.makedirs(RAW, exist_ok=True)
    path = os.path.join(RAW, f"{abbr}.csv")
    url = BASE.format(abbr)
    if os.path.exists(path):
        return path, url
    r = requests.get(url, timeout=60)
    r.raise_for_status()
    with open(path, "wb") as fh:
        fh.write(r.content)
    time.sleep(0.5)
    return path, url


def main():
    today = date.today().isoformat()
    frames, missing = [], []

    for abbr in JURISDICTIONS:
        try:
            path, url = fetch(abbr)
        except requests.HTTPError as exc:
            missing.append(f"{abbr}: {exc}")
            continue

        df = pd.read_csv(path)
        for col in ("id", "name", "email"):
            if col not in df.columns:
                sys.exit(f"{abbr}: expected column {col!r}; got {list(df.columns)}")

        df = df[df.email.notna()].copy()
        if df.empty:
            continue
        df["email_raw"] = df.email

        # The pipeline's own normaliser, not a local one. Re-deriving this rule
        # is what put the verification script and the pipeline on different
        # definitions in 1bbc95f, where they agreed with each other and both
        # were wrong.
        df = clean_email_column_no_dedupe(df, column_name="email")
        if df.empty:
            continue
        df = classify_comm_gov_email(df, email_col="email")

        frames.append(
            pd.DataFrame({
                "source_id": "openstates",
                "person_id": df.id,
                "wikidata": df.get("wikidata", pd.Series(index=df.index, dtype=object)),
                "name": df.name if "name" in df else pd.NA,
                "cc3": "USA",
                "level": "state",
                "chamber": df.get("current_chamber", pd.Series(index=df.index, dtype=object)),
                "term_start": pd.NA,
                "email": df.email,
                "email_raw": df.email_raw,
                "ecategory": df.ecategory,
                "retrieved_date": today,
                "source_url": url,
            })
        )
        print(f"  {abbr}: {len(df):>4} addresses")

    if missing:
        print("\njurisdictions that failed to fetch:")
        for m in missing:
            print("   ", m)

    out = pd.concat(frames, ignore_index=True)[CANONICAL]
    # Append if the canonical table already holds other sources, replacing any
    # previous run of THIS source so reruns are idempotent.
    if os.path.exists(OUT):
        prior = pd.read_csv(OUT)
        out = pd.concat([prior[prior.source_id != "openstates"], out], ignore_index=True)
    out.to_csv(OUT, index=False)

    added = (out.source_id == "openstates").sum()
    personal = ((out.source_id == "openstates") & (out.ecategory == "Commercial")).sum()
    print(f"\nopenstates: {added:,} addresses, {personal:,} personal "
          f"({100 * personal / added:.1f}%), {out.wikidata.notna().sum():,} with a QID")
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
