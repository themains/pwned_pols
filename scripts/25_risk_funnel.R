## 25_risk_funnel.R -- bound the quantity the manuscript actually cares about.
##
## The headline "a third of politician addresses appear in a breach" is the
## first link of a chain:
##
##   address in a corpus -> the corpus carries a credential -> that credential
##   still authenticates -> someone tries it -> nothing blocks it -> harm
##
## Only the first two links are observable here, and the audit showed the first
## is mostly data brokers holding a published address, which implies nothing
## about any account the politician holds. This script assembles what can be
## said about the whole chain.
##
## The design is a bracket, not a point estimate, and both ends come from
## measurement rather than assumption:
##
##   CEILING  addresses carrying a credential from a service the politician
##            plausibly used. No breach-attributable takeover can exceed this,
##            because the rest of the exposure carries no credential at all.
##
##   FLOOR    addresses appearing in malware-derived stealer corpora. This is
##            not a probability of compromise -- it is evidence of a realised
##            one, because malware ran on the device. It is a lower bound twice
##            over: HIBP holds only publicly dumped stealer corpora, and only
##            those loaded into the breach dataset.
##
## Between them sit three unobservables. Their ranges live in
## ../data/risk_parameters.csv, one reviewable row per link with its rationale
## and source, so an assumption can be argued with by editing a data file rather
## than by reading code. Changing a row moves the published interval.
##
## What matters in the output is not the interval but WHICH LINK ITS WIDTH COMES
## FROM. That is the statement about what the field should measure next.

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

## Data classes that constitute a credential. Password hints and security
## answers are included because they enable recovery-flow takeover, which is a
## credential compromise in every sense that matters operationally.
CREDENTIAL_CLASSES <- c(
  "Passwords", "Historical passwords", "Password hints", "Auth tokens",
  "Security questions and answers"
)

taxonomy <- readRDS("../analysis/breach_taxonomy.rds")
params <- read_csv("../data/risk_parameters.csv", show_col_types = FALSE)
stopifnot(
  all(c("link", "low", "high") %in% names(params)),
  all(params$low <= params$high),
  all(params$low >= 0), all(params$high <= 1)
)

breaches <- read_csv("../data/breaches_01_2025.csv", show_col_types = FALSE) %>%
  mutate(
    classes = str_split(str_remove_all(DataClasses, "^\\[|\\]$|'"), ",\\s*"),
    has_credential = map_lgl(classes, ~ any(str_trim(.x) %in% CREDENTIAL_CLASSES)),
    breach_year = as.integer(format(as.Date(BreachDate), "%Y"))
  ) %>%
  select(name = Name, has_credential, breach_year)

catalogue <- taxonomy %>%
  select(name, tax_class, is_stealer) %>%
  left_join(breaches, by = "name")

addresses <- read_csv("../data/email_lvl_cov.csv", show_col_types = FALSE) %>%
  dedupe_email_level()
N <- nrow(addresses)

read_hibp <- function(path) {
  read_csv(path, show_col_types = FALSE) %>%
    rename(email = Filename, breach = Breach, present = Present) %>%
    clean_dedupe_email_column(dedup = FALSE)
}

hits <- bind_rows(
  read_hibp("../data/everypol_hibp.csv"),
  read_hibp("../data/scraped_pol_hibp.csv")
) %>%
  filter(present, email %in% addresses$email) %>%
  distinct(email, breach) %>%
  left_join(catalogue, by = c("breach" = "name"))

stopifnot(!any(is.na(hits$tax_class)))

share <- function(mask) n_distinct(hits$email[mask]) / N

## ---------------------------------------------------------------------------
## The observable rungs.
## ---------------------------------------------------------------------------
ceiling_share <- share(hits$tax_class == "service" & hits$has_credential)
floor_share <- share(hits$is_stealer)

stealer_years <- range(hits$breach_year[hits$is_stealer], na.rm = TRUE)
window <- diff(stealer_years) + 1
floor_annual <- floor_share / window

observed <- tibble(
  row = c(
    "Any breach appearance",
    "\\quad first-party service compromise",
    "\\quad\\quad \\textbf{carrying a credential} (ceiling)",
    "\\quad credential, any provenance",
    "\\quad\\quad \\textbf{malware-derived capture} (floor)"
  ),
  pct = sprintf("%.2f\\%%", 100 * c(
    share(!is.na(hits$tax_class)),
    share(hits$tax_class == "service"),
    ceiling_share,
    share(hits$has_credential),
    floor_share
  ))
)
write_tex_fragment(observed, "../tables/risk_funnel_observed_body.tex")

## ---------------------------------------------------------------------------
## The bracket.
##
## Multiplied through the three unobservable links. The product of the low ends
## and the product of the high ends are NOT a confidence interval -- they are the
## range consistent with the parameter file, which is a different and weaker
## claim, and the manuscript must say so.
## ---------------------------------------------------------------------------
p <- setNames(params$low, params$link)
q <- setNames(params$high, params$link)

cum_low <- ceiling_share * p[["p_valid"]] * p[["p_attempted"]] * p[["p_no_second_factor"]]
cum_high <- ceiling_share * q[["p_valid"]] * q[["p_attempted"]] * q[["p_no_second_factor"]]

## Which link dominates the width? Hold all others at their midpoint and vary
## one across its range; the resulting spread is that link's contribution.
mid <- (p + q) / 2
contribution <- map_dbl(params$link, function(l) {
  lo <- mid; hi <- mid
  lo[[l]] <- p[[l]]; hi[[l]] <- q[[l]]
  ceiling_share * (prod(hi) - prod(lo))
})
names(contribution) <- params$link

width <- tibble(
  link = params$link,
  range = sprintf("%.2f--%.2f", params$low, params$high),
  spread = sprintf("%.2f pp", 100 * contribution),
  share_of_width = sprintf("%.0f\\%%", 100 * contribution / sum(contribution))
) %>%
  arrange(desc(contribution))
write_tex_fragment(width, "../tables/risk_funnel_width_body.tex")

saveRDS(
  list(ceiling = ceiling_share, floor = floor_share, floor_annual = floor_annual,
       window = window, cum_low = cum_low, cum_high = cum_high,
       contribution = contribution, params = params),
  "../analysis/risk_funnel.rds", version = 3
)

cat("observable rungs (n = ", format(N, big.mark = ","), ")\n", sep = "")
print(as.data.frame(observed))
cat(sprintf(
  "\nCEILING (credential from a used service): %.2f%%\nFLOOR   (malware-derived, observed)     : %.2f%% over %d years = %.3f%%/yr\n",
  100 * ceiling_share, 100 * floor_share, window, 100 * floor_annual
))
cat(sprintf(
  "\nmodelled cumulative takeover range: %.2f%% -- %.2f%%\n",
  100 * cum_low, 100 * cum_high
))

## The coherence check that makes the exercise worth doing: an independently
## measured floor should fall inside a range built from unrelated literature. If
## it does not, either the parameters or the floor is wrong, and saying which is
## the interesting part.
inside <- floor_share >= cum_low && floor_share <= cum_high
cat(sprintf(
  "observed floor inside the modelled range: %s\n",
  if (inside) "YES -- the two independent approaches agree" else
    "NO -- parameters and observation disagree; investigate before reporting"
))

cat("\nwidth of the range, by link:\n")
print(as.data.frame(width))
