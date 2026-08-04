## 18_three_sample_comparison.R -- politicians vs. general-population samples,
## on a common breach catalogue and a common construct.
##
## The paper reports that ~33% of politician addresses appear in a breach, and
## calls that alarming, but nothing anchors the level. Two sibling studies by
## the same authors supply population benchmarks:
##
##   YouGov  5,000 US adults, queried 2018 against a 293-breach catalogue
##   Florida ~1.35M voter-file addresses, queried 2023 against 680 breaches
##
## Two things have to be harmonised before any comparison means anything.
##
## 1. THE CATALOGUE. Scoring a 2018 sample against 293 breaches and a 2025
##    sample against 857 is not a robustness detail -- it is most of the gap.
##    The three catalogues are perfectly nested (asserted below), so the
##    comparison restricts every sample to their intersection. No fuzzy
##    matching, no name harmonisation.
##
## 2. THE CONSTRUCT. "Breached" pools broker aggregation with genuine service
##    compromise, and the mix differs sharply between politicians and the
##    public. Every sample is therefore also split by 17_breach_taxonomy.R's
##    classification, which resolves through one shared mapping.
##
## Breach metadata (data classes, taxonomy) is taken from the 2025 catalogue for
## BOTH samples rather than from each study's own snapshot. HIBP revises breach
## records over time, so using one snapshot is what makes "serious" mean the
## same thing on both sides. It does mean the YouGov rows are scored against
## metadata newer than their query date.
##
## The level comparison runs hard AGAINST the paper's framing. That is reported,
## not buried, together with the confounds that make it uninterpretable in both
## directions -- see the manuscript text.

suppressPackageStartupMessages({
  library(dplyr)
  library(jsonlite)
  library(purrr)
  library(readr)
  library(stringr)
  library(tidyr)
})

source("utilities.R")

dir.create("../analysis", showWarnings = FALSE)
dir.create("../tables", showWarnings = FALSE)

FLORIDA_HITS <- "../data/benchmark/florida_hibp.csv"

breaches <- read_csv("../data/breaches_01_2025.csv", show_col_types = FALSE)
taxonomy <- readRDS("../analysis/breach_taxonomy.rds")

## DataClasses ships as a Python list repr, e.g. "['Email addresses', 'Names']".
serious_names <- breaches %>%
  mutate(
    classes = str_split(str_remove_all(DataClasses, "^\\[|\\]$|'"), ",\\s*"),
    serious = map_lgl(classes, ~ any(str_trim(.x) %in% LIST_SERIOUS_DATACLASSES))
  ) %>%
  select(name = Name, serious)

catalogue <- taxonomy %>%
  select(name, tax_class, is_stealer) %>%
  left_join(serious_names, by = "name")

## ---------------------------------------------------------------------------
## Catalogue nesting. The whole comparison rests on this, so it is asserted
## rather than assumed -- a future catalogue refresh that breaks it must fail
## the build loudly instead of silently producing an incomparable table.
## ---------------------------------------------------------------------------
cat_pol <- breaches$Name
cat_yg <- fromJSON("../data/benchmark/yougov_breaches.json")$Name
cat_fl <- fromJSON("../data/benchmark/florida_breaches.json")$Name

if (!all(cat_yg %in% cat_pol) || !all(cat_fl %in% cat_pol) || !all(cat_yg %in% cat_fl)) {
  stop(
    "catalogue nesting violated (expected YouGov subset-of Florida subset-of politicians); ",
    "yougov-not-in-politicians: ", length(setdiff(cat_yg, cat_pol)),
    ", florida-not-in-politicians: ", length(setdiff(cat_fl, cat_pol)),
    ", yougov-not-in-florida: ", length(setdiff(cat_yg, cat_fl))
  )
}
COMMON <- sort(intersect(intersect(cat_pol, cat_yg), cat_fl))
cat(sprintf(
  "catalogues: politicians %d, florida %d, yougov %d -> common %d\n",
  length(cat_pol), length(cat_fl), length(cat_yg), length(COMMON)
))

## ---------------------------------------------------------------------------
## Why the harmonised panel cannot be read on its own.
##
## The common catalogue is a 2018 draw, so restricting to it also restricts the
## ERA. Every broker corpus that dominates politician exposure post-dates it --
## db8151dd (2020), PDL (2019), VerificationsIO (2019), DemandScience (2024),
## LinkedInScrape (2021), Twitter200M (2021). So the politician aggregator share
## collapsing under harmonisation is a catalogue-vintage artifact, NOT evidence
## that politicians have little broker exposure. Printed every run so the
## restriction can never be forgotten when reading the table.
## ---------------------------------------------------------------------------
common_meta <- breaches %>%
  filter(Name %in% COMMON) %>%
  mutate(year = as.integer(format(as.Date(BreachDate), "%Y")))
cat(sprintf(
  "common catalogue spans %d-%d; full catalogue spans %d-%d; %d breaches excluded by harmonisation\n",
  min(common_meta$year), max(common_meta$year),
  min(as.integer(format(as.Date(breaches$BreachDate), "%Y"))),
  max(as.integer(format(as.Date(breaches$BreachDate), "%Y"))),
  length(cat_pol) - length(COMMON)
))
COMMON_LAST_YEAR <- max(common_meta$year)

## ---------------------------------------------------------------------------
## Long address/person x breach tables, one per sample.
## ---------------------------------------------------------------------------
## Keyed on email, not on row: the file stores 12,916 rows for 12,385 distinct
## addresses, so nrow() would understate every rate by ~4%. See
## dedupe_email_level() in utilities.R.
pol_emails <- read_csv("../data/email_lvl_cov.csv", show_col_types = FALSE) %>%
  dedupe_email_level()
stopifnot(!anyDuplicated(pol_emails$email))

pol_hits <- bind_rows(
  read_csv("../data/everypol_hibp.csv", show_col_types = FALSE),
  read_csv("../data/scraped_pol_hibp.csv", show_col_types = FALSE)
) %>%
  rename_with(str_to_lower) %>%
  filter(present) %>%
  # 382 HIBP filenames keep the capitalisation they were scraped in; joining
  # raw drops 380 addresses that then score as never breached.
  mutate(unit = str_to_lower(filename)) %>%
  filter(unit %in% pol_emails$email) %>%
  distinct(unit, breach)

## YGOV1058_pwned.csv holds only breached respondents; the denominator is the
## 5,000-row profile file, so unbreached respondents are never dropped.
yg_n <- nrow(read_csv("../data/benchmark/YGOV1058_profile.csv", show_col_types = FALSE))
yg_hits <- read_csv("../data/benchmark/YGOV1058_pwned.csv", show_col_types = FALSE) %>%
  transmute(unit = as.character(id), breach = Name) %>%
  distinct()

samples <- list(
  Politicians = list(hits = pol_hits, n = nrow(pol_emails)),
  `US adults (YouGov)` = list(hits = yg_hits, n = yg_n)
)

if (file.exists(FLORIDA_HITS)) {
  fl <- read_csv(FLORIDA_HITS, show_col_types = FALSE)
  samples[["Florida voters"]] <- list(
    hits = distinct(transmute(fl, unit = as.character(unit), breach)),
    n = n_distinct(fl$unit)
  )
} else {
  cat(sprintf(
    "NOTE: Florida sample omitted -- %s absent. Retrieve doi:10.7910/DVN/NTN9EP.\n",
    FLORIDA_HITS
  ))
}

## ---------------------------------------------------------------------------
## Rates, restricted to the common catalogue.
## ---------------------------------------------------------------------------
rates <- function(hits, n, restrict) {
  h <- hits %>%
    filter(breach %in% restrict) %>%
    left_join(catalogue, by = c("breach" = "name"))
  # An unmatched breach would silently vanish from every rate below.
  stopifnot(!any(is.na(h$tax_class)))
  pct <- function(x) sprintf("%.1f\\%%", 100 * x / n)
  tibble(
    n = format(n, big.mark = ","),
    any = pct(n_distinct(h$unit)),
    serious = pct(n_distinct(h$unit[h$serious])),
    service = pct(n_distinct(h$unit[h$tax_class == "service"])),
    aggregator = pct(n_distinct(h$unit[h$tax_class == "aggregator"])),
    combolist = pct(n_distinct(h$unit[h$tax_class == "combolist"])),
    stealer = pct(n_distinct(h$unit[h$is_stealer]))
  )
}

## Era matching. The common catalogue closes in 2018, so an address created
## after that could not have been exposed by any breach in it. Politicians are
## structurally young (median legislative start 2015, 25% starting in 2025);
## every YouGov respondent existed in 2018. Comparing without this restriction
## charges politicians for breaches that predate their addresses -- the
## time-at-risk problem, and it runs the full width of the gap.
pol_subset <- function(rows) {
  list(
    hits = semi_join(pol_hits, rows, by = c("unit" = "email")),
    n = nrow(rows)
  )
}

era_rows <- filter(pol_emails, leg_start_year <= COMMON_LAST_YEAR)

era_samples <- samples
era_samples[["Politicians"]] <- pol_subset(era_rows)
## Address TYPE is the confound era matching cannot touch. 76% of politician
## addresses are institutional (@parliament.uk, @sansad.nic.in), whereas a
## YouGov respondent supplied a personal address -- their long-lived primary
## account, which is exactly where consumer-service breaches land. Restricting
## politicians to their personal addresses is the closest like-for-like this
## data supports, and it is the row the level comparison should be read from.
era_samples[["Politicians (personal addr.)"]] <-
  pol_subset(filter(era_rows, ecategory == "Commercial"))
## Keep the two politician rows adjacent so the comparison row reads last.
era_samples <- era_samples[c(
  "Politicians", "Politicians (personal addr.)",
  setdiff(names(era_samples), c("Politicians", "Politicians (personal addr.)"))
)]

harmonised <- imap_dfr(samples, ~ rates(.x$hits, .x$n, COMMON) %>% mutate(sample = .y)) %>%
  relocate(sample)
era_matched <- imap_dfr(era_samples, ~ rates(.x$hits, .x$n, COMMON) %>% mutate(sample = .y)) %>%
  relocate(sample)
native <- imap_dfr(samples, ~ rates(.x$hits, .x$n, unique(.x$hits$breach)) %>%
                     mutate(sample = .y)) %>%
  relocate(sample)

write_tex_fragment(harmonised, "../tables/three_sample_harmonised_body.tex")
write_tex_fragment(era_matched, "../tables/three_sample_era_matched_body.tex")
write_tex_fragment(native, "../tables/three_sample_native_body.tex")
saveRDS(
  list(harmonised = harmonised, era_matched = era_matched, native = native,
       common_catalogue = COMMON, common_last_year = COMMON_LAST_YEAR),
  "../analysis/three_sample_comparison.rds",
  version = 3
)

cat("\n== A. each sample against its own full catalogue (NOT comparable) ==\n")
print(as.data.frame(native))
cat("\n== B. common", length(COMMON), "breaches; address vintage NOT matched ==\n")
print(as.data.frame(harmonised))
cat(sprintf(
  "\n== C. common %d breaches AND addresses existing by %d (the defensible panel) ==\n",
  length(COMMON), COMMON_LAST_YEAR
))
print(as.data.frame(era_matched))
