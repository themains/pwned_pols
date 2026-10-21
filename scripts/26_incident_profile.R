## 26_incident_profile.R -- what observed incidents say about the danger
## politicians are actually in.
##
## Everything else in this repository measures EXPOSURE. This measures what
## happened, using EuRepoC's expert coding of 3,414 cyber incidents, and it
## asks three questions the exposure data cannot answer.
##
##   1. Do political targets face a different class of adversary?
##   2. Is the harm larger?
##   3. Do incidents against them actually begin with stolen credentials --
##      that is, is the mechanism this project measures the mechanism that
##      matters?
##
## The third is the one that disciplines the whole argument. A perfectly
## measured credential exposure is only interesting to the extent that
## credentials are how intrusions start.
##
## COVERAGE WARNING, which governs how far any of this can be pushed:
## EuRepoC codes publicly reported incidents, so its measurement error runs the
## same direction as HIBP's -- both track media attention and disclosure regimes
## and both over-represent Anglophone, wealthy states. And initial access is
## coded for only ~15% of incidents, almost certainly not at random, since
## better-documented incidents attract richer coding. Treat every comparison
## here as descriptive.

suppressPackageStartupMessages({
  library(dplyr)
  library(readr)
  library(stringr)
  library(tidyr)
})

source("utilities.R")

dir.create("../analysis", showWarnings = FALSE)
dir.create("../tables", showWarnings = FALSE)

PROFILE <- "../data/eurepoc_incident_profile.csv"
if (!file.exists(PROFILE)) {
  stop("missing ", PROFILE, " -- run scripts/collect/eurepoc.py first")
}

inc <- read_csv(PROFILE, show_col_types = FALSE)
pol <- filter(inc, is_political)
oth <- filter(inc, !is_political)

pct <- function(x) sprintf("%.1f\\%%", 100 * x)

## ---------------------------------------------------------------------------
## 1 & 2 -- adversary and magnitude.
## ---------------------------------------------------------------------------
compare <- tibble(
  row = c(
    "Incidents",
    "State-actor attribution",
    "Weighted intensity (mean)",
    "Weighted intensity (median)"
  ),
  political = c(
    format(nrow(pol), big.mark = ","),
    pct(mean(pol$state_attributed)),
    sprintf("%.2f", mean(pol$weighted_intensity, na.rm = TRUE)),
    sprintf("%.2f", median(pol$weighted_intensity, na.rm = TRUE))
  ),
  other = c(
    format(nrow(oth), big.mark = ","),
    pct(mean(oth$state_attributed)),
    sprintf("%.2f", mean(oth$weighted_intensity, na.rm = TRUE)),
    sprintf("%.2f", median(oth$weighted_intensity, na.rm = TRUE))
  )
)
write_tex_fragment(compare, "../tables/incident_profile_body.tex")

## ---------------------------------------------------------------------------
## 3 -- how intrusions begin.
##
## Reported over ALL coded incidents, not split by political target. Only 11
## political incidents carry a coded vector, which is too few to compare
## against, and reporting an 18% from n = 2 would be worse than reporting
## nothing. The overall distribution is the defensible quantity.
## ---------------------------------------------------------------------------
coded <- filter(inc, initial_access != "Not available", !is.na(initial_access))

vectors <- coded %>%
  count(initial_access, name = "n") %>%
  mutate(share = n / sum(n)) %>%
  arrange(desc(n)) %>%
  slice_head(n = 6) %>%
  transmute(initial_access, n = format(n, big.mark = ","), share = pct(share))
write_tex_fragment(vectors, "../tables/incident_vectors_body.tex")

credential_share <- mean(coded$initial_access == "Valid Accounts")
n_pol_coded <- sum(coded$is_political)

saveRDS(
  list(compare = compare, vectors = vectors,
       credential_share = credential_share,
       coded_coverage = nrow(coded) / nrow(inc),
       n_political_coded = n_pol_coded),
  "../analysis/incident_profile.rds", version = 3
)

cat("political vs other targets\n")
print(as.data.frame(compare))
cat(sprintf(
  "\ninitial access coded for %d of %d incidents (%.0f%%)\n",
  nrow(coded), nrow(inc), 100 * nrow(coded) / nrow(inc)
))
print(as.data.frame(vectors))
cat(sprintf(
  "\nintrusions beginning with stolen credentials: %.1f%%\n", 100 * credential_share
))
cat(sprintf(
  "political incidents with a coded vector: %d -- too few to compare separately\n",
  n_pol_coded
))

## The bound this puts on the whole project, stated where it is computed rather
## than only in the prose.
cat(sprintf(
  "\nUpper bound on incidents a perfect credential-exposure measure could\nanticipate: %.0f%%. The remaining %.0f%% begin with phishing or with the\nexploitation of internet-facing software, neither of which breach-corpus\nappearance predicts.\n",
  100 * credential_share, 100 * (1 - credential_share)
))
