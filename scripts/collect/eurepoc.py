"""Collection adapter: EuRepoC political cyber incidents.

Supplies the outcome variable this project has never had. Everything else here
measures exposure; this measures whether something actually happened.

Source: European Repository of Cyber Incidents, Global Dataset v1.3.
        Zenodo DOI 10.5281/zenodo.14965395, published 2025-03-04.
        Expert-coded, 60 variables, incidents from 2000 onward.

LICENCE: CC-BY-NC-4.0 -- unlike the CC0 sources, this one is not ours to
redistribute casually. EuRepoC publishes static versioned files precisely so
analyses can be reproduced against a fixed snapshot, so this adapter pins the
version in the URL and the raw download is git-ignored. What the repository
commits is the derived country-level count, which is an aggregate fact rather
than the dataset, distributed with attribution.

WHAT IS COUNTED: incidents whose receiver subcategory is Legislative, Political
parties, or Election infrastructure. Deliberately NOT Government / ministries,
which is far larger (1,586 receiver rows against 327) but is the executive
branch. Our sample is legislators. An underpowered test of the right target
beats a well-powered test of the wrong one.

KNOWN LIMITATION, to be stated wherever these counts are used: EuRepoC codes
PUBLICLY REPORTED incidents. Its measurement error therefore correlates with
HIBP's -- both track media attention, disclosure regimes and analyst focus, and
both over-represent Anglophone and wealthy states. The two biases point the same
way, which is why any model using this outcome must carry the country covariates
that absorb reporting intensity.

FROZEN. Listed in FROZEN_COLLECTORS; never runs in a build.

Usage:  python scripts/collect/eurepoc.py
"""

import os
import sys
from datetime import date

import pandas as pd
import pycountry
import requests

REPO = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
RAW = os.path.join(REPO, "data", "raw", "eurepoc")
OUT = os.path.join(REPO, "data", "eurepoc_political_incidents.csv")

ZENODO_RECORD = "14965395"
VERSION = "1.3"
FILE = f"eurepoc_receiver_dataset_{VERSION}.csv"
URL = f"https://zenodo.org/api/records/{ZENODO_RECORD}/files/{FILE}/content"

# The receiver file carries only target country and category. The incident-level
# file carries the variables that decide whether credential exposure is even the
# right thing to measure: mitre_initial_access (how the intrusion began),
# attribution_type (whether a state actor was named) and weighted_intensity (how
# much damage was done).
GLOBAL_FILE = "eurepoc_global_dataset_1_3.csv"
GLOBAL_URL = f"https://zenodo.org/api/records/{ZENODO_RECORD}/files/{GLOBAL_FILE}/content"
PROFILE_OUT = os.path.join(REPO, "data", "eurepoc_incident_profile.csv")

POLITICAL = [
    "Legislative",
    "Political parties",
    "Election infrastructure / related systems",
]


# pycountry.lookup() matches official names and fails on the common ones. It
# raises LookupError on "Russia" (official: Russian Federation), "Turkey"
# (renamed Türkiye in ISO in 2022) and "Palestine" (Palestine, State of). Left
# unmapped these become zeros in the outcome, which would bias the validation
# toward finding nothing -- so they are aliased explicitly rather than fuzzy
# matched, since fuzzy matching silently guesses and cannot be reviewed.
ALIASES = {
    "russia": "RUS",
    "turkey": "TUR",
    "türkiye": "TUR",
    "palestine": "PSE",
    "kosovo": "XKX",
}

# Genuine non-countries in the receiver field. Excluding these is correct; they
# are listed so the exclusion is deliberate rather than incidental.
NOT_COUNTRIES = {
    "eastern europe", "africa", "global (region)", "middle east (region)",
    "mena region (region)", "unknown", "not available", "europe (region)",
    "asia (region)", "eu (region)",
}


def iso3(name):
    """Map EuRepoC's country label to ISO-3166 alpha-3, or None."""
    key = str(name).strip().lower()
    if key in NOT_COUNTRIES:
        return None
    if key in ALIASES:
        return ALIASES[key]
    try:
        return pycountry.countries.lookup(str(name)).alpha_3
    except LookupError:
        return None


def main():
    os.makedirs(RAW, exist_ok=True)
    path = os.path.join(RAW, FILE)
    if not os.path.exists(path):
        r = requests.get(URL, timeout=120)
        r.raise_for_status()
        with open(path, "wb") as fh:
            fh.write(r.content)
        print(f"  downloaded {FILE} ({len(r.content) / 1e6:.1f} MB)")
    else:
        print(f"  using existing snapshot {FILE}")

    d = pd.read_csv(path, low_memory=False)
    for col in ("incident_id", "country", "category", "subcategory"):
        if col not in d.columns:
            sys.exit(f"expected column {col!r}; got {list(d.columns)}")

    pol = d[d.subcategory.isin(POLITICAL)].drop_duplicates(["incident_id", "country"])
    pol = pol.assign(cc3=pol.country.map(iso3))

    unmapped = pol[pol.cc3.isna()].country.value_counts()
    if len(unmapped):
        print("\n  country labels that did not resolve to ISO-3166 (excluded):")
        for name, n in unmapped.items():
            print(f"    {n:>3}  {name}")

    counts = (
        pol.dropna(subset=["cc3"])
        .groupby("cc3")
        .agg(
            n_incidents=("incident_id", "nunique"),
            n_legislative=("subcategory", lambda s: (s == "Legislative").sum()),
            n_party=("subcategory", lambda s: (s == "Political parties").sum()),
            n_election=("subcategory", lambda s: s.str.startswith("Election").sum()),
        )
        .reset_index()
        .assign(
            source_id="eurepoc",
            dataset_version=VERSION,
            zenodo_record=ZENODO_RECORD,
            retrieved_date=date.today().isoformat(),
        )
        .sort_values("n_incidents", ascending=False)
    )
    counts.to_csv(OUT, index=False)

    print(f"\n  {pol.incident_id.nunique():,} political incidents across "
          f"{counts.cc3.nunique()} countries")
    print(f"  wrote {OUT}")

    # ---- incident-level profile ------------------------------------------
    gpath = os.path.join(RAW, GLOBAL_FILE)
    if not os.path.exists(gpath):
        r = requests.get(GLOBAL_URL, timeout=300)
        r.raise_for_status()
        with open(gpath, "wb") as fh:
            fh.write(r.content)
        print(f"  downloaded {GLOBAL_FILE} ({len(r.content) / 1e6:.1f} MB)")

    g = pd.read_csv(gpath, low_memory=False)
    profile = pd.DataFrame({
        "incident_id": g.get("incident_id", pd.RangeIndex(len(g))),
        "is_political": g.receiver_subcategory.astype(str).apply(
            lambda s: any(p in s for p in POLITICAL)
        ),
        "receiver_country": g.receiver_country,
        "initial_access": g.mitre_initial_access,
        # "Not available" is the modal value at 85%, and almost certainly not
        # missing at random -- better-documented incidents get richer coding.
        # Kept as an explicit level rather than dropped, so any analysis has to
        # confront the coverage rather than quietly condition on it.
        "state_attributed": g.attribution_type.astype(str).str.contains(
            "State", case=False, na=False
        ),
        "weighted_intensity": pd.to_numeric(g.weighted_intensity, errors="coerce"),
        "source_id": "eurepoc",
        "dataset_version": VERSION,
        "retrieved_date": date.today().isoformat(),
    })
    profile.to_csv(PROFILE_OUT, index=False)
    coded = (profile.initial_access != "Not available").mean()
    print(f"  {len(profile):,} incidents profiled; initial access coded for "
          f"{100 * coded:.0f}%")
    print(f"  wrote {PROFILE_OUT}")


if __name__ == "__main__":
    main()
