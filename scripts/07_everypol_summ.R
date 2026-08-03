## 07_everypol_summ.R -- build the email-level analysis file and the summary tables.
##
## R port of 07_everypol_summ.ipynb. The analysis stages are R; 01-06 remain
## frozen Python notebooks that never run. See utilities.R for why the helper
## quirks are preserved rather than fixed.
##
## The Python version silently produced wrong numbers under pandas 3: two EP
## addresses (bholasingh.mp@sansad.nic.in, mos4ud@gmail.com) lost their breach
## hits, moving the main regression coefficient from 0.241 to 0.239. Pinning it
## would have needed three coordinated pins (Python 3.12 + pandas 2.2.3 +
## pyjanitor 0.27.0), because pandas 2.2.3 kills the kernel on Python 3.14.
##
## Input:  data/everypol/everypol_combined_legislature_data.csv   (frozen, 02)
##         data/scraped_pol_combined_legislature_data.csv         (frozen, 05)
##         data/everypol_hibp.csv, data/scraped_pol_hibp.csv      (frozen, 05)
##         data/breaches_01_2025.csv                              (frozen, 04)
##         data/popsize.csv, data/edomain_validation.csv          (frozen)
## Output: data/email_lvl_cov.csv
##         tables/hibp_pooled_emailcoverage_summary.tex
##         tables/pooled_pols_breach_number_summary.tex
##         tables/pooled_pols_seriousbreach_number_summary.tex
##         tables/hibp_pwnpols_datatypes.tex
##         tables/hibp_pwnpols_breach_incidents.tex

suppressPackageStartupMessages({
  library(dplyr); library(tidyr); library(readr); library(stringr); library(purrr)
})
source("utilities.R")

DATA <- "../data"; TABLES <- "../tables"

# ---------------------------------------------------------------- breaches
# 07 read breaches_01_2025_expanded.parquet, a binary intermediate holding the
# CSV with DataClasses expanded into 146 indicator columns. Verified derivable
# from the CSV exactly (0 mismatches across all 857 breaches, row order aside),
# so it is rebuilt here and the parquet drops out of the pipeline.
breaches_raw <- read_csv(file.path(DATA, "breaches_01_2025.csv"), show_col_types = FALSE)

parse_dataclasses <- function(s) {
  s %>% str_remove_all("^\\[|\\]$") %>% str_split(",\\s*") %>%
    map(~ str_remove_all(.x, "^['\"]|['\"]$")) %>% map(~ .x[nzchar(.x)])
}
breaches_raw$.dc <- parse_dataclasses(breaches_raw$DataClasses)
ALL_DATACLASSES <- sort(unique(unlist(breaches_raw$.dc)))

breaches <- breaches_raw %>%
  transmute(
    breach          = Name,
    breachdate      = as.Date(BreachDate),
    addeddate       = as.Date(substr(AddedDate, 1, 10)),
    pwncount        = PwnCount,
    isverified      = IsVerified, isfabricated = IsFabricated,
    issensitive     = IsSensitive, isretired = IsRetired,
    isspamlist      = IsSpamList, ismalware = IsMalware,
    n_dataclasses   = lengths(breaches_raw$.dc),
    yearstopublic   = as.numeric(addeddate - breachdate) / 365.25,
    # a breach is serious if it exposed any of the 38 hand-listed classes
    seriousbreach   = as.integer(map_lgl(breaches_raw$.dc,
                                         ~ any(.x %in% LIST_SERIOUS_DATACLASSES)))
  )
# one indicator column per data class, matching the parquet's layout
dc_ind <- map_dfc(setNames(ALL_DATACLASSES, ALL_DATACLASSES),
                  function(d) as.integer(map_lgl(breaches_raw$.dc, ~ d %in% .x)))
breaches <- bind_cols(breaches, dc_ind)

# ---------------------------------------------------------------- politician emails
popsize <- read_csv(file.path(DATA, "popsize.csv"), show_col_types = FALSE) %>%
  filter(!is.na(cc3)) %>% rename(pop2024 = `2024 [YR2024]`) %>%
  distinct(cc3, .keep_all = TRUE)

ep_emails <- read_csv(file.path(DATA, "everypol/everypol_combined_legislature_data.csv"),
                      show_col_types = FALSE, guess_max = 50000) %>%
  arrange(cc3, leg_start_year, email) %>%
  clean_dedupe_email_column() %>%
  distinct(email, .keep_all = TRUE) %>%
  # Wales and Scotland carry no cc3 of their own
  mutate(cc3 = if_else(cc %in% c("GB-SCT", "GB-WLS"), "GBR", cc3),
         ltype = if_else(cc3 == "NAM" & legislature == "National Assembly",
                         "lower house", ltype),
         ltype = if_else(cc3 == "IND", "lower house", ltype)) %>%
  group_by(cc3) %>% mutate(nemail_cc3 = n_distinct(email)) %>% ungroup()
stopifnot(all(ep_emails$nemail_cc3 >= 30))

scraped_emails <- read_csv(file.path(DATA, "scraped_pol_combined_legislature_data.csv"),
                           show_col_types = FALSE, guess_max = 50000) %>%
  arrange(cc3, email) %>%
  clean_dedupe_email_column() %>%
  distinct(email, .keep_all = TRUE) %>%
  left_join(popsize %>% select(cc3, pop2024), by = "cc3") %>%
  group_by(cc3) %>% mutate(nemail_cc3 = n_distinct(email)) %>% ungroup() %>%
  # every scraped legislature is 2025 except Singapore, which spans 2001-2025
  mutate(leg_start_year = as.integer(if_else(cc3 == "SGP", leg_start_year, 2025)))
stopifnot(all(scraped_emails$nemail_cc3 >= 30))

# ---------------------------------------------------------------- HIBP merge
# Both sides are normalised. The original normalised only the EP side ("needed
# to normalize strings -- do not remove") and left the scraped side raw, which
# is the same defect that cost notebook 10 four percentage points: HIBP
# filenames keep the capitalisation they were scraped in (381 in the EP file,
# 1 in the scraped file), so a raw join scores those addresses as never
# breached. Normalising one side and not the other cannot be right under any
# reading.
ep_hibp <- read_csv(file.path(DATA, "everypol_hibp.csv"), show_col_types = FALSE) %>%
  rename(email = Filename, breach = Breach, present = Present) %>%
  clean_dedupe_email_column(dedup = FALSE)

sc_hibp <- read_csv(file.path(DATA, "scraped_pol_hibp.csv"), show_col_types = FALSE) %>%
  rename(email = Filename, breach = Breach, present = Present) %>%
  clean_dedupe_email_column(dedup = FALSE)

ep_expanded <- ep_emails %>%
  select(email, gender, cc3, country, ltype, legislature, chamber,
         leg_start_year, nemail_cc3) %>%
  left_join(ep_hibp, by = "email", relationship = "one-to-many") %>%
  filter(!is.na(breach)) %>%
  left_join(breaches, by = "breach") %>%
  mutate(source = "ep") %>%
  select(-chamber, -legislature)

sc_expanded <- scraped_emails %>%
  select(email, cc3, country, leg_start_year, nemail_cc3) %>%
  left_join(sc_hibp, by = "email", relationship = "one-to-many") %>%
  mutate(present = replace_na(present, FALSE)) %>%
  left_join(breaches, by = "breach") %>%
  mutate(source = "scraped")

# Deduplicating (email, breach) has to resolve conflicts, not pick arbitrarily.
# Three addresses were queried against HIBP under two spellings each --
# "bholasingh.mp@sansad.nic.in." (trailing dot), "mos4ud@gmail.com," (trailing
# comma) and "1.office@bjpanda.org" -- because the malformed forms were in the
# source data. HIBP returns nothing for the malformed spelling and the real
# hits for the clean one. Normalisation then merges each pair into duplicate
# (email, breach) rows, one TRUE and one FALSE.
#
# The original took `keep="first"` after sorting on (source, email) only, so
# which row survived depended on row order -- unstable across pandas versions
# and across reruns, and it silently zeroed real breaches. Taking the max makes
# it order-independent and is the right semantics: if any spelling of the
# address appears in a breach, that person was breached.
email_breach <- bind_rows(ep_expanded, sc_expanded) %>%
  filter(!is.na(breach)) %>%
  arrange(source, email) %>%
  group_by(email, breach) %>%
  mutate(present = any(present)) %>%
  slice_head(n = 1) %>%
  ungroup() %>%
  filter(!email %in% DELINQUENTS) %>%
  classify_comm_gov_email()

# ---------------------------------------------------------------- analysis file
ep_cov <- read_csv(file.path(DATA, "everypol/everypol_combined_legislature_data.csv"),
                   show_col_types = FALSE, guess_max = 50000) %>%
  filter(!is.na(email)) %>%
  select(email, twitter, facebook, group_id, gender, ltype,
         leg_start_year, leg_start_date, person_count_legistype) %>%
  arrange(email, leg_start_year) %>% select(-leg_start_year) %>%
  clean_dedupe_email_column()

email_lvl_cov <- email_breach %>%
  group_by(email, source, leg_start_year, country, cc3, ecategory) %>%
  summarise(nbreach = sum(present),
            nbreach_serious = sum(present * seriousbreach), .groups = "drop") %>%
  arrange(source, cc3, leg_start_year, email) %>%
  left_join(ep_cov, by = "email")
stopifnot(all(email_lvl_cov$nbreach >= email_lvl_cov$nbreach_serious))

write_csv(email_lvl_cov, file.path(DATA, "email_lvl_cov.csv"))

n_emails <- n_distinct(email_breach$email)
cat(sprintf("emails %d | breaches %d | breached %d | serious %d\n",
            n_emails, n_distinct(email_breach$breach),
            n_distinct(email_breach$email[email_breach$present]),
            n_distinct(email_breach$email[email_breach$present &
                                          email_breach$seriousbreach == 1])))

# ---------------------------------------------------------------- Table 1
# One row per country: emails, the legislature years covered, chamber types,
# legislature names, and 2024 population in millions.
pooled <- bind_rows(
  ep_emails %>% select(email, cc3, country, ltype, legislature, leg_start_year),
  scraped_emails %>% select(email, cc3, country, ltype, legislature, leg_start_year)
) %>% filter(email %in% email_breach$email)

collapse_years <- function(y) {
  y <- sort(unique(y))
  if (length(y) == 1) return(as.character(y))
  # contiguous-ish spans are shown as a range, sparse sets are listed
  if (length(y) > 3) sprintf("%d--%d", min(y), max(y)) else paste(y, collapse = ", ")
}
title_ltype <- function(x) {
  x <- unique(na.omit(x))
  x <- str_replace(x, " house$", ""); x <- str_replace(x, "cameral legislature$", "cameral")
  paste(str_to_title(sort(unique(x))), collapse = ", ")
}

tab1 <- pooled %>%
  group_by(cc3) %>%
  summarise(country = first(na.omit(country)),
            n = n_distinct(email),
            years = collapse_years(leg_start_year),
            chamber = title_ltype(ltype),
            legislature = paste(sort(unique(na.omit(legislature))), collapse = ", "),
            .groups = "drop") %>%
  left_join(popsize %>% select(cc3, pop2024), by = "cc3") %>%
  # popsize.csv uses ".." for territories the World Bank series does not cover
  # (Bermuda, French Polynesia, Greenland, Guernsey, Hong Kong, Jersey)
  mutate(pop_n = suppressWarnings(as.numeric(pop2024)),
         pop = if_else(is.na(pop_n), "---", sprintf("%.1f", pop_n / 1e6)),
         country = str_replace_all(country, "-", " ")) %>%
  arrange(cc3) %>%
  transmute(ix = row_number(), cc3, country, n, years, chamber, legislature, pop)
write_tex_fragment(tab1, file.path(TABLES, "hibp_pooled_emailcoverage_summary"))

# ------------------------------------------------- Tables: breaches per email
# Distribution of breach counts per address, for all / official / personal.
# The Python floored mean and sd to integers for the two subgroup rows but not
# for the "All emails" row, so one table used two rules and reported a mean of
# 0.0 beside "17.2% have at least one". Everything is rounded to 1dp here.
per_email <- function(df) {
  df %>% group_by(email) %>% summarise(k = sum(present), .groups = "drop") %>% pull(k)
}
summary_row <- function(label, k, n_tot) {
  q <- quantile(k, c(.25, .5, .75), names = FALSE)
  tibble(cat = label,
         n = format(n_tot, big.mark = ","),
         mean = sprintf("%.1f", mean(k)), sd = sprintf("%.1f", sd(k)),
         min = as.character(round(min(k))), p25 = as.character(round(q[1])),
         p50 = as.character(round(q[2])), p75 = as.character(round(q[3])),
         max = as.character(round(max(k))),
         ge1 = sprintf("%.1f\\%%", 100 * mean(k >= 1)),
         ge2 = sprintf("%.1f\\%%", 100 * mean(k >= 2)))
}

make_count_table <- function(serious_only, path) {
  d <- if (serious_only) email_breach %>% filter(seriousbreach == 1) else email_breach
  # every address stays in the denominator, including those with no qualifying
  # breach -- restricting to seriousbreach==1 rows would silently drop them
  all_e <- email_breach %>% distinct(email, ecategory)
  k_of <- function(sub) {
    kk <- d %>% filter(email %in% sub$email) %>% per_email()
    c(kk, rep(0, nrow(sub) - length(kk)))
  }
  rows <- bind_rows(
    summary_row("All emails",        k_of(all_e), nrow(all_e)),
    summary_row("Government emails", k_of(all_e %>% filter(ecategory == "Official")),
                sum(all_e$ecategory == "Official")),
    summary_row("Personal emails",   k_of(all_e %>% filter(ecategory == "Commercial")),
                sum(all_e$ecategory == "Commercial"))
  )
  write_tex_fragment(rows, path)
}
make_count_table(FALSE, file.path(TABLES, "pooled_pols_breach_number_summary"))
make_count_table(TRUE,  file.path(TABLES, "pooled_pols_seriousbreach_number_summary"))

# ---------------------------------------------------------------- Table 2
# Data classes exposed, ranked, laid out in three column blocks of 20.
n_pwned <- n_distinct(email_breach$email[email_breach$present])
dt <- email_breach %>% filter(present) %>%
  select(email, all_of(ALL_DATACLASSES)) %>%
  pivot_longer(-email, names_to = "datatype", values_to = "v") %>%
  group_by(email, datatype) %>% summarise(v = max(v), .groups = "drop") %>%
  group_by(datatype) %>% summarise(count = sum(v), .groups = "drop") %>%
  filter(count > 0) %>%
  arrange(desc(count), datatype) %>%
  mutate(ix = row_number(),
         percent = sprintf("%.1f\\%%", 100 * count / n_pwned),
         serious = ifelse(datatype %in% LIST_SERIOUS_DATACLASSES, "\\checkmark", ""))
nblock <- 20
blocks <- map(0:2, function(b) {
  s <- dt[(b * nblock + 1):min((b + 1) * nblock, nrow(dt)), ]
  s <- s %>% select(ix, datatype, count, percent, serious)
  if (nrow(s) < nblock) s <- bind_rows(s, tibble(ix = rep(NA, nblock - nrow(s))))
  setNames(s, paste0(names(s), b))
})
write_tex_fragment(bind_cols(blocks) %>% mutate(across(everything(), ~ replace_na(as.character(.x), ""))),
                   file.path(TABLES, "hibp_pwnpols_datatypes"))

# ---------------------------------------------------------------- Table 3
# The 25 breach incidents hitting the most politician addresses.
tab3 <- email_breach %>% filter(present) %>%
  count(breach, name = "emails") %>%
  arrange(desc(emails), breach) %>% head(25) %>%
  mutate(percent = sprintf("%.1f\\%%", 100 * emails / n_pwned)) %>%
  left_join(breaches_raw %>% transmute(breach = Name, domain = Domain), by = "breach") %>%
  left_join(breaches %>% select(breach, breachdate, addeddate, yearstopublic,
                                pwncount, n_dataclasses, seriousbreach), by = "breach") %>%
  transmute(ix = row_number(), breach, emails, percent,
            domain = replace_na(domain, "---"),
            breachdate = as.character(breachdate), addeddate = as.character(addeddate),
            lag = sprintf("%.1f years", yearstopublic),
            accounts = sprintf("%.1fM", pwncount / 1e6),
            n_dataclasses,
            serious = ifelse(seriousbreach == 1, "\\checkmark", ""))
write_tex_fragment(tab3, file.path(TABLES, "hibp_pwnpols_breach_incidents"))

cat("wrote 5 table fragments\n")
