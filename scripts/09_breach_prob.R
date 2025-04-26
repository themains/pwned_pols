library(fixest)
library(purrr)
library(tidyverse)
library(kableExtra)

print_tex <- function(path) {
  if (file.exists(path)) {
    cat(readLines(path), sep = "\n")
  } else {
    message("File not found: ", path)
  }
}

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


# Tabulate ----------------------------------------------------------------
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
  replace=TRUE,
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
print_tex("../tables/breach_prob.tex")

# Plot fixef ---------------------------------------------------------------
# Extract from stored model
fe_coef_serious = fixef(models$dbreach_serious_pooled)
summary(fe_coef_serious)
par(mar = c(0, 0, 0, 0))
par(oma = c(0, 0, 0, 0))
plot(fe_coef_serious, n = 5)

pdf("../figures/fixef_plot_model3_dseriousbreach.pdf", width = 15, height = 5)
par(mar = c(0, 0, 0, 0))
par(oma = c(0, 0, 0, 0))
plot(fe_coef_serious, n = 5)
dev.off()

png("../figures/fixef_plot_model3_dseriousbreach.png", units = "in", width = 15, height = 5, res = 300)
par(mar = c(0, 0, 0, 0))
par(oma = c(0, 0, 0, 0))
plot(fe_coef_serious, n = 5)
dev.off()

fe_coef = fixef(models$dbreach_pooled)
summary(fe_coef)
par(mar = c(0, 0, 0, 0))
par(oma = c(0, 0, 0, 0))
plot(fe_coef, n = 5)

pdf("../figures/fixef_plot_model1_dbreach.pdf", width = 15, height = 5)
par(mar = c(0, 0, 0, 0))
par(oma = c(0, 0, 0, 0))
plot(fe_coef, n = 5)
dev.off()

png("../figures/fixef_plot_model1_dbreach.png", units = "in", width = 15, height = 5, res = 300)
par(mar = c(0, 0, 0, 0))
par(oma = c(0, 0, 0, 0))
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

df_fes <- left_join(df_serious, df_breach, by = "Country") %>%
  arrange(desc(fe_breach_serious)) %>%
  mutate(
    # Add index column
    Index = row_number(), 
    # Round all numeric columns to 3 decimals
    across(where(is.numeric), ~ round(.x, 3))
  ) %>%
  # Merge back with email_data to retrieve "country" (ensuring uniqueness)
  left_join(
    email_data %>%
      filter(!country %in% c("Scotland", "Wales")) %>%  # Remove Scotland & Wales
      distinct(Country, country) %>%  # Ensure only one row per Country
      select(Country, country),
    by = c("Country" = "Country")
  ) %>%
  # Reorder columns
  select(Index, Country, country, fe_breach_serious, fe_breach)


fes_tex = df_fes %>%
  kable(format = "latex", booktabs = TRUE, caption = "Country Fixed Effects") %>%
  kable_styling(full_width = FALSE)

fes_tex <- gsub("\\\\addlinespace", "\\\\midrule", fes_tex)

cat(fes_tex, file = "../tables/country_fixed_effects.tex")

print_tex("../tables/country_fixed_effects.tex")

