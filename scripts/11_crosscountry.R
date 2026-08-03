suppressPackageStartupMessages({
  library(dplyr)
  library(fixest)
  library(ggplot2)
  library(purrr)
  library(readr)
  library(relaimpo)
  library(sandwich)
  library(stringr)
  library(tibble)
  library(tidyr)
})

source("theme.R")
source("utilities.R")

SEED <- 20260803L
HIER_BOOT_DRAWS <- as.integer(Sys.getenv("HIER_BOOT_DRAWS", "999"))
SHAPLEY_DRAWS <- as.integer(Sys.getenv("SHAPLEY_DRAWS", "10000"))
COVARIATES <- c("log_gdppc", "egdi", "english", "gci", "vdem")
OUTCOMES <- c(breach = "fe_breach", serious = "fe_breach_serious")

dir.create("../analysis", showWarnings = FALSE)
dir.create("../figures", showWarnings = FALSE)
dir.create("../tables", showWarnings = FALSE)
setFixest_notes(FALSE)

assert_columns <- function(data, expected, object_name) {
  missing <- setdiff(expected, names(data))
  extra <- setdiff(names(data), expected)
  if (length(missing) || length(extra)) {
    stop(
      object_name, " schema mismatch; missing: ", paste(missing, collapse = ", "),
      "; extra: ", paste(extra, collapse = ", ")
    )
  }
}

effects <- readRDS("../analysis/country_fixed_effects.rds")
assert_columns(
  effects,
  c("cc3", "country", "fe_breach_serious", "fe_breach", "n_email"),
  "country_fixed_effects.rds"
)
stopifnot(
  is.character(effects$cc3),
  is.character(effects$country),
  is.double(effects$fe_breach_serious),
  is.double(effects$fe_breach),
  is.integer(effects$n_email),
  nrow(effects) == n_distinct(effects$cc3),
  !anyNA(effects)
)

covariate_schema <- cols_only(
  cc3 = col_character(),
  country = col_character(),
  gdppc = col_double(),
  egdi = col_double(),
  vdem = col_double(),
  gci = col_double(),
  english = col_double(),
  log_gdppc = col_double()
)

covariates <- read_csv(
  "../data/country_fes_covariates.csv",
  col_types = covariate_schema,
  na = c("", "NA")
)
assert_columns(
  covariates,
  c("cc3", "country", "gdppc", "egdi", "vdem", "gci", "english", "log_gdppc"),
  "country_fes_covariates.csv"
)
stopifnot(
  is.character(covariates$cc3),
  is.character(covariates$country),
  is.double(covariates$gdppc),
  is.double(covariates$egdi),
  is.double(covariates$vdem),
  is.double(covariates$gci),
  is.double(covariates$english),
  is.double(covariates$log_gdppc),
  nrow(covariates) == n_distinct(covariates$cc3)
)

if (nrow(anti_join(effects, covariates, by = "cc3")) ||
    nrow(anti_join(covariates, effects, by = "cc3"))) {
  stop("Current country effects and frozen covariates do not have the same country keys.")
}

country_data <- effects %>%
  dplyr::select(-country) %>%
  inner_join(
    covariates,
    by = "cc3",
    relationship = "one-to-one"
  ) %>%
  drop_na(all_of(c(unname(OUTCOMES), COVARIATES))) %>%
  arrange(cc3)

stopifnot(nrow(country_data) == 52L, all(country_data$english %in% c(0, 1)))
saveRDS(country_data, "../analysis/country_predictor_data.rds", version = 3)

model_specs <- list(
  "breach M1" = fe_breach ~ log_gdppc,
  "breach M2" = fe_breach ~ log_gdppc + egdi + english + gci + vdem,
  "serious M1" = fe_breach_serious ~ log_gdppc,
  "serious M2" = fe_breach_serious ~ log_gdppc + egdi + english + gci + vdem
)
models <- map(model_specs, lm, data = country_data)

tidy_hc3 <- function(model, model_name) {
  test <- lmtest::coeftest(model, vcov. = vcovHC(model, type = "HC3"))
  model_n <- as.integer(stats::nobs(model))
  model_r2 <- unname(summary(model)$r.squared)
  model_adj_r2 <- unname(summary(model)$adj.r.squared)
  model_outcome_mean <- mean(model$model[[1]])
  tibble(
    model = model_name,
    term = rownames(test),
    estimate = unname(test[, "Estimate"]),
    std_error_hc3 = unname(test[, "Std. Error"]),
    statistic_hc3 = unname(test[, "t value"]),
    p_value_hc3 = unname(test[, "Pr(>|t|)"]),
    n = model_n,
    r_squared = model_r2,
    adj_r_squared = model_adj_r2,
    outcome_mean = model_outcome_mean
  )
}

hc3_results <- imap_dfr(models, tidy_hc3)

email_schema <- cols_only(
  email = col_character(),
  source = col_character(),
  cc3 = col_character(),
  country = col_character(),
  ecategory = col_character(),
  nbreach = col_double(),
  nbreach_serious = col_double(),
  leg_start_year = col_double()
)

email_data_all <- read_csv(
  "../data/email_lvl_cov.csv",
  col_types = email_schema,
  na = c("", "NA")
) %>%
  arrange(desc(source == "ep")) %>%
  distinct(email, .keep_all = TRUE) %>%
  transmute(
    email,
    Country = cc3,
    dbreach = as.integer(nbreach > 0),
    dbreach_serious = as.integer(nbreach_serious > 0),
    ecategory = factor(ecategory, levels = c("Official", "Commercial")),
    Decade = as.integer(floor(leg_start_year / 10) * 10)
  )

# Reconstruct alternative seriousness indicators from the frozen HIBP catalog.
# This is an analysis handoff: source-data production remains in 06_everypol_summ.R.
parse_dataclasses <- function(x) {
  x %>%
    stringr::str_remove_all("^\\[|\\]$") %>%
    stringr::str_split(",\\s*") %>%
    purrr::map(~ stringr::str_remove_all(.x, "^['\"]|['\"]$") %>% .[nzchar(.)])
}
breach_catalog <- read_csv("../data/breaches_01_2025.csv", show_col_types = FALSE) %>%
  transmute(breach = Name, dataclasses = parse_dataclasses(DataClasses))
password_classes <- c(
  "Passwords", "Historical passwords", "Password hints", "Auth tokens",
  "Login histories", "Security questions and answers", "PINs"
)
tier3_classes <- setdiff(
  LIST_SERIOUS_DATACLASSES,
  password_classes
)
hibp_hits <- bind_rows(
  read_csv("../data/everypol_hibp.csv", show_col_types = FALSE) %>%
    transmute(email = tolower(trimws(Filename)), breach = Breach, present = Present),
  read_csv("../data/scraped_pol_hibp.csv", show_col_types = FALSE) %>%
    transmute(email = tolower(trimws(Filename)), breach = Breach, present = Present)
) %>%
  left_join(breach_catalog, by = "breach") %>%
  mutate(
    serious_narrow = as.integer(present & map_lgl(dataclasses, ~ any(.x %in% tier3_classes))),
    serious_password = as.integer(present & map_lgl(dataclasses, ~ any(.x %in% password_classes)))
  ) %>%
  group_by(email) %>%
  summarise(
    serious_narrow = max(serious_narrow, na.rm = TRUE),
    serious_password = max(serious_password, na.rm = TRUE),
    .groups = "drop"
  )

role_prefixes <- c("info", "office", "contact", "press", "secretariat")
email_data_all <- email_data_all %>%
  left_join(hibp_hits, by = "email") %>%
  mutate(
    serious_narrow = replace_na(serious_narrow, 0L),
    serious_password = replace_na(serious_password, 0L),
    role_account = as.integer(str_extract(email, "^[^@]+") %in% role_prefixes)
  )

email_data <- email_data_all %>% filter(Country %in% country_data$cc3)

sensitivity_summary <- map_dfr(
  c("dbreach_serious", "serious_narrow", "serious_password"),
  function(outcome) {
    email_data_all %>%
      group_by(ecategory) %>%
      summarise(
        outcome = outcome,
        n = n(),
        rate = mean(.data[[outcome]]),
        role_excluded_rate = mean(.data[[outcome]][role_account == 0]),
        .groups = "drop"
      )
  }
)
saveRDS(
  list(
    metadata = list(
      primary = "Tier 2 or Tier 3",
      narrow = "Tier 3 only",
      password = password_classes,
      role_prefixes = role_prefixes
    ),
    estimates = sensitivity_summary
  ),
  "../analysis/serious_sensitivity.rds",
  version = 3
)

sensitivity_body <- sensitivity_summary %>%
  mutate(
    outcome = recode(
      outcome,
      dbreach_serious = "Primary (Tier 2+3)",
      serious_narrow = "Narrow (Tier 3 only)",
      serious_password = "Password-related"
    ),
    cell = sprintf("%.1f\\\\%%", 100 * rate),
    role_cell = sprintf("%.1f\\\\%%", 100 * role_excluded_rate)
  ) %>%
  dplyr::select(outcome, ecategory, n, cell, role_cell) %>%
  tidyr::pivot_wider(names_from = ecategory, values_from = c(n, cell, role_cell)) %>%
  transmute(
    outcome,
    `Official rate (N)` = paste0(cell_Official, " (", n_Official, ")"),
    `Commercial rate (N)` = paste0(cell_Commercial, " (", n_Commercial, ")"),
    `Official, role excluded` = role_cell_Official,
    `Commercial, role excluded` = role_cell_Commercial
  )
write_tex_fragment(sensitivity_body, "../tables/serious_sensitivity_body.tex")

email_groups <- split(email_data, email_data$Country)

hierarchical_draw <- function(draw_id) {
  sampled_cc3 <- sample(country_data$cc3, nrow(country_data), replace = TRUE)
  boot_keys <- tibble(
    cc3 = sampled_cc3,
    CountryBoot = sprintf("%s_%03d", sampled_cc3, seq_along(sampled_cc3))
  ) %>%
    left_join(
      country_data %>% dplyr::select(cc3, all_of(COVARIATES)),
      by = "cc3",
      relationship = "many-to-one"
    )

  boot_emails <- map2_dfr(sampled_cc3, boot_keys$CountryBoot, function(cc3, key) {
    block <- email_groups[[cc3]]
    block[sample.int(nrow(block), nrow(block), replace = TRUE), , drop = FALSE] %>%
      mutate(CountryBoot = key)
  })

  first_stage <- list(
    breach = feols(
      dbreach ~ i(ecategory, ref = "Official") | CountryBoot + Decade,
      data = boot_emails
    ),
    serious = feols(
      dbreach_serious ~ i(ecategory, ref = "Official") | CountryBoot + Decade,
      data = boot_emails
    )
  )

  map2_dfr(names(OUTCOMES), OUTCOMES, function(outcome_name, outcome_var) {
    boot_outcome <- fixef(first_stage[[outcome_name]])$CountryBoot
    second_stage <- boot_keys %>%
      mutate(!!outcome_var := unname(boot_outcome[CountryBoot]))

    specs <- list(
      M1 = reformulate("log_gdppc", response = outcome_var),
      M2 = reformulate(COVARIATES, response = outcome_var)
    )

    imap_dfr(specs, function(spec, spec_name) {
      fit <- lm(spec, data = second_stage)
      tibble(
        draw = as.integer(draw_id),
        model = paste(outcome_name, spec_name),
        term = names(coef(fit)),
        estimate = unname(coef(fit))
      )
    })
  })
}

set.seed(SEED)
hierarchical_reps <- map(seq_len(HIER_BOOT_DRAWS), function(draw_id) {
  tryCatch(
    hierarchical_draw(draw_id),
    error = function(error) {
      warning("Hierarchical bootstrap draw ", draw_id, " failed: ", conditionMessage(error))
      NULL
    }
  )
})

failed_hierarchical_draws <- sum(lengths(hierarchical_reps) == 0L)
if (failed_hierarchical_draws / HIER_BOOT_DRAWS > 0.01) {
  stop("More than 1% of hierarchical bootstrap draws failed.")
}

hierarchical_reps <- bind_rows(hierarchical_reps)
hierarchical_summary <- hierarchical_reps %>%
  group_by(model, term) %>%
  summarise(
    boot_lo = quantile(estimate, 0.025, names = FALSE),
    boot_hi = quantile(estimate, 0.975, names = FALSE),
    boot_p = 2 * min(mean(estimate <= 0), mean(estimate >= 0)),
    successful_draws = n(),
    .groups = "drop"
  )

model_results <- hc3_results %>%
  left_join(hierarchical_summary, by = c("model", "term"))

saveRDS(
  list(
    metadata = list(
      seed = SEED,
      hc_type = "HC3",
      hierarchical_draws_requested = HIER_BOOT_DRAWS,
      hierarchical_draws_failed = failed_hierarchical_draws
    ),
    estimates = model_results,
    hierarchical_replicates = hierarchical_reps
  ),
  "../analysis/country_predictor_models.rds",
  version = 3
)

shapley_results <- imap_dfr(OUTCOMES, function(outcome_var, outcome_name) {
  formula <- reformulate(COVARIATES, response = outcome_var)
  point <- calc.relimp(formula, data = country_data, type = "lmg", rela = FALSE)
  set.seed(SEED + match(outcome_name, names(OUTCOMES)))
  boot_run <- boot.relimp(
    formula,
    data = country_data,
    type = "lmg",
    b = SHAPLEY_DRAWS,
    rank = FALSE,
    diff = FALSE,
    rela = FALSE
  )
  boot_eval <- booteval.relimp(
    boot_run,
    bty = "perc",
    level = 0.95,
    sort = FALSE,
    norank = TRUE,
    nodiff = TRUE,
    typesel = "lmg"
  )
  tibble(
    outcome = outcome_name,
    covariate = names(point$lmg),
    share = unname(point$lmg),
    lo95 = unname(boot_eval@lmg.lower[1, ]),
    hi95 = unname(boot_eval@lmg.upper[1, ]),
    draws = as.integer(SHAPLEY_DRAWS)
  )
})

full_model_p <- hc3_results %>%
  filter(grepl("M2$", model), term != "(Intercept)") %>%
  transmute(
    outcome = sub(" M2$", "", model),
    covariate = term,
    significant = p_value_hc3 < 0.05
  )

shapley_results <- shapley_results %>%
  left_join(full_model_p, by = c("outcome", "covariate"))

saveRDS(
  list(
    metadata = list(seed = SEED, draws = SHAPLEY_DRAWS, method = "LMG/Shapley"),
    estimates = shapley_results
  ),
  "../analysis/country_shapley.rds",
  version = 3
)

covariate_labels <- c(
  log_gdppc = "Log GDP per capita",
  egdi = "e-Government development (EGDI)",
  english = "English official language",
  gci = "Global Cybersecurity Index (GCI)",
  vdem = "Electoral democracy (V-Dem)"
)

shapley_results <- shapley_results %>%
  mutate(
    outcome = recode(outcome, breach = "Any breach", serious = "Serious breach"),
    covariate_label = factor(
      covariate_labels[covariate],
      levels = rev(covariate_labels[shapley_results %>%
        filter(outcome == "serious") %>%
        arrange(share) %>%
        pull(covariate)])
    ),
    inference = if_else(significant, "HC3 p < 0.05", "HC3 p >= 0.05")
  )

shapley_plot <- ggplot(
  shapley_results,
  aes(x = share, y = covariate_label, xmin = lo95, xmax = hi95, fill = inference)
) +
  geom_errorbar(orientation = "y", width = 0.12, color = PWNED_COLORS[["mid"]], linewidth = 0.45) +
  geom_point(shape = 21, size = 2.8, color = PWNED_COLORS[["mid"]], stroke = 0.45) +
  facet_wrap(~outcome, nrow = 1) +
  scale_fill_manual(values = c(
    "HC3 p < 0.05" = PWNED_COLORS[["mid"]],
    "HC3 p >= 0.05" = PWNED_COLORS[["paper"]]
  )) +
  scale_x_continuous(limits = c(0, 0.33), breaks = c(0, 0.1, 0.2, 0.3)) +
  labs(x = expression("Shapley share of " * R^2), y = NULL) +
  theme_pwned_pols() +
  theme(legend.position = "right", panel.spacing.x = unit(1.1, "lines"))

save_pwned_plot(shapley_plot, "../figures/fig_shapley", width = 8.6, height = 3.2)

shapley_value <- function(outcome, covariate) {
  shapley_results %>%
    filter(.data$outcome == .env$outcome, .data$covariate == .env$covariate) %>%
    pull(share)
}

writeLines(
  c(
    sprintf("\\newcommand{\\CrossCountryN}{%d}", nrow(country_data)),
    sprintf("\\newcommand{\\CrossCountryAnyIncomeRSquared}{%.2f}", summary(models[["breach M1"]])$r.squared),
    sprintf("\\newcommand{\\CrossCountrySeriousIncomeRSquared}{%.2f}", summary(models[["serious M1"]])$r.squared),
    sprintf("\\newcommand{\\CrossCountrySeriousFullRSquared}{%.2f}", summary(models[["serious M2"]])$r.squared),
    sprintf("\\newcommand{\\CrossCountrySeriousEnglishShapley}{%.2f}", shapley_value("Serious breach", "english")),
    sprintf("\\newcommand{\\CrossCountrySeriousEgdiShapley}{%.2f}", shapley_value("Serious breach", "egdi")),
    sprintf("\\newcommand{\\CrossCountryShapleyDraws}{%d}", SHAPLEY_DRAWS)
  ),
  "../tables/country_check_values.tex"
)

star <- function(p) {
  case_when(
    p < 0.001 ~ "\\sym{***}",
    p < 0.01 ~ "\\sym{**}",
    p < 0.05 ~ "\\sym{*}",
    p < 0.1 ~ "\\sym{+}",
    TRUE ~ ""
  )
}

table_terms <- c("log_gdppc", "egdi", "english", "gci", "vdem", "(Intercept)")
table_labels <- c(
  log_gdppc = "Log GDP per capita",
  egdi = "Digitization (EGDI)",
  english = "English official language",
  gci = "Global Cybersecurity Index (GCI)",
  vdem = "Electoral democracy (V-Dem)",
  `(Intercept)` = "Constant"
)
model_order <- names(model_specs)

cell_for <- function(term, model, kind) {
  row <- model_results %>% filter(.data$model == .env$model, .data$term == .env$term)
  if (!nrow(row)) return("")
  if (kind == "estimate") return(paste0(sprintf("%.3f", row$estimate), star(row$p_value_hc3)))
  if (kind == "se") return(sprintf("(%.3f)", row$std_error_hc3))
  sprintf("[%.3f, %.3f]", row$boot_lo, row$boot_hi)
}

body_lines <- map_chr(table_terms, function(term) {
  estimate <- paste(c(table_labels[[term]], map_chr(model_order, ~cell_for(term, .x, "estimate"))), collapse = " & ")
  se <- paste(c("", map_chr(model_order, ~cell_for(term, .x, "se"))), collapse = " & ")
  interval <- paste(c("", map_chr(model_order, ~cell_for(term, .x, "interval"))), collapse = " & ")
  paste0(estimate, " \\\\\\n", se, " \\\\\\n", interval, " \\\\")
})

bad_line_break <- paste0(strrep("\\", 3), "n")
good_line_break <- paste0(strrep("\\", 2), "\n")
body_lines <- gsub(bad_line_break, good_line_break, body_lines, fixed = TRUE)
body_lines <- ifelse(
  endsWith(body_lines, strrep("\\", 3)),
  paste0(substr(body_lines, 1, nchar(body_lines) - 3), strrep("\\", 2)),
  body_lines
)

summary_rows <- c(
  paste(c("Dependent variable mean", map_chr(model_order, ~sprintf("%.3f", unique(model_results$outcome_mean[model_results$model == .x])))), collapse = " & "),
  paste(c("Countries", map_chr(model_order, ~as.character(unique(model_results$n[model_results$model == .x])))), collapse = " & "),
  paste(c("R$^2$", map_chr(model_order, ~sprintf("%.3f", unique(model_results$r_squared[model_results$model == .x])))), collapse = " & "),
  paste(c("Adjusted R$^2$", map_chr(model_order, ~sprintf("%.3f", unique(model_results$adj_r_squared[model_results$model == .x])))), collapse = " & ")
)

writeLines(
  c(body_lines, "\\midrule", paste0(summary_rows, " \\\\")),
  "../tables/country_predictors_body.tex"
)

message(
  "Wrote typed cross-country results with ", HIER_BOOT_DRAWS,
  " hierarchical draws and ", SHAPLEY_DRAWS, " Shapley draws."
)
