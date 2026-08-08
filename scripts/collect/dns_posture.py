"""Collection adapter: email-authentication posture of politician email domains.

Measures the PHISHING surface. From EuRepoC's coded initial-access techniques,
phishing is the single largest entry vector into political targets at 35.4% --
more than three times the share attributable to stolen credentials (10.9%),
which is the only vector the rest of this project measures. A domain without an
enforcing DMARC policy can be spoofed, and spoofing is how phishing at
institutions usually starts.

Uses `checkdmarc` rather than a hand-rolled resolver. That package already
parses and validates SPF (including the ten-DNS-lookup limit, which is fiddly
and easy to get wrong), DMARC, MTA-STS, SMTP-TLS reporting, DNSSEC and MX
STARTTLS. Reimplementing it would add bugs and no capability.

THE ONE THING THE WRAPPER MUST ADD is the distinction between "this domain
publishes no DMARC record" and "we could not find out". They are not the same
fact and conflating them manufactures findings. The very first three-domain test
hit it: bunge.go.tz returned no DMARC because the lookup timed out, not because
Tanzania's parliament publishes nothing. The same failure already cost this
project once -- 150 of the 154 domains rejected by the existing MX validation
failed on transient timeout rather than NXDOMAIN, silently dropping ~270 real
addresses from the analysis.

So every record here carries a STATUS, and a timeout is `lookup_failed`, never
`absent`. Downstream analysis must treat `lookup_failed` as missing data.

FROZEN. Listed in FROZEN_COLLECTORS; never runs in a build.

Usage:  python scripts/collect/dns_posture.py [--limit N]
"""

import argparse
import json
import os
import sys
from datetime import date

import pandas as pd

REPO = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
RAW = os.path.join(REPO, "data", "raw", "dns_posture")
OUT = os.path.join(REPO, "data", "domain_security.csv")

# Errors that mean "we failed to ask", as opposed to "the answer is no".
TRANSIENT = ("timed out", "resolution lifetime expired", "no nameservers",
             "connection", "temporary")


def status_of(block):
    """Classify a checkdmarc sub-result as ok / absent / lookup_failed.

    checkdmarc reports both a missing record and a failed lookup as valid=False
    with a message in `error`. Separating them is the whole point of this
    wrapper, so the classification is explicit and errors that match nothing
    known fall through to lookup_failed rather than being assumed absent --
    failing toward "we do not know" is the safe direction.
    """
    if not isinstance(block, dict):
        return "lookup_failed", None
    if block.get("valid"):
        return "ok", block.get("error")
    err = str(block.get("error") or "").lower()
    if not err:
        return "absent", None
    if any(t in err for t in TRANSIENT):
        return "lookup_failed", block.get("error")
    # A syntactically broken record is present-but-wrong, which is a different
    # and interesting state: the domain owner tried and failed.
    return "invalid", block.get("error")


def spf_qualifier(record):
    """The 'all' qualifier decides whether SPF actually rejects anything.

    -all is a hard fail, ~all a soft fail that most receivers accept anyway, and
    +all is worse than no record at all because it authorises the world.
    """
    if not record:
        return None
    r = str(record).lower()
    for token, label in (("-all", "hard_fail"), ("~all", "soft_fail"),
                         ("?all", "neutral"), ("+all", "pass_all")):
        if token in r:
            return label
    return "no_all"


def domains_from_sample():
    """One row per domain, with how many addresses sit behind it.

    Weighting matters: a misconfigured domain carrying 626 addresses is a
    different finding from one carrying 2.
    """
    cov = pd.read_csv(os.path.join(REPO, "data", "email_lvl_cov.csv"))
    cov = cov.drop_duplicates("email")
    cov["domain"] = cov.email.str.split("@").str[-1].str.lower()
    agg = (
        cov.groupby("domain")
        .agg(n_addresses=("email", "size"),
             ecategory=("ecategory", lambda s: s.mode().iat[0] if len(s.mode()) else None))
        .reset_index()
        .sort_values("n_addresses", ascending=False)
    )
    return agg


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=None,
                    help="only the N largest domains; for a pilot run")
    args = ap.parse_args()

    try:
        from checkdmarc import check_domains
    except ImportError:
        sys.exit("checkdmarc is not installed. pip install checkdmarc")

    dom = domains_from_sample()
    if args.limit:
        dom = dom.head(args.limit)
    print(f"==> checking {len(dom):,} domains")

    os.makedirs(RAW, exist_ok=True)
    today = date.today().isoformat()

    # skip_tls: connecting to MX hosts to test STARTTLS would be active contact
    # with mail infrastructure. Everything here stays passive DNS lookups.
    results = check_domains(list(dom.domain), skip_tls=True)
    if isinstance(results, dict):
        results = [results]

    with open(os.path.join(RAW, f"checkdmarc_{today}.json"), "w") as fh:
        json.dump(results, fh, indent=1, default=str)

    rows = []
    for res in results:
        dmarc, spf = res.get("dmarc", {}), res.get("spf", {})
        d_status, d_err = status_of(dmarc)
        s_status, s_err = status_of(spf)
        policy = None
        tags = dmarc.get("tags") if isinstance(dmarc, dict) else None
        if isinstance(tags, dict):
            policy = (tags.get("p") or {}).get("value")
        rows.append({
            "domain": res.get("domain"),
            "dmarc_status": d_status,
            "dmarc_policy": policy,
            "dmarc_error": d_err,
            "spf_status": s_status,
            "spf_qualifier": spf_qualifier(spf.get("record") if isinstance(spf, dict) else None),
            "spf_error": s_err,
            "mta_sts": status_of(res.get("mta_sts"))[0],
            "dnssec": res.get("dnssec"),
            "checked_date": today,
            "source_id": "dns_posture",
        })

    out = pd.DataFrame(rows).merge(dom, on="domain", how="left")
    out.to_csv(OUT, index=False)

    n = len(out)
    print(f"\n  dmarc: " + ", ".join(
        f"{k} {v}" for k, v in out.dmarc_status.value_counts().items()))
    print(f"  policy among valid: " + ", ".join(
        f"{k} {v}" for k, v in out.dmarc_policy.value_counts(dropna=False).items()))
    failed = (out.dmarc_status == "lookup_failed").sum()
    print(f"\n  {failed} of {n} DMARC lookups FAILED and are recorded as missing,")
    print("  not as 'no DMARC'. Treat them as missing downstream.")
    print(f"  wrote {OUT}")


if __name__ == "__main__":
    main()
