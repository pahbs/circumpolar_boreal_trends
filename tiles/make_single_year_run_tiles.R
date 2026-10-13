# Tile list for the new single-year AGBD runs (model-strategy comparison). Run on ADAPT (local paths below):
#   Rscript make_single_year_run_tiles.R <output dir>
suppressPackageStartupMessages({ library(sf); library(dplyr); library(readr) })
sf_use_s2(FALSE)
set.seed(20261012)
args <- commandArgs(TRUE); OUT <- args[1]

AEA <- st_crs("+proj=aea +lat_0=40 +lon_0=180 +lat_1=50 +lat_2=70 +x_0=0 +y_0=0 +ellps=GRS80 +towgs84=0,0,0,0,0,0,0 +units=m +no_defs")
U <- "/panfs/ccds02/nobackup/people/pmontesa/userfs02"
tiles <- st_read(file.path(U, "projects/above_icesat2/boreal_tiles/boreal_tiles_v004.gpkg"), quiet = TRUE) %>% select(tile_num)
st_crs(tiles) <- AEA
boreal <- st_read(file.path(U, "projects/above_icesat2/wwf_circumboreal_Dissolve.geojson"), quiet = TRUE) %>%
    st_make_valid() %>% st_transform(AEA) %>% st_union()

# Share of each tile inside the WWF boreal forest/taiga biome
inter <- st_intersection(tiles, boreal)
frac <- tibble(tile_num = inter$tile_num, boreal_km2 = as.numeric(st_area(inter)) / 1e6) %>%
    group_by(tile_num) %>% summarise(boreal_km2 = sum(boreal_km2))
cen <- st_coordinates(st_transform(st_centroid(st_geometry(tiles)), 4326))
tiles <- tiles %>%
    mutate(tile_km2 = as.numeric(st_area(geom)) / 1e6, lon = cen[, 1], lat = cen[, 2],
           realm = ifelse(lon > -170 & lon < -30, "North America", "Eurasia")) %>%
    left_join(frac, by = "tile_num") %>%
    mutate(boreal_frac = coalesce(boreal_km2 / tile_km2, 0))

# Field plots (same sources as validation_v3.1_height_agbd.ipynb); extraction GPKGs are in the tile CRS
R <- file.path(U, "data/reference/extracted")
plot_files <- c(NFI = "nfi_plus_20220603_value_ht_H30_2020.gpkg",
                NASA = "eurasia_forest_structure_plots_smrytrees_20240124_value_ht_H30_2020.gpkg",
                Miesner = "Miesner_plots_value_ht_H30_2020.gpkg",
                Kolyma = "KolymaRegion_all_value_ht_L30_2020.gpkg")
plots <- bind_rows(lapply(names(plot_files), function(s) {
    x <- st_read(file.path(R, plot_files[[s]]), quiet = TRUE)
    bb <- st_bbox(x)
    if (max(abs(bb)) <= 360) st_crs(x) <- 4326 else st_crs(x) <- AEA   # geographic or tile CRS
    st_transform(x, AEA) %>% transmute(source = s)
}))
plot_tiles <- st_join(plots, tiles %>% select(tile_num), join = st_intersects, left = FALSE) %>%
    st_drop_geometry() %>% count(tile_num, source) %>%
    group_by(tile_num) %>% summarise(n_plots = sum(n), plot_sources = paste(sort(unique(source)), collapse = "+"))

LAT_BREAKS <- seq(45, 75, by = 5)
N_PER_STRATUM <- 10
EARLIER <- c(1209, 1775, 1822, 1841, 1902, 2832, 3173, 3456, 37522)

cand <- tiles %>% st_drop_geometry() %>%
    mutate(lat_band = cut(lat, LAT_BREAKS, right = FALSE, labels = paste0(head(LAT_BREAKS, -1), "-", LAT_BREAKS[-1], "N"))) %>%
    left_join(plot_tiles, by = "tile_num") %>%
    mutate(n_plots = coalesce(n_plots, 0L))

field <- cand %>% filter(n_plots > 0, boreal_frac >= 0.25) %>% mutate(reason = "field plots")
strat <- cand %>% filter(boreal_frac >= 0.5, !is.na(lat_band), !tile_num %in% field$tile_num) %>%
    group_by(realm, lat_band) %>% slice_sample(n = N_PER_STRATUM) %>% ungroup() %>% mutate(reason = "stratified sample")
earlier <- cand %>% filter(tile_num %in% EARLIER, !tile_num %in% c(field$tile_num, strat$tile_num)) %>% mutate(reason = "earlier examples")

out <- bind_rows(field, strat, earlier) %>%
    transmute(tile_num, reason, realm, lat_band, lat = round(lat, 2), lon = round(lon, 2),
              boreal_frac = round(boreal_frac, 2), n_plots, plot_sources) %>%
    arrange(reason, realm, lat)
write_csv(out, file.path(OUT, "single_year_run_tiles.csv"))
writeLines(as.character(sort(out$tile_num)), file.path(OUT, "single_year_run_tiles.txt"))

cat("plot CRS check: bbox of plots in AEA\n"); print(st_bbox(plots))
cat("\nplots matched to tiles:", sum(plot_tiles$n_plots), "of", nrow(plots), "\n")
cat("tiles with >=50% boreal:", sum(cand$boreal_frac >= 0.5), "of", nrow(cand), "\n\n")
print(out %>% count(reason))
print(out %>% count(realm, lat_band) %>% tidyr::pivot_wider(names_from = realm, values_from = n))
cat("\nEARLIER tiles not in v004:", setdiff(EARLIER, cand$tile_num), "\n")
