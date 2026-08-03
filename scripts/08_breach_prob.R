# Load necessary libraries
library(fixest)
library(purrr)
library(tidyverse)
source("theme.R")
source("utilities.R")


# Coefficient labels for etable(). This lived in the interactive session rather
# than the script, so tables/breach_prob.tex could not be regenerated from a
# clean checkout.
#
# Reconstructed from the published table rather than guessed: the committed
# breach_prob.tex renders the three coefficient rows as "Personal email",
# "Female" and "Social media", and the fixed-effect rows as "Country",
# "Decade", "Legislature type" and "Political party". It leaves the dependent
# variables as the raw `dbreach` / `dbreach_serious`, so those are deliberately
# NOT mapped here -- adding them would silently change the column headers of a
# table that is already in the manuscript.
COEF_LABELS <- c(
  "ecategory::Commercial" = "Personal email",
  "gender::female"        = "Female",
  "socials::1"            = "Social media",
  "Country"               = "Country",
  "Decade"                = "Decade",
  "ltype"                 = "Legislature type",
  "group_id"              = "Political party"
)

# fixest >= 0.12 drops singleton fixed-effect groups by default; earlier
# versions kept them. The published table was produced under the old behaviour
# (7,188 obs / 465 parties); the new default gives 7,082 / 359, because 106
# parties contain exactly one email each. Singletons contribute no identifying
# variation, so dropping them is the defensible choice -- but it has to be
# stated rather than inherited from whichever fixest happens to be installed.
setFixest_estimation(fixef.rm = "singleton")


# -------------------------------------------------------------------------
email_data <- read_csv("../data/email_lvl_cov.csv") %>%
  arrange(desc(source == "ep")) %>%
  distinct(email, .keep_all = TRUE) %>%
  rename(Country = cc3) %>%
  mutate(
    dbreach         = if_else(nbreach > 0, 1, 0),
    dbreach_serious = if_else(nbreach_serious > 0, 1, 0),
    Decade           = floor(leg_start_year / 10) * 10,
    socials          = if_else(
      ((!is.na(twitter) & twitter != "") | (!is.na(facebook) & facebook != "")),
      1, 0
    ),
  )


# Estimate ----------------------------------------------------------------
covars_pooled <- "i(ecategory, ref='Official') | Country + Decade"
covars_ep     <- "i(ecategory, ref='Official') + i(gender, ref='Male') + i(socials) | Country + Decade + ltype + group_id"

model_formulas <- list(
  "dbreach_pooled"         = as.formula(paste("dbreach ~", covars_pooled)),
  "dbreach_ep"             = as.formula(paste("dbreach ~", covars_ep)),
  "dbreach_serious_pooled" = as.formula(paste("dbreach_serious ~", covars_pooled)),
  "dbreach_serious_ep"     = as.formula(paste("dbreach_serious ~", covars_ep))
)

models <- imap(model_formulas, ~ feols(.x, data = email_data, vcov = "cluster"))
models


# Wild-cluster inference ---------------------------------------------------
if (!requireNamespace("fwildclusterboot", quietly = TRUE)) {
  stop("Install fwildclusterboot to run the required wild-cluster inference.")
}
if (!requireNamespace("dqrng", quietly = TRUE)) {
  stop("Install dqrng to reproduce fwildclusterboot random draws.")
}

WILD_BOOT_DRAWS <- as.integer(Sys.getenv("WILD_BOOT_DRAWS", "9999"))
WILD_BOOT_SEED <- 20260803L

wild_data <- email_data %>%
  transmute(
    Country = factor(Country),
    Decade = factor(Decade),
    personal = as.integer(ecategory == "Commercial"),
    dbreach,
    dbreach_serious
  )

wild_models <- list(
  breach = lm(dbreach ~ personal + Country + Decade, data = wild_data),
  serious = lm(dbreach_serious ~ personal + Country + Decade, data = wild_data)
)

wild_results <- imap_dfr(wild_models, function(model, outcome) {
  draw_seed <- WILD_BOOT_SEED + match(outcome, names(wild_models))
  set.seed(draw_seed)
  dqrng::dqset.seed(draw_seed)
  test <- fwildclusterboot::boottest(
    model,
    param = "personal",
    clustid = ~Country,
    B = WILD_BOOT_DRAWS,
    bootstrap_type = "11",
    impose_null = TRUE,
    engine = "R"
  )
  tibble(
    outcome = outcome,
    term = "personal",
    estimate = unname(coef(model)[["personal"]]),
    test_statistic = unname(test$t_stat),
    p_value = unname(test$p_val),
    p_value_resolution = 1 / (WILD_BOOT_DRAWS + 1),
    clusters = as.integer(test$N_G[["Country"]]),
    observations = as.integer(test$N),
    draws = as.integer(WILD_BOOT_DRAWS),
    weights = as.character(test$type),
    bootstrap_type = "WCR11",
    null_imposed = isTRUE(test$impose_null),
    seed = as.integer(draw_seed)
  )
})

dir.create("../analysis", showWarnings = FALSE)
saveRDS(wild_results, "../analysis/wild_cluster_inference.rds", version = 3)


# Tabulate ----------------------------------------------------------------
# etable(file=) appends rather than overwrites, so re-running the script used to
# leave several stacked copies of the same table in breach_prob.tex. Clear it
# first so the file always holds exactly one.
if (file.exists("../tables/breach_prob.tex")) file.remove("../tables/breach_prob.tex")

etable(
  models$dbreach_pooled,
  models$dbreach_ep,
  models$dbreach_serious_pooled,
  models$dbreach_serious_ep,
  vcov = "cluster",
  tex = TRUE,
  adjustbox = TRUE,
  placement = "!htbp",
  file = "../tables/breach_prob.tex",
  signif.code = c("***"=.001, "**"=.01, "*"=.05, "+"=.1),
  style.tex = style.tex("aer"),
  dict = COEF_LABELS,          
  fitstat = c("my", "n", "r2"),
  fixef_sizes = TRUE,
  fixef_sizes.simplify = FALSE,
  digits = 3,
  digits.stats = 3,
  se.below = TRUE
)


# Plot fixef ---------------------------------------------------------------
# Extract from stored model
fe_coef_serious = fixef(models$dbreach_serious_pooled)
summary(fe_coef_serious)
do.call(par, pwned_base_par())
plot(fe_coef_serious, n = 5)

pdf("../figures/fixef_plot_model3_dseriousbreach.pdf", width = 15, height = 5)
do.call(par, pwned_base_par())
plot(fe_coef_serious, n = 5)
dev.off()

png("../figures/fixef_plot_model3_dseriousbreach.png", units = "in", width = 15, height = 5, res = 300)
do.call(par, pwned_base_par())
plot(fe_coef_serious, n = 5)
dev.off()

fe_coef = fixef(models$dbreach_pooled)
summary(fe_coef)
do.call(par, pwned_base_par())
plot(fe_coef, n = 5)

pdf("../figures/fixef_plot_model1_dbreach.pdf", width = 15, height = 5)
do.call(par, pwned_base_par())
plot(fe_coef, n = 5)
dev.off()

png("../figures/fixef_plot_model1_dbreach.png", units = "in", width = 15, height = 5, res = 300)
do.call(par, pwned_base_par())
plot(fe_coef, n = 5)
dev.off()


# Tabulate fixef -----------------------------------------------------------
fe_breach  <- fixef(models$dbreach_pooled)$Country
fe_serious <- fixef(models$dbreach_serious_pooled)$Country

df_breach <- tibble(
  Country = names(fe_breach),
  fe_breach = unname(fe_breach)
)

df_serious <- tibble(
  Country = names(fe_serious),
  fe_breach_serious = unname(fe_serious)
)

country_names <- email_data %>%
  filter(!country %in% c("Scotland", "Wales")) %>%
  distinct(Country, country)

country_counts <- email_data %>%
  count(Country, name = "n_email")

df_fes_unrounded <- left_join(df_serious, df_breach, by = "Country") %>%
  left_join(
    country_names,
    by = "Country",
    relationship = "one-to-one"
  ) %>%
  left_join(country_counts, by = "Country", relationship = "one-to-one") %>%
  transmute(
    cc3 = as.character(Country),
    country = as.character(country),
    fe_breach_serious = as.double(fe_breach_serious),
    fe_breach = as.double(fe_breach),
    n_email = as.integer(n_email)
  ) %>%
  arrange(desc(fe_breach_serious))

stopifnot(
  nrow(df_fes_unrounded) == n_distinct(df_fes_unrounded$cc3),
  !anyNA(df_fes_unrounded),
  is.character(df_fes_unrounded$cc3),
  is.character(df_fes_unrounded$country),
  is.double(df_fes_unrounded$fe_breach_serious),
  is.double(df_fes_unrounded$fe_breach),
  is.integer(df_fes_unrounded$n_email)
)

dir.create("../analysis", showWarnings = FALSE)
saveRDS(df_fes_unrounded, "../analysis/country_fixed_effects.rds", version = 3)

df_fes <- df_fes_unrounded %>%
  mutate(
    Index = row_number(),
    fe_breach_serious = round(fe_breach_serious, 3),
    fe_breach = round(fe_breach, 3)
  ) %>%
  select(Index, cc3, country, fe_breach_serious, fe_breach)

write_tex_fragment(df_fes, "../tables/country_fixed_effects_body.tex")
