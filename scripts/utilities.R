## utilities.R -- R ports of the helpers in utilities.py
##
## The analysis stages are R. Data acquisition (01-06) stays as frozen Python
## notebooks that never run, so utilities.py is still needed to read them, but
## nothing downstream of the frozen inputs depends on Python any more.
##
## These functions must reproduce their Python counterparts exactly, because the
## published numbers were produced by the Python versions. Every deliberate
## quirk is preserved and commented -- including the ones that are bugs. Fixing
## them here would silently move published numbers; they should be fixed
## knowingly, in a separate change, with the effect measured.

suppressPackageStartupMessages({
  library(dplyr)
  library(stringr)
  library(readr)
  library(tidyr)
})

REPO <- normalizePath(file.path(dirname(sys.frame(1)$ofile %||% "."), ".."),
                      mustWork = FALSE)

`%||%` <- function(a, b) if (is.null(a)) b else a


#' Clean (and optionally dedupe) an email column.
#'
#' Port of utilities.py::clean_dedupe_email_column. Order matters -- each step
#' is applied to the output of the previous one.
#'
#' Two quirks are preserved deliberately:
#'
#' 1. `str.lstrip("1.")` in Python strips any leading run of the CHARACTERS
#'    '1' and '.', not the prefix "1.". So "1.aron@x.com" -> "aron@x.com"
#'    (intended) but "2004mp@x.com" -> "004mp@x.com" (not intended). Reproduced
#'    with a character-class regex so the R and Python samples match.
#' 2. The domain filter is an inner join against data/edomain_validation.csv,
#'    which was built from DNS MX lookups. 150 of the 154 domains it rejects
#'    failed on transient Timeout rather than NXDOMAIN, so this drops ~270 real
#'    addresses. It is a frozen input; do not regenerate it.
clean_dedupe_email_column <- function(df, column_name = "email", dedup = TRUE,
                                      edomain_path = NULL) {
  stopifnot(column_name %in% names(df))
  e <- df[[column_name]]

  # 1. basic normalisation
  e <- str_trim(e)
  e <- str_to_lower(e)
  e <- str_replace_all(e, ",", "")
  e <- str_replace_all(e, " ", "")
  df[[column_name]] <- e

  # 2. drop single-character junk, 3. drop NA
  df <- df[!str_detect(replace_na(df[[column_name]], ""), "^[A-Za-z,_-]$"), , drop = FALSE]
  df <- df[!is.na(df[[column_name]]), , drop = FALSE]

  # 4/5. trailing "." then the leading-character strip described above
  df[[column_name]] <- str_replace(df[[column_name]], "\\.+$", "")
  df[[column_name]] <- str_replace(df[[column_name]], "^[1.]+", "")
  df[[column_name]] <- str_replace(df[[column_name]], "^[2.]+", "")

  # 6. RFC-ish shape filter (the same regex the Python uses)
  keep <- str_detect(df[[column_name]],
                     "^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\\.[a-zA-Z0-9-.]+$")
  df <- df[replace_na(keep, FALSE), , drop = FALSE]

  # 7. Python then runs email_validator's normalized form. For ASCII addresses
  # already lowercased above that is a no-op, so there is nothing to do here.
  # Non-ASCII local parts would diverge -- assert none survive rather than
  # silently differ.
  stopifnot(!any(str_detect(df[[column_name]], "[^\\x01-\\x7F]")))

  # 8. valid-domain inner join
  if (is.null(edomain_path)) edomain_path <- "../data/edomain_validation.csv"
  edom <- read_csv(edomain_path, show_col_types = FALSE) %>%
    select(domain, valid_email_domain) %>%
    filter(valid_email_domain) %>%
    distinct(domain, .keep_all = TRUE)

  df$.domain <- str_split_i(df[[column_name]], "@", -1L)
  df <- df %>% semi_join(edom, by = c(".domain" = "domain"))
  df$.domain <- NULL

  # 9. optional dedupe, keeping first
  if (dedup) df <- df[!duplicated(df[[column_name]]), , drop = FALSE]

  as_tibble(df)
}


## Government / institutional domain patterns, ported verbatim from
## utilities.py::get_gov_patterns(). Hand-maintained and visibly country-skewed
## -- this classifier is what makes the paper's "Personal email" category, and
## it has never been validated against a labelled sample.
GOV_PATTERNS <- c(
  "\\.gov$", "\\.gob$", "\\.gouv$", "\\.go\\.", "\\.gc\\.", "\\.fed\\.",
  "\\.mil$", "\\.admin$", "\\.bund$", "\\.fgov$", "\\.regering$",
  "\\.regeringen$", "\\.regjeringen$", "ft\\.dk$", "senato\\.it$",
  "stortinget\\.no$", "prpg-grc\\.sg$", "wp\\.sg$", "\\.nic\\.", "nic\\.in$",
  "nrsr\\.sk$", "tweedekamer\\.nl$", "cdep\\.ro$", "eduskunta\\.fi$",
  "assnat\\.cm$", "riigikogu\\.ee$", "sobranie\\.mk$", "dekamer\\.be$",
  "chd\\.lu$", "lachambre\\.be$", "dna\\.sr$", "inatsisartut\\.gl$",
  "nanoq\\.gl$", "da\\.org\\.za$", "dab\\.org\\.hk$", "liberal\\.org\\.hk$",
  "camera\\.it$", "um\\.dk$", "fm\\.dk$", "skm\\.dk$", "sum\\.dk$", "trm\\.dk$",
  "uim\\.dk$", "jm\\.dk$", "kum\\.dk$", "bm\\.dk$", "uvm\\.dk$", "stm\\.dk$",
  "aeldremin\\.dk$", "fvm\\.dk$", "evm\\.dk$", "efkm\\.dk$", "km\\.dk$",
  "em\\.dk$", "oim\\.dk$", "sm\\.dk$", "ufm\\.dk$", "mfvm\\.dk$", "mssb\\.dk$",
  "dphk\\.org$", "bjpanda\\.org$", "iyc\\.in$", "da-mp\\.org\\.za$",
  "ifp\\.org\\.za$", "fondazionecraxi\\.org$", "libero\\.it$",
  "istruzione\\.it$", "partitodemocratico\\.it$", "ecolo\\.be$", "mfa\\.gr$",
  "pasok\\.gr$", "\\.gov\\.", "\\.org\\.sg$", "\\.mil\\.za$", "udm\\.org\\.za$",
  # institution keywords
  "parliament", "parlament", "parlamento", "parl", "senat", "senado",
  "assembly", "assemblee", "asamblea", "congress", "congreso", "ministry",
  "cabinet", "gov", "government", "bureau"
)


#' Classify an email domain as Official or Commercial.
#'
#' Port of utilities.py::classify_comm_gov_email. Note what this actually does:
#' the default is "Commercial" and only the government patterns are tested. The
#' Python builds a commercial pattern list and never uses it, and the "Other"
#' branch is commented out. So "Personal email" in every table and regression
#' means "did not match the hand-maintained government regex" -- university,
#' party, corporate, ISP and vanity domains all land in it.
classify_comm_gov_email <- function(df, email_col = "email") {
  dom <- str_to_lower(str_split_i(df[[email_col]], "@", 2L))
  gov <- str_detect(replace_na(dom, ""), regex(paste(GOV_PATTERNS, collapse = "|"),
                                               ignore_case = TRUE))
  df$ecategory <- ifelse(gov, "Official", "Commercial")
  df
}


## The 38 data classes treated as "serious". Hand-drawn line; the 21.6% headline
## is entirely a function of this list and no sensitivity analysis is run on it.
## Note ms.tex describes a three-tier scheme (tab:risk-tiers) that does not
## correspond to this flat list -- worth reconciling.
LIST_SERIOUS_DATACLASSES <- c(
  "Audio recordings", "Auth tokens", "Bank account numbers", "Biometric data",
  "Browsing histories", "Chat logs", "Credit card CVV", "Credit cards",
  "Credit status information", "Drinking habits", "Driver's licenses",
  "Drug habits", "Email messages", "Encrypted keys", "Government issued IDs",
  "Health insurance information", "Historical passwords", "HIV statuses",
  "Login histories", "MAC addresses", "Mothers maiden names",
  "Nationalities", "Partial credit card data", "Partial dates of birth",
  "Passport numbers", "Password hints", "Passwords", "Personal health data",
  "Photos", "PINs", "Places of birth", "Private messages",
  "Security questions and answers", "Sexual fetishes", "Sexual orientations",
  "SMS messages", "Social security numbers", "Taxation records"
)


## Addresses that returned nothing from HIBP and are excluded by hand.
##
## The Python list carried a seventh entry, dhanwatichandela498@gmail.com. It is
## NOT absent from HIBP -- it was queried as "Dhanwatichandela498@gmail.com" and
## has 39 rows with 1 hit. It only looked missing because the scraped side of
## the HIBP join was not case-normalised, so it was excluded by hand to paper
## over that. Both sides are normalised now, so it is a real, breached
## politician and stays in. The other six are genuinely absent (0 rows each,
## verified against both HIBP files).
DELINQUENTS <- c(
  "m.chrysomallis@parliament.gr", "r.christidou@parliament.gr", "3@abc.com",
  "3@gmail.com", "_bsec@pap.org.sg", "mariamjaafar@gmail.com"
)


#' Write a LaTeX table fragment: body rows only, no environment or header.
#'
#' Port of utilities.py::pandas_to_tex, which strips the first two and last
#' three lines of to_latex() output so the result can be \input into a float
#' defined in the manuscript.
write_tex_fragment <- function(df, path) {
  if (!str_ends(path, "\\.tex")) path <- paste0(path, ".tex")
  # as.character column-wise, not apply() over rows: apply() coerces the frame
  # to a character matrix via format(), which right-pads numerics to a common
  # width and leaves " 1 & ALB & ...  140 &" in the .tex.
  cols <- lapply(df, function(x) {
    x <- as.character(x)
    ifelse(is.na(x), "", x)
  })
  body <- do.call(paste, c(cols, sep = " & "))
  writeLines(c("\\midrule", paste0(body, " \\\\")), path)
  invisible(path)
}
