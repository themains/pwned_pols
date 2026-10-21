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
import json
import os
import re
import sys

import pandas as pd

_HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(_HERE, ".."))
DATA = os.path.join(REPO, "data")
TABLES = os.path.join(REPO, "tables")
ANALYSIS = os.path.join(REPO, "analysis")
MS = os.path.join(REPO, "ms", "ms.tex")

# private_blacklight's introduction had been pasted into this manuscript at
# lines 205-225, carrying numbers from a different paper (6.2 million visits,
# 64,074 domains, 1,134 panelists) plus 23 citations and two \ref targets that
# resolve only in that paper. It has been deleted. Guard against it coming back
# on a merge rather than excluding a line range, which goes stale the moment
# anything above it changes.
FOREIGN_MARKERS = (
    "Blacklight",
    "Tracker Radar",
    "canvas fingerprinting",
    "64,074",
    "1,134 adults",
)

UNSUPPORTED_CLAIMS = (
    "north of 50\\%",
    "more than 50\\%",
    "true rate of serious",
)


# --------------------------------------------------------------- helpers
def read_text(path):
    with open(path, encoding="utf-8") as file:
        return file.read()


def load_emails():
    """The analysis file, deduped exactly as 11_breach_prob.R does."""
    df = pd.read_csv(os.path.join(DATA, "email_lvl_cov.csv"))
    df = df.sort_values("source", key=lambda s: s != "ep").drop_duplicates("email")
    return df


def check_no_foreign_text():
    """Fail loudly if private_blacklight's prose reappears in this manuscript."""
    txt = read_text(MS)
    return [m for m in FOREIGN_MARKERS if m in txt]


def check_unsupported_claims():
    """Keep the manuscript from reintroducing non-identified population claims."""
    txt = read_text(MS)
    return [m for m in UNSUPPORTED_CLAIMS if m in txt]


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
    rows = [r for r in read_text(path).split("\n") if r.strip() and "&" in r]
    if row >= len(rows):
        return None
    cells = [c.strip() for c in rows[row].replace(r"\\", "").split("&")]
    return cells[col] if col < len(cells) else None


def says(prose, value):
    """Does the prose contain this exact numeric token, not embedded in a longer one?"""
    return (
        re.search(r"(?<![\d.,])" + re.escape(str(value)) + r"(?![\d,])", prose)
        is not None
    )


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
    out = [read_text(MS)]
    for fn in sorted(os.listdir(TABLES)):
        if fn.endswith(".tex"):
            out.append(read_text(os.path.join(TABLES, fn)))
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
    breached = df.nbreach > 0
    serious = df.nbreach_serious > 0
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
    claim(
        "HIBP data classes",
        len({d for s in breaches.DataClasses for d in ast.literal_eval(s)}),
    )

    # -- headline prevalence
    claim("share breached (%)", f"{100 * breached.mean():.1f}")
    claim("share serious (%)", f"{100 * serious.mean():.1f}")
    claim("share breached >=2 (%)", f"{100 * (df.nbreach > 1).mean():.1f}")
    claim("share serious >=2 (%)", f"{100 * (df.nbreach_serious > 1).mean():.1f}")

    # -- official vs personal
    claim("official emails n", f"{off.sum():,}")
    claim("personal emails n", f"{com.sum():,}")
    claim("official breached (%)", f"{100 * breached[off].mean():.1f}")
    claim("personal breached (%)", f"{100 * breached[com].mean():.1f}")
    claim("official serious (%)", f"{100 * serious[off].mean():.1f}")
    claim("personal serious (%)", f"{100 * serious[com].mean():.1f}")

    # -- values that must agree between table fragment and prose
    claim(
        "mean breaches, official (fragment)",
        frag_cell("pooled_pols_breach_number_summary.tex", 1, 2),
        note="from fragment",
    )
    claim(
        "mean breaches, personal (fragment)",
        frag_cell("pooled_pols_breach_number_summary.tex", 2, 2),
        note="from fragment",
    )

    # -- 10_breach_rate_evolution: the two numbers that exist only inside a
    # figure, so nothing could check them until now. Recomputed here from the
    # same inputs the notebook uses.
    for name, value in breach_rate_evolution_stats().items():
        claim(name, value)

    # -- SI: breach provenance, population benchmark, stealer logs
    for name, value in si_stats().items():
        claim(name, value)

    # -- person-key coverage, cited where the manuscript explains why a
    # within-politician comparison is not identified
    for name, value in person_key_stats().items():
        claim(name, value)

    # -- sensitivity bound on the hand-coded taxonomy rows
    for name, value in sensitivity_stats().items():
        claim(name, value)

    return C


def sensitivity_stats():
    """Bound on how far the hand-coded taxonomy rows move any provenance share.

    Read from the fragment 20_sensitivity.R writes rather than recomputed. The
    ordering that the provenance argument depends on -- broker aggregation above
    service compromise -- is enforced there, in the stage that owns the
    classification, so that a build cannot produce a manuscript whose central
    claim its own tables contradict. Duplicating that check here would put the
    enforcement in two places and let them disagree.
    """
    path = os.path.join(TABLES, "sensitivity_taxonomy_body.tex")
    if not os.path.exists(path):
        return {"taxonomy sensitivity": "UNTESTABLE -- run scripts/20_sensitivity.R"}

    rows = [r for r in read_text(path).splitlines() if r.strip().endswith(r"\\")]
    pct = re.compile(r"([0-9]+\.[0-9]+)\\%")
    shares = [[float(x) for x in pct.findall(r)] for r in rows]
    shares = [s for s in shares if len(s) == 3]
    if not shares:
        return {"taxonomy sensitivity": "UNTESTABLE -- fragment has no share rows"}

    published = shares[0]
    shift = max(abs(v - published[i]) for s in shares for i, v in enumerate(s))
    return {"max provenance share shift (pp)": f"{shift:.2f}"}


def person_key_stats():
    """Recompute the person-key coverage cited in the robustness discussion.

    EveryPolitician's `id` keys a person WITHIN a legislature, not a person: 68
    records share a Wikidata QID because the same individual served in two
    legislatures (Alex Salmond in Holyrood and Westminster; Doris Jakobsen in
    Greenland and Denmark). The QID is the identifier that resolves to the
    human, so the pairing counts are computed against it.
    """
    ep = pd.read_csv(
        os.path.join(DATA, "everypol", "everypol_combined_legislature_data.csv"),
        low_memory=False,
    )
    qid = ep[ep.wikidata.notna()]
    shared = qid.groupby("wikidata").id.nunique()

    withmail = ep[ep.email.notna() & ep.wikidata.notna()].copy()
    withmail["email"] = withmail.email.str.lower().str.strip()
    per_person = withmail.groupby("wikidata").email.nunique()

    return {
        "person-legislature records": f"{ep.id.nunique():,}",
        "distinct people (Wikidata QID)": f"{qid.wikidata.nunique():,}",
        "records sharing a QID": f"{shared[shared > 1].sum():,}",
        "people with an address (by QID)": f"{len(per_person):,}",
    }


def _politician_hits():
    """One row per (address, breach), joined to the taxonomy.

    email_lvl_cov.csv is NOT keyed on email -- 12,916 rows for 12,385 distinct
    addresses, because an address found in both sources is stored once per
    source. Every rate below is therefore computed against distinct addresses;
    using the row count understates them by ~4%. 4,090/12,385 = 33.0% is the
    published headline, which is the check that this is the right denominator.
    """
    tax_path = os.path.join(ANALYSIS, "breach_taxonomy.csv")
    if not os.path.exists(tax_path):
        return None, None
    tax = pd.read_csv(tax_path)

    # Normalise with the SAME helper the pipeline uses, not with .str.lower().
    # utilities.py is the original; utilities.R is a port of it. Lowercasing
    # alone matches two fewer addresses, because the helper also trims,
    # normalises unicode and strips a leading "1."/"2.". Re-implementing it here
    # is how the checker and the pipeline drift apart while both keep passing --
    # which is exactly what happened before this line was fixed.
    from utilities import clean_email_column_no_dedupe

    hibp = pd.concat(
        [
            pd.read_csv(os.path.join(DATA, "everypol_hibp.csv")),
            pd.read_csv(os.path.join(DATA, "scraped_pol_hibp.csv")),
        ],
        ignore_index=True,
    )
    hibp = hibp[hibp.Present]
    hibp = clean_email_column_no_dedupe(
        hibp.rename(columns={"Filename": "email"}), column_name="email"
    )

    cov = pd.read_csv(os.path.join(DATA, "email_lvl_cov.csv"))
    addr = cov.groupby("email").agg(
        ecategory=("ecategory", "first"), leg_start_year=("leg_start_year", "min")
    )

    hits = (
        hibp[hibp.email.isin(addr.index)][["email", "Breach"]]
        .drop_duplicates()
        .merge(tax, left_on="Breach", right_on="name", how="left")
    )
    assert not hits.tax_class.isna().any(), "unclassified breach in politician hits"
    return hits, addr


def si_stats():
    """Recompute the SI numbers from the frozen inputs.

    The taxonomy ASSIGNMENT is read from analysis/breach_taxonomy.csv rather
    than re-derived, so there is exactly one place where a breach's class is
    decided. What is recomputed here is the arithmetic on top of it, which is
    what drifts.
    """
    hits, addr = _politician_hits()
    if hits is None:
        return {"SI stats": "UNTESTABLE -- run scripts/17_breach_taxonomy.R"}

    n = len(addr)
    pct = lambda emails: f"{100 * len(set(emails)) / n:.1f}"

    out = {
        "SI service-compromise share (%)": pct(
            hits.email[hits.tax_class == "service"]
        ),
        "SI aggregator share (%)": pct(hits.email[hits.tax_class == "aggregator"]),
        "SI combolist share (%)": pct(hits.email[hits.tax_class == "combolist"]),
    }

    stealer = set(hits.email[hits.is_stealer])
    out["SI stealer addresses (n)"] = f"{len(stealer):,}"
    out["SI stealer share (%)"] = f"{100 * len(stealer) / n:.2f}"
    # Repeat appearance across corpora: the SI argues this is hard to explain
    # as incidental inclusion, so the count is gated rather than asserted.
    per_addr = hits[hits.is_stealer].groupby("email").Breach.nunique()
    out["SI stealer, multiple corpora (n)"] = f"{(per_addr > 1).sum():,}"
    personal = addr.index[addr.ecategory == "Commercial"]
    official = addr.index[addr.ecategory != "Commercial"]
    out["SI stealer, personal (%)"] = (
        f"{100 * len(stealer & set(personal)) / len(personal):.2f}"
    )
    out["SI stealer, official (%)"] = (
        f"{100 * len(stealer & set(official)) / len(official):.2f}"
    )

    # -- population benchmark, restricted to the shared catalogue and window
    yg_cat_path = os.path.join(DATA, "benchmark", "yougov_breaches.json")
    yg_hits_path = os.path.join(DATA, "benchmark", "YGOV1058_pwned.csv")
    yg_prof_path = os.path.join(DATA, "benchmark", "YGOV1058_profile.csv")
    if not all(map(os.path.exists, (yg_cat_path, yg_hits_path, yg_prof_path))):
        return out

    with open(yg_cat_path) as fh:
        common = {b["Name"] for b in json.load(fh)}
    cat = pd.read_csv(os.path.join(DATA, "breaches_01_2025.csv"), usecols=["Name"])
    assert common <= set(cat.Name), "YouGov catalogue is not nested in ours"

    era = addr.index[addr.leg_start_year <= 2018]
    in_common = hits[hits.Breach.isin(common)]
    # Catalogue-restricted but NOT era-matched: cited in the SI to show how
    # much of the gap era matching closes (15.2 -> 17.5), so it is gated too.
    out["SI catalogue-only politicians breached (%)"] = (
        f"{100 * in_common.email.nunique() / n:.1f}"
    )
    out["SI era-matched politicians service (%)"] = (
        f"{100 * len(set(in_common.email[in_common.tax_class == 'service']) & set(era)) / len(era):.1f}"
    )
    out["SI era-matched politicians (n)"] = f"{len(era):,}"
    out["SI era-matched politicians breached (%)"] = (
        f"{100 * len(set(in_common.email) & set(era)) / len(era):.1f}"
    )
    era_personal = addr.index[
        (addr.leg_start_year <= 2018) & (addr.ecategory == "Commercial")
    ]
    out["SI era-matched personal breached (%)"] = (
        f"{100 * len(set(in_common.email) & set(era_personal)) / len(era_personal):.1f}"
    )

    yg_n = len(pd.read_csv(yg_prof_path))
    yg = pd.read_csv(yg_hits_path, usecols=["id", "Name"])
    yg_common = yg[yg.Name.isin(common)]
    out["SI YouGov breached (%)"] = f"{100 * yg_common.id.nunique() / yg_n:.1f}"
    # Resolved through the SAME taxonomy as the politician side; that identity
    # is what makes the construct comparison like-for-like rather than a
    # comparison of two differently-defined outcomes.
    tax = pd.read_csv(os.path.join(ANALYSIS, "breach_taxonomy.csv"))
    yg_service = yg_common.merge(tax, left_on="Name", right_on="name", how="left")
    assert not yg_service.tax_class.isna().any(), "unclassified breach in YouGov hits"
    out["SI YouGov service (%)"] = (
        f"{100 * yg_service[yg_service.tax_class == 'service'].id.nunique() / yg_n:.1f}"
    )
    return out


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
    first = hibp.assign(k=hibp.Filename.str.lower()).groupby("k")["BreachDate"].min()

    df = pd.read_csv(
        os.path.join(DATA, "email_lvl_cov.csv"),
        usecols=["email", "cc3", "leg_start_date", "leg_start_year"],
    )
    # Singapore legislature start dates are absent upstream; the notebook
    # patches them from leg_start_year.
    sgp = {
        2021: "2020-08-24",
        2016: "2016-01-15",
        2011: "2011-10-10",
        2006: "2006-11-02",
        2001: "2002-03-25",
    }
    df["leg_start_date"] = (
        pd.Series(pd.NA, index=df.index)
        .where(df.cc3 != "SGP", df.leg_start_year.map(sgp))
        .fillna(df.leg_start_date)
    )
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


def check_crosscountry(results):
    """Check generated cross-country values and their manuscript bindings."""
    initial_result_count = len(results)
    values_path = os.path.join(TABLES, "country_check_values.tex")
    table_path = os.path.join(TABLES, "country_predictors.tex")
    if not os.path.exists(values_path) or not os.path.exists(table_path):
        results.append(
            (
                "cross-country outputs",
                "UNTESTABLE",
                "run scripts/11_crosscountry.R and scripts/12_format_ms_tables.py",
            )
        )
        return

    values_text = read_text(values_path)
    manuscript_text = read_text(MS)
    macros = dict(re.findall(r"\\newcommand\{\\(\w+)\}\{([^}]*)\}", values_text))
    required = {
        "CrossCountryN",
        "CrossCountryAnyIncomeRSquared",
        "CrossCountrySeriousIncomeRSquared",
        "CrossCountrySeriousFullRSquared",
        "CrossCountrySeriousEnglishShapley",
        "CrossCountrySeriousEgdiShapley",
        "CrossCountryShapleyDraws",
    }
    missing = required - macros.keys()
    if missing:
        results.append(("cross-country macros", "MISSING", ", ".join(sorted(missing))))
        return

    for macro in sorted(required):
        if f"\\{macro}" not in manuscript_text:
            results.append(
                (f"unused cross-country macro {macro}", macros[macro], "not in ms.tex")
            )

    if macros["CrossCountryShapleyDraws"] != "10000":
        results.append(
            (
                "Shapley bootstrap draws",
                macros["CrossCountryShapleyDraws"],
                "must equal the 10,000 draws advertised by the analysis",
            )
        )

    table_lines = read_text(table_path).splitlines()

    def cells(label):
        line = next(
            (line for line in table_lines if line.startswith(label + " &")), None
        )
        if line is None:
            return None
        return [cell.strip().rstrip("\\") for cell in line.split("&")[1:]]

    countries = cells("Countries")
    r_squared = cells(r"R$^2$")
    if countries is None or r_squared is None:
        results.append(
            ("cross-country table rows", "MISSING", "Countries or R-squared")
        )
        return

    expected = {
        "CrossCountryN": countries[0],
        "CrossCountryAnyIncomeRSquared": f"{float(r_squared[0]):.2f}",
        "CrossCountrySeriousIncomeRSquared": f"{float(r_squared[2]):.2f}",
        "CrossCountrySeriousFullRSquared": f"{float(r_squared[3]):.2f}",
    }
    for macro, value in expected.items():
        if macros[macro] != value:
            results.append(
                (f"cross-country {macro}", macros[macro], f"table implies {value}")
            )

    if len(results) == initial_result_count:
        results.append(
            (
                "cross-country generated values",
                ", ".join(f"{name}={macros[name]}" for name in sorted(required)),
                "ok",
            )
        )


def main():
    verbose = "--verbose" in sys.argv
    prose = ms_prose()
    claims = build_claims()
    unsupported = check_unsupported_claims()
    if unsupported:
        print("Unsupported claims found: " + ", ".join(unsupported))
        return 1

    tables_txt = all_table_text()
    print(f"Checking {len(claims)} quantities against ms/ms.tex\n")
    fails = []

    foreign = check_no_foreign_text()
    if foreign:
        print(
            "  FOREIGN     private_blacklight prose is back in ms.tex: "
            f"{', '.join(foreign)}"
        )
        fails.append(("foreign text in ms.tex", ", ".join(foreign)))
    for name, value, note in claims:
        if value is None:
            print(f"  UNTESTABLE  {name:<34} (source fragment missing)")
            continue
        if name in PHRASED_IN_WORDS:
            phrase = PHRASED_IN_WORDS[name]
            if phrase in prose:
                if verbose:
                    print(f'  in-words    {name:<34} = {value}  ("{phrase}")')
            else:
                print(
                    f"  NOT IN MS   {name:<34} = {value}  "
                    f'(expected phrase "{phrase}" is gone)'
                )
                fails.append((name, value))
            continue
        if says(prose, value):
            if verbose:
                print(f"  in-prose    {name:<34} = {value}  {note}")
            continue
        stale = stale_near_miss(prose, value)
        if stale is not None:
            print(f"  STALE       {name:<34} = {value}  (prose still says {stale})")
            fails.append((name, value))
        elif says(tables_txt, value):
            if verbose:
                print(f"  in-table    {name:<34} = {value}")
        else:
            print(f"  NOT IN MS   {name:<34} = {value}  {note}")
            fails.append((name, value))

    extra = []
    check_regtab(prose, extra)
    check_crosscountry(extra)
    if extra:
        print()
        for name, value, status in extra:
            if status != "ok":
                print(f"  STALE       {name:<34} = {value}  ({status})")
                fails.append((name, value))
            elif verbose:
                print(f"  generated   {name:<34} = {value}")

    print()
    if fails:
        print(
            f"{len(fails)} value(s) computed here do not appear in the manuscript prose."
        )
        print("Either the prose is stale, or the quantity is phrased differently")
        print("(e.g. 'nearly one in three' for 33.0). Check each before dismissing.")
        return 1
    print("All checked quantities appear in the manuscript.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
