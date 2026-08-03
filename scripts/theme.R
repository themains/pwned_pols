suppressPackageStartupMessages(library(ggplot2))

PWNED_COLORS <- c(
  ink = "#252525",
  mid = "#777777",
  light = "#D9D9D9",
  grid = "#E8E8E8",
  paper = "#FFFFFF"
)

theme_pwned_pols <- function(base_size = 10, base_family = "sans") {
  theme_minimal(base_size = base_size, base_family = base_family) +
    theme(
      plot.title.position = "plot",
      plot.title = element_text(face = "bold", margin = margin(b = 6)),
      axis.title = element_text(color = PWNED_COLORS[["ink"]]),
      axis.text = element_text(color = PWNED_COLORS[["ink"]]),
      panel.grid.minor = element_blank(),
      panel.grid.major.y = element_blank(),
      panel.grid.major.x = element_line(
        color = PWNED_COLORS[["grid"]], linewidth = 0.35
      ),
      legend.position = "bottom",
      legend.title = element_blank(),
      plot.background = element_rect(
        fill = PWNED_COLORS[["paper"]], color = NA
      ),
      panel.background = element_rect(
        fill = PWNED_COLORS[["paper"]], color = NA
      )
    )
}

pwned_base_par <- function() {
  list(
    family = "sans",
    fg = PWNED_COLORS[["ink"]],
    col.axis = PWNED_COLORS[["ink"]],
    col.lab = PWNED_COLORS[["ink"]],
    bty = "l",
    las = 1,
    tcl = -0.2,
    mgp = c(2.1, 0.55, 0),
    mar = c(3, 3, 1, 0.5),
    oma = c(0, 0, 0, 0)
  )
}

save_pwned_plot <- function(plot, stem, width, height, dpi = 300) {
  ggsave(paste0(stem, ".pdf"), plot, width = width, height = height,
         device = grDevices::pdf, bg = PWNED_COLORS[["paper"]])
  ggsave(paste0(stem, ".png"), plot, width = width, height = height,
         dpi = dpi, bg = PWNED_COLORS[["paper"]])
  invisible(stem)
}
