## 20_sensitivity.R -- what the two discretionary choices in this pipeline cost.
##
## Two steps are judgement rather than arithmetic, and a reader has no way to
## tell how much either one is doing:
##
##   1. Collapsing email_lvl_cov.csv to one row per address. The file holds
##      12,916 rows for 12,385 addresses, and the aggregation rule per field is
##      a choice (dedupe_email_level() in utilities.R takes min leg_start_year
##      and max nbreach).
##
##   2. Four breaches in data/breach_taxonomy_overrides.csv are classified by
##      hand where the rules misfire. They carry ~2.7% of all appearances.
##
## Asserting a choice is defensible is worth less than showing the range it
## spans, so both are recomputed here on every run and written out. The claim
## the paper actually rests on -- that more addresses appear in broker
## aggregation than in first-party service compromise -- is checked against
## EVERY specification, not just the published one.

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

taxonomy <- readRDS("../analysis/breach_taxonomy.rds")
cov_raw <- read_csv("../data/email_lvl_cov.csv", show_col_types = FALSE)

## Same normalisation as 06/17/18. Lowercasing alone matches two fewer
## addresses; bypassing this helper is what caused the drift fixed in 1bbc95f.
read_hibp <- function(path) {
  read_csv(path, show_col_types = FALSE) %>%
    rename(email = Filename, breach = Breach, present = Present) %>%
    clean_dedupe_email_column(dedup = FALSE)
}

addresses <- dedupe_email_level(cov_raw)
hits <- bind_rows(
  read_hibp("../data/everypol_hibp.csv"),
  read_hibp("../data/scraped_pol_hibp.csv")
) %>%
  filter(present, email %in% addresses$email) %>%
  distinct(email, breach)

N <- nrow(addresses)

## ---------------------------------------------------------------------------
## Dial 1 -- the taxonomy overrides.
##
## One function computes the shares, and every specification goes through it.
## A parallel reimplementation could agree with the headline today and drift
## tomorrow, which is the failure this whole file exists to make visible.
## ---------------------------------------------------------------------------
shares_for <- function(class_map) {
  hits %>%
    left_join(class_map, by = c("breach" = "name")) %>%
    { stopifnot(!any(is.na(.$cls))); . } %>%
    group_by(cls) %>%
    summarise(pct = 100 * n_distinct(email) / N, .groups = "drop") %>%
    complete(cls = CLASSES, fill = list(pct = 0)) %>%
    arrange(match(cls, CLASSES))
}

published_map <- taxonomy %>% transmute(name, cls = tax_class)
published <- shares_for(published_map)

overridden <- taxonomy %>% filter(overridden)

## Leave-one-out: revert a single override to what the rules would have said.
loo <- overridden$name %>%
  set_names() %>%
  map(function(nm) {
    shares_for(taxonomy %>%
      transmute(name, cls = if_else(name == nm, rule_class, tax_class)))
  })

all_reverted <- shares_for(taxonomy %>% transmute(name, cls = rule_class))

specs <- c(list(published = published), loo, list(all_reverted = all_reverted))

## The bound: the largest absolute movement of any share under any
## specification. This is the single number the SI should quote.
max_shift <- specs %>%
  map_dbl(~ max(abs(.x$pct - published$pct))) %>%
  max()

## The ordering the paper's argument depends on, checked everywhere.
ordering_holds <- specs %>%
  map_lgl(~ .x$pct[.x$cls == "aggregator"] > .x$pct[.x$cls == "service"]) %>%
  all()

tax_rows <- imap_dfr(specs, function(s, nm) {
  wide <- set_names(s$pct, s$cls)
  tibble(
    spec = nm,
    aggregator = wide[["aggregator"]],
    combolist = wide[["combolist"]],
    service = wide[["service"]]
  )
}) %>%
  left_join(
    hits %>% count(breach, name = "n_hits"),
    by = c("spec" = "breach")
  ) %>%
  mutate(
    label = recode(spec,
      published = "\\textit{As published}",
      all_reverted = "\\textit{All four reverted}",
      .default = paste0("\\quad revert ", spec)
    ),
    hits = ifelse(is.na(n_hits), "", format(n_hits, big.mark = ",")),
    across(all_of(CLASSES), ~ sprintf("%.2f\\%%", .x))
  ) %>%
  select(label, hits, all_of(CLASSES))

write_tex_fragment(tax_rows, "../tables/sensitivity_taxonomy_body.tex")

## ---------------------------------------------------------------------------
## Dial 2 -- the deduplication rule.
##
## The (min, max) row must reproduce dedupe_email_level() exactly. If it ever
## stops doing so, this table has silently become a different analysis from the
## one that produced the headline, so it is an assertion rather than a comment.
## ---------------------------------------------------------------------------
collapse_with <- function(year_rule, breach_rule) {
  cov_raw %>%
    group_by(email) %>%
    summarise(
      leg_start_year = year_rule(leg_start_year),
      nbreach = breach_rule(nbreach),
      nbreach_serious = breach_rule(nbreach_serious),
      .groups = "drop"
    )
}

reference <- collapse_with(min, max)
stopifnot(
  nrow(reference) == nrow(addresses),
  all(reference$nbreach == addresses$nbreach),
  all(reference$leg_start_year == addresses$leg_start_year)
)

dedup_rows <- expand_grid(
  year = c("min", "max"),
  breach = c("max", "sum", "first", "min")
) %>%
  pmap_dfr(function(year, breach) {
    d <- collapse_with(
      get(year),
      switch(breach, max = max, sum = sum, min = min, first = dplyr::first)
    )
    tibble(
      row = sprintf("%s / %s%s", year, breach,
                    if (year == "min" && breach == "max") " \\textit{(used)}" else ""),
      breached = sprintf("%.2f\\%%", 100 * mean(d$nbreach > 0)),
      serious = sprintf("%.2f\\%%", 100 * mean(d$nbreach_serious > 0)),
      mean_n = sprintf("%.3f", mean(d$nbreach)),
      era_n = format(sum(d$leg_start_year <= 2018), big.mark = ",")
    )
  })

write_tex_fragment(dedup_rows, "../tables/sensitivity_dedup_body.tex")

saveRDS(
  list(max_taxonomy_shift = max_shift, ordering_holds = ordering_holds,
       specs = specs, dedup = dedup_rows),
  "../analysis/sensitivity.rds", version = 3
)

cat("taxonomy specifications:\n")
print(as.data.frame(tax_rows))
cat(sprintf("\nlargest share movement across specifications: %.2f pp\n", max_shift))
cat(sprintf("aggregator > service in every specification: %s\n", ordering_holds))
cat("\ndeduplication rules:\n")
print(as.data.frame(dedup_rows))

if (!ordering_holds) {
  stop("aggregator no longer exceeds service in at least one specification -- ",
       "the manuscript's central provenance claim does not survive the taxonomy ",
       "as currently coded. Fix the argument, not this check.")
}
