"""13_check_ms_numbers.py
Check every headline number in ms/ms.tex against the data and tables that produce it.

Prose is not compiled against its sources, so a corrected table and the sentence
citing it drift apart silently. This script closes that loop: each claim below
names the quantity, recomputes it from data/ or reads it out of the emitted
tables/ fragment, and asserts the manuscript says the same thing.

Statuses refer to where a number appears in the manuscript, NOT to whether an
email was found in HIBP:

    in-prose    the value appears in the running text
    in-table    the value appears in an emitted table but not in the text
    in-words    the text states it in words ("nearly one in three") -- the
                paired phrase is checked instead of the digits
    NOT IN MS   the value appears nowhere in the manuscript
    UNTESTABLE  the source fragment is absent, so the check could not run

A claim that cannot be recomputed is reported UNTESTABLE rather than passed.

Exit status is 1 if any claim is NOT IN MS or the prose quotes a superseded
value, so it can gate a build.

Usage: python 13_check_ms_numbers.py [--verbose]
"""

import ast
import os
import re
import sys

import pandas as pd

_HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(_HERE, ".."))
DATA = os.path.join(REPO, "data")
TABLES = os.path.join(REPO, "tables")
MS = os.path.join(REPO, "ms", "ms.tex")

# private_blacklight's introduction had been pasted into this manuscript at
# lines 205-225, carrying numbers from a different paper (6.2 million visits,
# 64,074 domains, 1,134 panelists) plus 23 citations and two \ref targets that
# resolve only in that paper. It has been deleted. Guard against it coming back
# on a merge rather than excluding a line range, which goes stale the moment
# anything above it changes.
FOREIGN_MARKERS = ("Blacklight", "Tracker Radar", "canvas fingerprinting",
                   "64,074", "1,134 adults")


# --------------------------------------------------------------- helpers
def load_emails():
    """The analysis file, deduped exactly as 11_breach_prob.R does."""
    df = pd.read_csv(os.path.join(DATA, "email_lvl_cov.csv"))
    df = df.sort_values("source", key=lambda s: (s != "ep")).drop_duplicates("email")
    return df


def check_no_foreign_text():
    """Fail loudly if private_blacklight's prose reappears in this manuscript."""
    txt = open(MS).read()
    return [m for m in FOREIGN_MARKERS if m in txt]


def ms_prose():
    """ms.tex body with tables and figures removed."""
    with open(MS) as fh:
        lines = fh.readlines()
    keep, depth = [], 0
    for ln in lines:
        if re.search(r"\\begin\{(table|figure|tabular|adjustbox)", ln):
            depth += 1
        if depth == 0 and not ln.lstrip().startswith("%"):
            keep.append(ln)
        if re.search(r"\\end\{(table|figure|tabular|adjustbox)", ln):
            depth = max(0, depth - 1)
    return "".join(keep)


def frag_cell(fragment, row, col):
    """Read one cell out of a pipeline .tex fragment (0-indexed, & separated)."""
    path = os.path.join(TABLES, fragment)
    if not os.path.exists(path):
        return None
    rows = [
        r for r in open(path).read().split("\n") if r.strip() and "&" in r
    ]
    if row >= len(rows):
        return None
    cells = [c.strip() for c in rows[row].replace(r"\\", "").split("&")]
    return cells[col] if col < len(cells) else None


def says(prose, value):
    """Does the prose contain this exact numeric token, not embedded in a longer one?"""
    return re.search(r"(?<![\d.,])" + re.escape(str(value)) + r"(?![\d,])", prose) is not None


def stale_near_miss(prose, value):
    """Find a prose number that looks like a superseded version of `value`.

    A table match must not excuse a contradicting prose value. When the analysis
    file gained one address, the regenerated table read 12,385 while the prose
    still read 12,384; the value was found in a table and the check passed,
    which is precisely the drift this script exists to catch. So when the exact
    value is absent from the prose, look for a number close enough to be the
    stale version of it and report that instead of quietly falling back.
    """
    try:
        target = float(str(value).replace(",", "").rstrip("%"))
    except ValueError:
        return None
    if target == 0:
        return None
    for tok in re.findall(r"(?<![\d.,])\d[\d,]*\.?\d*", prose):
        try:
            got = float(tok.replace(",", ""))
        except ValueError:
            continue
        if got == target:
            return None
        # same order of magnitude and within 1% -- a rounding or off-by-N drift,
        # not an unrelated number that happens to be nearby
        if abs(got - target) / target <= 0.01 and len(tok.replace(",", "")) == len(
            str(value).replace(",", "").rstrip("%")
        ):
            return tok
    return None


def all_table_text():
    """Emitted fragments plus the whole manuscript.

    ms_prose() strips table and figure environments, so a value stated only in
    a caption (n = 679 in the fixed-cohort figure) is absent from prose but very
    much present in the paper. This is the 'stated somewhere, just not in the
    running text' fallback.
    """
    out = [open(MS).read()]
    for fn in sorted(os.listdir(TABLES)):
        if fn.endswith(".tex"):
            out.append(open(os.path.join(TABLES, fn)).read())
    return "\n".join(out)


# Quantities the manuscript states in words rather than digits. Each is paired
# with the phrase that carries it, so a reader can confirm the phrase still
# matches the number -- and so the check does not report a false miss.
PHRASED_IN_WORDS = {
    "HIBP breaches in catalogue": "more than 850 public breaches",
    "share breached (%)": "Nearly one in three",
    # 71.4% after the case-sensitivity fix in 10_breach_rate_evolution; the
    # footnote to fig:breach_rate_evolution says "close to 70\%", which the
    # corrected value still satisfies (it did so from below at 66.9%).
    "pre-2007 cohort rate (%)": r"close to 70\%",
}


# --------------------------------------------------------------- claims
def build_claims():
    df = load_emails()
    n = len(df)
    breached = (df.nbreach > 0)
    serious = (df.nbreach_serious > 0)
    off = df.ecategory == "Official"
    com = df.ecategory == "Commercial"
    breaches = pd.read_csv(os.path.join(DATA, "breaches_01_2025.csv"))

    ep = pd.read_csv(
        os.path.join(DATA, "everypol", "everypol_combined_legislature_data.csv"),
        low_memory=False,
    )

    C = []

    def claim(name, computed, fmt=None, note=""):
        shown = fmt(computed) if fmt else computed
        C.append((name, shown, note))

    # -- sample construction
    claim("unique analysis emails", f"{n:,}")
    claim("countries in analysis sample", df.cc3.nunique())
    claim("EveryPolitician unique emails", f"{ep.email.nunique():,}")
    claim("HIBP breaches in catalogue", len(breaches))
    # literal_eval, not eval: DataClasses is a stringified list read off a CSV,
    # and 09_breach_summ.ipynb uses bare eval() on the same field.
    claim("HIBP data classes", len({d for s in breaches.DataClasses
                                    for d in ast.literal_eval(s)}))

    # -- headline prevalence
    claim("share breached (%)", f"{100*breached.mean():.1f}")
    claim("share serious (%)", f"{100*serious.mean():.1f}")
    claim("share breached >=2 (%)", f"{100*(df.nbreach>1).mean():.1f}")
    claim("share serious >=2 (%)", f"{100*(df.nbreach_serious>1).mean():.1f}")

    # -- official vs personal
    claim("official emails n", f"{off.sum():,}")
    claim("personal emails n", f"{com.sum():,}")
    claim("official breached (%)", f"{100*breached[off].mean():.1f}")
    claim("personal breached (%)", f"{100*breached[com].mean():.1f}")
    claim("official serious (%)", f"{100*serious[off].mean():.1f}")
    claim("personal serious (%)", f"{100*serious[com].mean():.1f}")

    # -- values that must agree between table fragment and prose
    claim("mean breaches, official (fragment)", frag_cell(
        "pooled_pols_breach_number_summary.tex", 1, 2), note="from fragment")
    claim("mean breaches, personal (fragment)", frag_cell(
        "pooled_pols_breach_number_summary.tex", 2, 2), note="from fragment")

    # -- 10_breach_rate_evolution: the two numbers that exist only inside a
    # figure, so nothing could check them until now. Recomputed here from the
    # same inputs the notebook uses.
    for name, value in breach_rate_evolution_stats().items():
        claim(name, value)

    return C


def breach_rate_evolution_stats():
    """Recompute the evolution series endpoints independently of the notebook.

    The notebook renders these into figures/breach_rate_evolution*.pdf and
    nowhere else, so they were unverifiable. Recomputing them here means the
    figure and the prose are checked against the same source.

    The join key must be lowercased: 382 HIBP filenames preserve scraped
    capitalisation (Mark.Coulton.MP@aph.gov.au) while email_lvl_cov.csv is
    lowercased, and joining raw silently scores 380 addresses -- mostly CAN,
    AUS and GBR -- as never breached.
    """
    hibp = pd.concat(
        [
            pd.read_csv(os.path.join(DATA, "everypol_hibp.csv")),
            pd.read_csv(os.path.join(DATA, "scraped_pol_hibp.csv")),
        ],
        ignore_index=True,
    )
    hibp = hibp[hibp.Present]
    cat = pd.read_csv(
        os.path.join(DATA, "breaches_01_2025.csv"), usecols=["Name", "BreachDate"]
    )
    hibp = hibp.merge(cat, left_on="Breach", right_on="Name", how="left")
    first = (
        hibp.assign(k=hibp.Filename.str.lower()).groupby("k")["BreachDate"].min()
    )

    df = pd.read_csv(
        os.path.join(DATA, "email_lvl_cov.csv"),
        usecols=["email", "cc3", "leg_start_date", "leg_start_year"],
    )
    # Singapore legislature start dates are absent upstream; the notebook
    # patches them from leg_start_year.
    sgp = {2021: "2020-08-24", 2016: "2016-01-15", 2011: "2011-10-10",
           2006: "2006-11-02", 2001: "2002-03-25"}
    df["leg_start_date"] = pd.Series(
        pd.NA, index=df.index
    ).where(df.cc3 != "SGP", df.leg_start_year.map(sgp)).fillna(df.leg_start_date)
    # Rows with no datable start cannot be placed on the timeline at all. 3,644
    # of the 3,715 dropped enter in 2025, after the series ends, so this costs
    # 0.07pp at the endpoint and nothing in the fixed cohort.
    df = df.dropna(subset=["leg_start_date"])
    df["leg_start_date"] = pd.to_datetime(df["leg_start_date"])

    end = pd.Timestamp("2025-02-01")
    breached = df.email.str.lower().map(first)
    hit = breached.notna() & (pd.to_datetime(breached) < end)

    cohort = df.leg_start_date < pd.Timestamp("2007-01-01")
    return {
        "evolution denominator": f"{len(df):,}",
        "evolution endpoint (%)": f"{100 * hit.mean():.1f}",
        "pre-2007 cohort n": f"{cohort.sum():,}",
        "pre-2007 cohort rate (%)": f"{100 * hit[cohort].mean():.1f}",
    }


# Values the published table once carried that a later rerun changed. If prose
# still quotes the superseded value, the sentence is stale -- which is the
# failure mode this whole script exists to catch. fixest >= 0.12 drops singleton
# fixed-effect groups, moving the EP-subsample models from 7,188 obs / 465
# parties / 54 countries to 7,082 / 359 / 53.
SUPERSEDED = {
    "7,188": "7,082 (fixest now drops 106 singleton parties)",
    "465": "359 (singleton parties dropped)",
}


def check_regtab(prose, results):
    """Flag prose that contradicts the LPM table, not prose that merely omits it.

    A regression table carrying its own N is normal and needs no echo in the
    text, so absence is not a defect. Quoting a superseded value is.
    """
    path = os.path.join(TABLES, "breach_prob.tex")
    if not os.path.exists(path):
        results.append(("regtab", "UNTESTABLE", "tables/breach_prob.tex absent"))
        return
    for stale, replacement in SUPERSEDED.items():
        if says(prose, stale):
            results.append(
                (f"stale value {stale!r} in prose", stale, f"should be {replacement}")
            )


def main():
    verbose = "--verbose" in sys.argv
    prose = ms_prose()
    claims = build_claims()

    tables_txt = all_table_text()
    print(f"Checking {len(claims)} quantities against ms/ms.tex\n")
    fails = []

    foreign = check_no_foreign_text()
    if foreign:
        print("  FOREIGN     private_blacklight prose is back in ms.tex: "
              f"{', '.join(foreign)}")
        fails.append(("foreign text in ms.tex", ", ".join(foreign)))
    for name, value, note in claims:
        if value is None:
            print(f"  UNTESTABLE  {name:<34} (source fragment missing)")
            continue
        if name in PHRASED_IN_WORDS:
            phrase = PHRASED_IN_WORDS[name]
            if phrase in prose:
                if verbose:
                    print(f"  in-words    {name:<34} = {value}  (\"{phrase}\")")
            else:
                print(f"  NOT IN MS   {name:<34} = {value}  "
                      f"(expected phrase \"{phrase}\" is gone)")
                fails.append((name, value))
            continue
        if says(prose, value):
            if verbose:
                print(f"  in-prose    {name:<34} = {value}  {note}")
            continue
        stale = stale_near_miss(prose, value)
        if stale is not None:
            print(f"  STALE       {name:<34} = {value}  "
                  f"(prose still says {stale})")
            fails.append((name, value))
        elif says(tables_txt, value):
            if verbose:
                print(f"  in-table    {name:<34} = {value}")
        else:
            print(f"  NOT IN MS   {name:<34} = {value}  {note}")
            fails.append((name, value))

    extra = []
    check_regtab(prose, extra)
    if extra:
        print()
        for name, value, status in extra:
            if status != "ok":
                print(f"  STALE       {name:<34} = {value}  ({status})")
                fails.append((name, value))

    print()
    if fails:
        print(f"{len(fails)} value(s) computed here do not appear in the manuscript prose.")
        print("Either the prose is stale, or the quantity is phrased differently")
        print("(e.g. 'nearly one in three' for 33.0). Check each before dismissing.")
        return 1
    print("All checked quantities appear in the manuscript.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
