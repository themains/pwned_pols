"""12_format_ms_tables.py
Wrap pipeline table fragments into the float environments the manuscript inputs.

ms/ms.tex reads tables/table_1_everypol, table_2_pwnpol_datatypes,
table_3_pwnpols_breach_incident, table_4_pwnpols_number_of_breaches and
tables/regtab. None of them existed in the repo or in git history -- they were
maintained by hand outside version control, which is where a number drifts away
from the script that produced it without anything noticing. This script closes
that gap: the numbers still come from the pipeline fragments written by
07_everypol_summ.ipynb and 11_breach_prob.R, and only the caption, column
headers and label are added here.

The \\label each wrapper carries is the one ms.tex already \\cref s, so the
cross-references resolve without touching the prose.

Input:  tables/hibp_pooled_emailcoverage_summary.tex        (07, cell 41)
        tables/pooled_pols_breach_number_summary.tex        (07, cell 98)
        tables/pooled_pols_seriousbreach_number_summary.tex (07, cell 102)
        tables/hibp_pwnpols_datatypes.tex                   (07, cell 106)
        tables/hibp_pwnpols_breach_incidents.tex            (07, cell 110)
        tables/breach_prob.tex                              (11_breach_prob.R)
Output: tables/table_1_everypol.tex                 (tab:tableone)
        tables/table_4_pwnpols_number_of_breaches.tex (tab:pooled_pols_breach_summary)
        tables/table_2_pwnpol_datatypes.tex         (tab:hibp_pwnedpols_datatype)
        tables/regtab.tex                           (tab:breach_lpm)
        tables/table_3_pwnpols_breach_incident.tex  (tab:top20_pols_breach_incidences)
        tables/country_predictors.tex                (tab:country_predictors)
        tables/serious_sensitivity.tex               (tab:serious-sensitivity)
"""

import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(_HERE, ".."))
TABLES = os.path.join(REPO, "tables")

# Said once here so the captions that need it inherit it rather than drifting
# apart. Both facts bear on how every number in these tables should be read.
LOWER_BOUND_NOTE = (
    "HIBP indexes only breaches that have become public and been ingested, and "
    "we observe at most one address per politician for most of the sample, so "
    "every figure is a lower bound."
)

SERIOUS_NOTE = (
    "A breach is coded serious if it exposed at least one of the 38 data "
    "classes listed in \\cref{tab:serious_dataclasses}."
)


def read_fragment(name):
    """Return a fragment's body, or exit with the script that should have made it."""
    path = os.path.join(TABLES, name)
    if not os.path.exists(path):
        sys.exit(
            f"missing fragment: tables/{name}\n"
            "Run 07_everypol_summ.ipynb (and 11_breach_prob.R for breach_prob.tex) first."
        )
    with open(path) as fh:
        body = fh.read().rstrip("\n")
    if not body.strip():
        sys.exit(f"empty fragment: tables/{name}")
    return body


def write_table(stem, text):
    path = os.path.join(TABLES, f"{stem}.tex")
    with open(path, "w") as fh:
        fh.write(text.rstrip("\n") + "\n")
    print(f"  wrote tables/{stem}.tex")


def float_wrap(caption, label, align, header, body, note, small=r"\footnotesize"):
    """Standard table float: caption above, note below, adjustbox for width."""
    return f"""\\begin{{table}}[!htbp]
\\centering
{small}
\\def\\sym#1{{\\ifmmode^{{#1}}\\else\\(^{{#1}}\\)\\fi}}
\\caption{{{caption}}}
\\label{{{label}}}
\\begin{{adjustbox}}{{max width=\\linewidth}}
\\begin{{tabular}}{{{align}}}
\\toprule\\toprule
{header}
{body}
\\bottomrule
\\end{{tabular}}
\\end{{adjustbox}}
\\caption*{{\\scriptsize \\emph{{Note:}} {note}}}
\\end{{table}}"""


# ---------------------------------------------------------------- Table 1
def table_1_everypol():
    body = read_fragment("hibp_pooled_emailcoverage_summary.tex")
    header = (
        r"& ISO & Country & Emails & Legislature years & Chamber & "
        r"Legislature & Pop. (M) \\"
    )
    return float_wrap(
        caption="Politician email coverage by country",
        label="tab:tableone",
        align="llrrlllr",
        header=header,
        body=body,
        note=(
            "One row per country in the analysis sample. Emails counts unique "
            "addresses after validation and deduplication. Legislatures with "
            "fewer than 30 listed email addresses are excluded. Population is "
            "2024 World Bank total population; it is missing for territories "
            "the series does not cover. " + LOWER_BOUND_NOTE
        ),
        small=r"\scriptsize",
    )


# ---------------------------------------------------------------- Table 4
def table_4_number_of_breaches():
    """Two panels: any breach (A) and serious breach (B), same column layout."""
    panel_a = read_fragment("pooled_pols_breach_number_summary.tex")
    panel_b = read_fragment("pooled_pols_seriousbreach_number_summary.tex")
    header = (
        r"& N & Mean & SD & Min & P25 & Median & P75 & Max & "
        r"$\geq 1$ & $\geq 2$ \\"
    )
    body = (
        r"\multicolumn{11}{l}{\emph{Panel A: All breaches}} \\"
        f"\n{panel_a}\n"
        r"\midrule"
        "\n"
        r"\multicolumn{11}{l}{\emph{Panel B: Serious breaches}} \\"
        f"\n{panel_b}"
    )
    return float_wrap(
        caption="Number of breaches per politician email address",
        label="tab:pooled_pols_breach_summary",
        align="lrrrrrrrrrr",
        header=header,
        body=body,
        note=(
            "The unit is an email address, not a politician; politicians with "
            "more than one listed address contribute more than one row. The "
            "final two columns give the share of addresses appearing in at "
            "least one and at least two distinct breaches. "
            + SERIOUS_NOTE
            + " "
            + LOWER_BOUND_NOTE
        ),
    )


# ---------------------------------------------------------------- Table 2
def table_2_datatypes():
    body = read_fragment("hibp_pwnpols_datatypes.tex")
    col = r"& Data class & N & \% & "
    header = (col * 3).rstrip("& ") + r"\\"
    return float_wrap(
        caption="Data classes exposed in breaches involving politicians",
        label="tab:hibp_pwnedpols_datatype",
        align="rlrrl" * 3,
        header=header,
        body=body,
        note=(
            "Percentages are of breached addresses, not of all addresses, so "
            "they do not sum to 100. Read in three column blocks, ranked by "
            "frequency. " + LOWER_BOUND_NOTE
        ),
        small=r"\scriptsize",
    )


# ---------------------------------------------------------------- Table 3
def table_3_breach_incident():
    body = read_fragment("hibp_pwnpols_breach_incidents.tex")
    header = (
        r"& Breach & N & \% & Domain & Breach date & Added date & "
        r"Lag & Accounts & Data classes & Sensitive \\"
    )
    return float_wrap(
        caption="Breach incidents most often involving politician email addresses",
        label="tab:top20_pols_breach_incidences",
        align="rlrrlllrrrc",
        header=header,
        body=body,
        note=(
            "Ranked by the number of politician addresses in the breach. "
            "Percentages are of breached addresses. Lag is the interval "
            "between the breach date HIBP records and the date HIBP added it; "
            "because the breach date is often HIBP's approximation and the "
            "added date reflects ingestion rather than disclosure, the lag is "
            "an ingestion latency, not a disclosure latency. " + LOWER_BOUND_NOTE
        ),
        small=r"\scriptsize",
    )


# ---------------------------------------------------- country predictors
def country_predictors():
    body = read_fragment("country_predictors_body.tex")
    header = r"""& \multicolumn{4}{c}{Dependent variable: estimated country fixed effect} \\
\cmidrule(l){2-5}
& \multicolumn{2}{c}{Any breach} & \multicolumn{2}{c}{Serious breach} \\
\cmidrule(lr){2-3}\cmidrule(l){4-5}
& (1) & (2) & (3) & (4) \\
\midrule"""
    return float_wrap(
        caption="Country-level predictors of estimated country fixed effects",
        label="tab:country_predictors",
        align="lrrrr",
        header=header,
        body=body,
        note=(
            "OLS point estimates using current, unrounded first-stage country "
            "fixed effects. Parentheses contain HC3 standard errors. Brackets "
            "contain percentile 95\\% intervals from 999 hierarchical bootstrap "
            "draws that resample countries and then email addresses within "
            "countries and re-estimate both stages. English official language "
            "is an indicator; GCI is the 0--100 Global Cybersecurity Index of "
            "national commitments; EGDI and V-Dem range from 0 to 1. Stars use "
            "HC3 p-values. $^{{+}}$ $p<0.1$, $^{{*}}$ $p<0.05$, "
            "$^{{**}}$ $p<0.01$, $^{{***}}$ $p<0.001$."
        ),
        small=r"\scriptsize",
    )


# ------------------------------------------------ country fixed effects
def country_fixed_effects():
    body = read_fragment("country_fixed_effects_body.tex")
    header = r"\# & ISO & Country & Serious breaches & Breaches \\"
    return float_wrap(
        caption="Estimated country fixed effects (ranked by serious breaches)",
        label="tab:fixed_effects",
        align="rllrr",
        header=header,
        body=body,
        note=(
            "Estimated country fixed effects, partialing out personal/official "
            "email classification and decade fixed effects. The serious-breach "
            "column comes from Model (3) of \\cref{tab:breach_lpm}; the "
            "any-breach column comes from Model (1). Values are rounded only "
            "for display; downstream analysis uses the unrounded RDS artifact."
        ),
        small=r"\scriptsize",
    )


def serious_sensitivity():
    body = read_fragment("serious_sensitivity_body.tex")
    header = r"Outcome definition & Official rate (N) & Commercial rate (N) & Official, role excluded & Commercial, role excluded \\"
    return float_wrap(
        caption="Sensitivity of serious-breach prevalence to outcome definition",
        label="tab:serious-sensitivity",
        align="lrrrr",
        header=header,
        body=body,
        note=(
            "Rates are proportions of email addresses. The primary definition "
            "includes Tier 2 and Tier 3 classes; the narrow definition includes "
            "Tier 3 only; the password definition includes credential and recovery "
            "classes. Role-account columns exclude local-part prefixes commonly "
            "used for shared institutional mailboxes."
        ),
        small=r"\scriptsize",
    )


# ---------------------------------------------------------------- regtab
def regtab():
    """breach_prob.tex already carries its own tabular/adjustbox from etable().

    etable(file=) appends rather than overwrites, so the fragment can hold
    several identical copies of the table. Keep only the first.
    """
    body = read_fragment("breach_prob.tex")
    marker = r"\begingroup"
    parts = [p for p in body.split(marker) if p.strip()]
    if len(parts) > 1:
        print(
            f"  note: breach_prob.tex holds {len(parts)} copies "
            "(etable appends); keeping the first"
        )
    body = marker + parts[0].rstrip()

    return f"""\\begin{{table}}[!htbp]
\\centering
\\caption{{Linear probability models of breach exposure}}
\\label{{tab:breach_lpm}}
{body}
\\caption*{{\\scriptsize \\emph{{Note:}}
Linear probability models estimated with \\texttt{{fixest::feols}}. The unit is
an email address. Standard errors, in parentheses, are clustered on country;
note that 59 country clusters are dominated by India, which supplies 26.9\\% of
the sample, so the effective number of clusters is far smaller than the nominal
one. Columns 2 and 4 are estimated on the EveryPolitician subsample only, since
gender, party and social-media fields exist only there; they are a different
sample, not a robustness check on columns 1 and 3. Social media indicates that
EveryPolitician recorded a Twitter or Facebook handle, which is partly a measure
of how completely the record is populated.
{SERIOUS_NOTE}
$^{{+}}$ $p<0.1$, $^{{*}}$ $p<0.05$, $^{{**}}$ $p<0.01$, $^{{***}}$ $p<0.001$.
}}
\\end{{table}}"""


BUILDERS = {
    "table_1_everypol": table_1_everypol,
    "table_4_pwnpols_number_of_breaches": table_4_number_of_breaches,
    "table_2_pwnpol_datatypes": table_2_datatypes,
    "table_3_pwnpols_breach_incident": table_3_breach_incident,
    "country_predictors": country_predictors,
    "country_fixed_effects": country_fixed_effects,
    "serious_sensitivity": serious_sensitivity,
    "regtab": regtab,
}


def main():
    print("==> formatting manuscript tables")
    for stem, builder in BUILDERS.items():
        write_table(stem, builder())
    print(f"==> {len(BUILDERS)} tables written to tables/")


if __name__ == "__main__":
    main()
