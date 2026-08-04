## 17_breach_taxonomy.R -- classify every HIBP breach by how the data got out.
##
## The paper's headline ("a third of addresses breached") pools three things
## that mean very different amounts about the account holder:
##
##   aggregator  A broker, scraper or enrichment service held the address.
##               The subject never had an account and did nothing. Being here
##               says a marketing database had your business card.
##   combolist   Credentials appeared in an aggregated dump, spam corpus or
##               stealer log of unknown provenance. Evidence of compromise
##               somewhere, but not attributable to any one service.
##   service     A service the subject plausibly held an account with was
##               itself breached. This is the only class that supports a claim
##               about the subject's own accounts.
##
## The classification is a property of the BREACH, not of the sample, so it is
## computed once here and every downstream sample resolves through the same
## mapping. That is what makes the politician / YouGov / Florida comparison
## like-for-like on construct rather than only on level.
##
## Rules first, overrides second. Rules are preferred wherever they generalise
## to the whole catalogue; ../data/breach_taxonomy_overrides.csv carries only
## the cases needing human judgement, each with a written rationale, so the
## hand-coding is auditable rather than buried in a regex.

suppressPackageStartupMessages({
  library(dplyr)
  library(purrr)
  library(readr)
  library(stringr)
  library(tidyr)
})

source("utilities.R")

dir.create("../analysis", showWarnings = FALSE)
dir.create("../tables", showWarnings = FALSE)

CLASSES <- c("aggregator", "combolist", "service")

## Credential dumps, spam corpora and malware output. Deliberately checked
## BEFORE the aggregator rule: a stealer-log corpus is often also described as
## "collated", and the credential provenance is the more informative fact.
COMBO_RE <- str_c(
  "combo ?list|credential stuffing|collection of (credential|more than|[0-9])|",
  "collated from|spambot|spam operation|spam list|stealer|malware",
  collapse = ""
)

## Broker, scrape and enrichment vocabulary. "marketing firm" is included
## alongside "marketing company/data" because Exactis -- a pure data broker --
## is described only as a "marketing firm", and widening the rule is preferable
## to overriding a case the rule should have caught.
AGG_RE <- str_c(
  "scrap|data aggregat|enrichment|unprotected (elasticsearch|mongo ?db)|",
  "publicly (facing|exposed)|left exposed|sales engagement|lead generation|",
  "marketing (firm|company|data)|people search|(email )?address validation",
  collapse = ""
)

## Corpora built from infostealer malware output. A strict subset of combolist,
## kept as a flag rather than a fourth class so the three-way split stays clean.
## This is the closest free proxy for HIBP's paid /stealerLogsByEmail endpoint,
## and therefore a LOWER BOUND on stealer exposure: it sees only those stealer
## corpora that were loaded into the breach dataset.
STEALER_RE <- "stealer log|info ?stealer"

breaches <- read_csv("../data/breaches_01_2025.csv", show_col_types = FALSE)
overrides <- read_csv("../data/breach_taxonomy_overrides.csv", show_col_types = FALSE)

stopifnot(
  !anyDuplicated(breaches$Name),
  !anyDuplicated(overrides$name),
  all(overrides$class %in% CLASSES),
  all(overrides$name %in% breaches$Name)
)

taxonomy <- breaches %>%
  mutate(
    desc = str_to_lower(str_remove_all(replace_na(Description, ""), "<[^>]+>")),
    rule_class = case_when(
      IsSpamList | str_detect(desc, COMBO_RE) ~ "combolist",
      str_detect(desc, AGG_RE) ~ "aggregator",
      TRUE ~ "service"
    ),
    is_stealer = str_detect(desc, STEALER_RE) | IsMalware
  ) %>%
  left_join(overrides, by = c("Name" = "name")) %>%
  mutate(
    overridden = !is.na(class),
    tax_class = coalesce(class, rule_class)
  ) %>%
  select(name = Name, tax_class, rule_class, overridden, is_stealer,
         breach_date = BreachDate, pwn_count = PwnCount)

## An unclassified breach would silently drop hits from every downstream rate,
## so this is an assertion, not a warning.
stopifnot(
  all(taxonomy$tax_class %in% CLASSES),
  !any(is.na(taxonomy$tax_class)),
  nrow(taxonomy) == nrow(breaches)
)

saveRDS(taxonomy, "../analysis/breach_taxonomy.rds", version = 3)
## Also as CSV, so 13_check_ms_numbers.py can recompute the RATES independently
## without re-implementing the CLASSIFICATION. Duplicating the rules in Python
## would let the two rule sets drift apart silently; the arithmetic is what goes
## stale, and that is what the checker recomputes.
write_csv(taxonomy, "../analysis/breach_taxonomy.csv")

## ---------------------------------------------------------------------------
## Apply to the politician sample.
##
## Rebuilt from the raw HIBP files rather than from nbreach, because nbreach is
## a count and the split needs the breach names behind it. Case normalisation
## matters here: 382 HIBP filenames keep the capitalisation they were scraped
## in, and joining raw drops 380 addresses that then score as never breached.
## ---------------------------------------------------------------------------
## Keyed on email, not on row: the file stores 12,916 rows for 12,385 distinct
## addresses. See dedupe_email_level() in utilities.R.
emails <- read_csv("../data/email_lvl_cov.csv", show_col_types = FALSE) %>%
  dedupe_email_level()
stopifnot(!anyDuplicated(emails$email))

hits <- bind_rows(
  read_csv("../data/everypol_hibp.csv", show_col_types = FALSE),
  read_csv("../data/scraped_pol_hibp.csv", show_col_types = FALSE)
) %>%
  rename_with(str_to_lower) %>%
  filter(present) %>%
  mutate(email = str_to_lower(filename)) %>%
  filter(email %in% emails$email) %>%
  distinct(email, breach) %>%
  left_join(taxonomy, by = c("breach" = "name"))

stopifnot(!any(is.na(hits$tax_class)))

n_emails <- nrow(emails)

## The share of ADDRESSES in each class does not sum to 100 -- an address can
## appear in more than one class -- so it is computed against the full sample.
by_class <- hits %>%
  group_by(tax_class) %>%
  summarise(n_hits = n(), n_addr = n_distinct(email), .groups = "drop") %>%
  mutate(
    perc_hits = sprintf("%.1f\\%%", 100 * n_hits / sum(n_hits)),
    perc_addr = sprintf("%.1f\\%%", 100 * n_addr / n_emails),
    n_hits = format(n_hits, big.mark = ","),
    n_addr = format(n_addr, big.mark = ",")
  ) %>%
  arrange(match(tax_class, CLASSES)) %>%
  mutate(tax_class = recode(tax_class,
    aggregator = "Broker / scrape aggregation",
    combolist = "Credential combolist",
    service = "Service compromise"
  ))

write_tex_fragment(by_class, "../tables/breach_taxonomy_body.tex")

## ---------------------------------------------------------------------------
## Stealer-log exposure.
##
## HIBP loads some infostealer and malware corpora into the ordinary breach
## dataset, so they are searchable by any subscriber. Several come from
## documented law-enforcement seizures (Emotet: FBI/NHTCU; Qakbot: US DOJ).
## Unlike the rest of the catalogue these indicate credential capture from an
## infected machine rather than a third party holding the address.
##
## This is a LOWER BOUND. HIBP's dedicated /stealerLogsByEmail endpoint covers
## more, and it is unobtainable for this sample at any subscription tier: access
## requires verified control of the address or of its domain, which we do not
## have for parliament.uk, sansad.nic.in or gmail.com. What is lost is the list
## of target websites per address; what is kept is whether the address appears.
##
## Cells are small (286 addresses in total), so every rate is reported with its
## numerator, denominator and a Wilson interval rather than as a bare percent.
## ---------------------------------------------------------------------------
wilson <- function(x, n, conf = 0.95) {
  z <- qnorm(1 - (1 - conf) / 2)
  p <- x / n
  denom <- 1 + z^2 / n
  centre <- (p + z^2 / (2 * n)) / denom
  half <- z * sqrt(p * (1 - p) / n + z^2 / (4 * n^2)) / denom
  sprintf("[%.2f, %.2f]", 100 * max(0, centre - half), 100 * min(1, centre + half))
}

stealer_names <- taxonomy$name[taxonomy$is_stealer]
stealer_hits <- filter(hits, is_stealer)
stealer_emails <- unique(stealer_hits$email)

per_corpus <- taxonomy %>%
  filter(is_stealer) %>%
  left_join(count(stealer_hits, breach, name = "n_addr"),
            by = c("name" = "breach")) %>%
  mutate(n_addr = replace_na(n_addr, 0L)) %>%
  arrange(desc(n_addr), name) %>%
  transmute(
    row = name,
    date = substr(as.character(breach_date), 1, 7),
    n = format(n_addr, big.mark = ","),
    pct = sprintf("%.2f\\%%", 100 * n_addr / n_emails),
    ci = map2_chr(n_addr, n_emails, wilson)
  )

## Denominators differ by row, so they are carried explicitly.
group_row <- function(label, rows) {
  x <- sum(rows$email %in% stealer_emails)
  denom <- nrow(rows)
  # Computed before the tibble: a column named `n` would shadow the local `n`
  # in later arguments, because tibble() evaluates them in sequence.
  tibble(row = label, date = "", n = format(x, big.mark = ","),
         pct = sprintf("%.2f\\%%", 100 * x / denom), ci = wilson(x, denom))
}

summary_rows <- bind_rows(
  group_row("\\textit{Any stealer corpus}", emails),
  group_row("\\quad personal addresses", filter(emails, ecategory == "Commercial")),
  group_row("\\quad official addresses", filter(emails, ecategory != "Commercial"))
)

write_tex_fragment(bind_rows(per_corpus, summary_rows),
                   "../tables/stealer_logs_body.tex")

## Number of distinct corpora each exposed address appears in. Reported in the
## SI text rather than the table: repeat appearance is the part that is hard to
## explain as incidental inclusion.
multi <- stealer_hits %>%
  count(email, name = "n_corpora") %>%
  count(n_corpora, name = "n_addr")

saveRDS(
  list(per_corpus = per_corpus, summary_rows = summary_rows, multi = multi,
       n_addresses = length(stealer_emails), n_sample = n_emails,
       corpora = sort(stealer_names)),
  "../analysis/stealer_exposure.rds",
  version = 3
)

stealer_addr <- n_distinct(hits$email[hits$is_stealer])
any_addr <- n_distinct(hits$email)

cat(sprintf("breaches classified: %d (%d by override)\n",
            nrow(taxonomy), sum(taxonomy$overridden)))
print(as.data.frame(by_class))
cat(sprintf(
  "\naddresses with any hit: %s of %s (%.1f%%)\n",
  format(any_addr, big.mark = ","), format(n_emails, big.mark = ","),
  100 * any_addr / n_emails
))
cat(sprintf(
  "addresses in a stealer-log corpus: %s (%.2f%%) -- LOWER BOUND, %d such corpora in catalogue\n",
  format(stealer_addr, big.mark = ","), 100 * stealer_addr / n_emails,
  sum(taxonomy$is_stealer)
))
