## 19_person_key.R -- collapse EveryPolitician to one row per PERSON.
##
## The manuscript previously stated that the data contain no stable person
## identifier linking official and personal addresses, so a within-politician
## comparison is not identified. Only the second half of that is true.
## EveryPolitician ships `id`, a stable person key, for every row, plus a
## Wikidata QID for most people. What is missing is a SECOND ADDRESS: every
## person for whom an address is observed has exactly one, and nobody has both a
## personal-domain and an institutional one.
##
## So the within-politician design is blocked by address coverage, not by
## linkage. This script builds the key that a second address would attach to,
## and reports the coverage that determines whether that collection is worth
## attempting. It reads only a frozen input and touches no network.
##
## Note the file is person x term, not person: 25,087 rows for 16,351 people,
## because someone serving three terms appears three times. Collapsing needs a
## rule for every field, and the rules are stated inline rather than left to
## whichever row happens to sort first.

suppressPackageStartupMessages({
  library(dplyr)
  library(readr)
  library(stringr)
  library(tidyr)
})

source("utilities.R")

dir.create("../analysis", showWarnings = FALSE)
dir.create("../tables", showWarnings = FALSE)

ep <- read_csv(
  "../data/everypol/everypol_combined_legislature_data.csv",
  show_col_types = FALSE, guess_max = 50000
)

stopifnot(all(c("id", "name", "email", "wikidata", "cc3") %in% names(ep)))

## first() after arranging by term is "earliest observed", which is the right
## rule for country and name (they do not change) and for leg_start_year (the
## person entered politics then). last() would silently prefer whichever term
## the file happened to end with.
person <- ep %>%
  arrange(id, leg_start_year) %>%
  group_by(person_id = id) %>%
  summarise(
    name = first(na.omit(name)),
    wikidata = first(na.omit(wikidata)),
    cc3 = first(na.omit(cc3)),
    country = first(na.omit(country)),
    chamber = first(na.omit(chamber)),
    gender = first(na.omit(gender)),
    n_terms = n(),
    first_term_year = suppressWarnings(min(leg_start_year, na.rm = TRUE)),
    last_term_year = suppressWarnings(max(leg_start_year, na.rm = TRUE)),
    # An address is a property of the person, not of the term, and the file
    # repeats it across terms. n_emails is the quantity the design turns on.
    n_emails = n_distinct(na.omit(email)),
    email = first(na.omit(email)),
    .groups = "drop"
  ) %>%
  mutate(across(c(first_term_year, last_term_year), ~ ifelse(is.finite(.x), .x, NA_real_)))

stopifnot(
  !anyDuplicated(person$person_id),
  nrow(person) == n_distinct(ep$id)
)

## Classify the one address we do have, so the gap being measured is explicit:
## which people already hold an institutional address (and therefore need a
## personal one collected) and which hold the reverse.
keyed <- person %>%
  filter(!is.na(email)) %>%
  mutate(email = str_to_lower(email)) %>%
  classify_comm_gov_email() %>%
  select(person_id, ecategory)

person <- left_join(person, keyed, by = "person_id")

write_csv(person, "../data/person_key.csv")

## ---------------------------------------------------------------------------
## Coverage: the numbers that decide whether Stage 1 collection is worth doing.
## ---------------------------------------------------------------------------
n_people <- nrow(person)
with_email <- sum(!is.na(person$email))
multi <- sum(person$n_emails > 1)

coverage <- tibble(
  row = c(
    "People in EveryPolitician",
    "\\quad with a Wikidata identifier",
    "\\quad with at least one address",
    "\\quad with more than one address",
    "\\quad institutional address only",
    "\\quad personal address only"
  ),
  n = c(
    n_people,
    sum(!is.na(person$wikidata)),
    with_email,
    multi,
    sum(person$ecategory == "Official", na.rm = TRUE),
    sum(person$ecategory == "Commercial", na.rm = TRUE)
  )
) %>%
  mutate(
    pct = sprintf("%.1f\\%%", 100 * n / n_people),
    n = format(n, big.mark = ",")
  )

write_tex_fragment(coverage, "../tables/person_key_coverage_body.tex")
saveRDS(person, "../analysis/person_key.rds", version = 3)

cat(sprintf("people: %s | with address: %s | with >1 address: %s\n",
            format(n_people, big.mark = ","),
            format(with_email, big.mark = ","),
            format(multi, big.mark = ",")))
print(as.data.frame(coverage))

## ---------------------------------------------------------------------------
## `id` is NOT a person key -- it is a person-within-legislature key.
##
## The same human serving in two legislatures receives two ids: Alex Salmond
## appears under the Scottish and the UK parliaments, Doris Jakobsen under both
## Greenland and Denmark. The Wikidata QID is what actually identifies the
## human, and 34 QIDs are shared by 68 ids for exactly this reason.
##
## This matters for the design: a second address must be keyed on the QID where
## one exists, or the same person's two addresses would be filed as two people
## and the within-person comparison would silently become between-person.
## ---------------------------------------------------------------------------
qid_dupes <- person %>%
  filter(!is.na(wikidata)) %>%
  count(wikidata) %>%
  filter(n > 1)

paired_qid <- ep %>%
  filter(!is.na(email), !is.na(wikidata)) %>%
  mutate(email = str_to_lower(str_trim(email))) %>%
  group_by(wikidata) %>%
  summarise(n_email = n_distinct(email), .groups = "drop")

cat(sprintf(
  "\nperson keys: %s ids -> %s distinct Wikidata QIDs (%s ids share a QID,\n  i.e. the same human in two legislatures)\n",
  format(n_people, big.mark = ","),
  format(n_distinct(na.omit(person$wikidata)), big.mark = ","),
  format(sum(qid_dupes$n), big.mark = ",")
))
cat(sprintf(
  "keyed on QID: %s people hold an address, of whom %s hold more than one\n",
  format(nrow(paired_qid), big.mark = ","),
  format(sum(paired_qid$n_email > 1), big.mark = ",")
))

## The design is only blocked while this holds. If a future EveryPolitician
## refresh ever yields a second address for anyone, the within-politician
## comparison becomes partially identified and this message should change.
if (sum(paired_qid$n_email > 1) < 30) {
  cat("\nEffectively no politician holds two addresses, so the within-politician\n",
      "comparison cannot be run on this input at any useful sample size.\n",
      "Collecting one additional address per person, keyed on the QID, is what\n",
      "would identify it.\n", sep = "")
}

## Country-level pairing targets: where a collection effort would pay off.
targets <- person %>%
  filter(!is.na(email)) %>%
  count(cc3, ecategory) %>%
  pivot_wider(names_from = ecategory, values_from = n, values_fill = 0) %>%
  arrange(desc(Official + Commercial))
cat("\ntop 10 countries by people with a known address:\n")
print(as.data.frame(head(targets, 10)))
