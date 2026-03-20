#!/usr/bin/env python3
"""Download historical weather data for fire detection ML features.

Downloads daily weather from SILO (Bureau of Meteorology interpolated grids)
and optionally hourly reanalysis from ERA5 (Copernicus) for NSW Australia,
covering the Himawari calibration period (Nov 26, 2025 – Mar 19, 2026).

Data sources:
    SILO DataDrill API — daily gridded climate data at 0.05° (~5km) resolution.
        Free, no registration. Variables: temperature, rainfall, humidity,
        radiation, vapour pressure, MSLP. NO WIND DATA.
        https://www.longpaddock.qld.gov.au/silo/

    SILO S3 NetCDF — same data as annual NetCDF grids covering all of Australia.
        ~400MB per variable per year. Good for spatial ML features.
        s3://silo-open-data/Official/annual/{variable}/{year}.{variable}.nc

    ERA5 (optional) — hourly reanalysis at 0.25° (~30km). Has wind.
        Requires cdsapi package and CDS API key.
        https://cds.climate.copernicus.eu/

Usage:
    # Download SILO daily data for all calibration targets
    python scripts/download_weather.py --mode targets

    # Download SILO daily data for a grid covering NSW (0.5° spacing)
    python scripts/download_weather.py --mode grid --spacing 0.5

    # Download SILO annual NetCDF files (gridded, ~400MB each)
    python scripts/download_weather.py --mode netcdf

    # Download ERA5 hourly data for NSW (requires cdsapi + CDS key)
    python scripts/download_weather.py --mode era5

    # Quick test — one point, 3 days
    python scripts/download_weather.py --mode targets --test
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import urlencode

import numpy as np
import pandas as pd
import requests

# ---------------------------------------------------------------------------
# Project setup
# ---------------------------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Calibration period
DEFAULT_START = "20251126"
DEFAULT_END = "20260319"

# NSW bounding box (generous, covers all calibration targets)
NSW_BBOX = {
    "south": -38.0,
    "north": -28.0,
    "west": 141.0,
    "east": 154.0,
}

# Output directory
WEATHER_DIR = PROJECT_ROOT / "data" / "weather"

# SILO API
SILO_DATADRILL_URL = "https://www.longpaddock.qld.gov.au/cgi-bin/silo/DataDrillDataset.php"
SILO_S3_BASE = "https://s3-ap-southeast-2.amazonaws.com/silo-open-data/Official/annual"
SILO_USERNAME = "alexander.shenkin@nau.edu"  # Email, used as API username
SILO_PASSWORD = "apirequest"  # Fixed password for DataDrill API

# SILO variable codes for JSON API (empirically verified):
#   R=daily_rain, X=max_temp, N=min_temp, V=vp, D=vp_deficit,
#   H=rh_tmax, G=rh_tmin, J=radiation, M=mslp,
#   E=evap_pan, F=et_short_crop, S=evap_syn,
#   L=evap_morton_lake, P=et_morton_potential, A=et_morton_actual,
#   T=et_tall_crop, W=et_morton_wet, C=evap_comb
#   Z=ALL variables
SILO_VARIABLE_CODES = "RXNVDHGJME"

# Variables we care about for fire detection ML
SILO_VARIABLES_OF_INTEREST = [
    "max_temp",       # Daily max temperature (°C) — affects BTD baseline
    "min_temp",       # Daily min temperature (°C) — night BTD baseline
    "daily_rain",     # Rainfall (mm) — wet ground changes thermal properties
    "vp",             # Vapour pressure (hPa) — atmospheric moisture
    "vp_deficit",     # Vapour pressure deficit (hPa) — dryness indicator
    "rh_tmax",        # Relative humidity at Tmax (%) — atmosphere absorption
    "rh_tmin",        # Relative humidity at Tmin (%)
    "radiation",      # Solar radiation (MJ/m²) — surface heating
    "mslp",           # Mean sea level pressure (hPa) — synoptic conditions
    "evap_pan",       # Pan evaporation (mm) — drying/fire weather proxy
]

# SILO S3 NetCDF variable names (for gridded download)
SILO_NETCDF_VARS = [
    "max_temp",
    "min_temp",
    "daily_rain",
    "vp",
    "vp_deficit",
    "rh_tmax",
    "rh_tmin",
    "radiation",
    "mslp",
]

# ---------------------------------------------------------------------------
# Load calibration targets
# ---------------------------------------------------------------------------


def load_calibration_targets() -> list[dict]:
    """Load calibration target locations from the sample_targets.json file."""
    json_path = PROJECT_ROOT / "data" / "calibration" / "sample_targets.json"
    if not json_path.exists():
        log.warning("No sample_targets.json found at %s", json_path)
        # Fallback: representative NSW locations
        return [
            {"label": "central_nsw", "lat": -33.5, "lon": 148.0},
            {"label": "north_nsw", "lat": -30.0, "lon": 152.0},
            {"label": "south_nsw", "lat": -36.0, "lon": 149.0},
            {"label": "west_nsw", "lat": -32.0, "lon": 145.0},
        ]

    with open(json_path) as f:
        raw = json.load(f)

    targets = []
    seen_coords = set()
    for t in raw:
        # Round to SILO grid (0.05°) to avoid duplicate requests
        lat = round(t["lat"] * 20) / 20  # Snap to 0.05°
        lon = round(t["lon"] * 20) / 20
        coord_key = (lat, lon)
        if coord_key in seen_coords:
            continue
        seen_coords.add(coord_key)
        targets.append({
            "label": t["label"],
            "lat": lat,
            "lon": lon,
        })

    log.info("Loaded %d unique grid points from %d calibration targets", len(targets), len(raw))
    return targets


def generate_nsw_grid(spacing: float = 0.5) -> list[dict]:
    """Generate a regular grid of points covering NSW."""
    points = []
    lat = NSW_BBOX["south"]
    while lat <= NSW_BBOX["north"]:
        lon = NSW_BBOX["west"]
        while lon <= NSW_BBOX["east"]:
            points.append({
                "label": f"grid_{lat:.2f}_{lon:.2f}",
                "lat": round(lat, 2),
                "lon": round(lon, 2),
            })
            lon += spacing
        lat += spacing
    log.info("Generated %d grid points (%.1f° spacing)", len(points), spacing)
    return points


# ---------------------------------------------------------------------------
# SILO DataDrill — point-based daily data
# ---------------------------------------------------------------------------


def fetch_silo_point(
    lat: float, lon: float,
    start: str, end: str,
    variable_codes: str = SILO_VARIABLE_CODES,
) -> pd.DataFrame | None:
    """Fetch SILO daily data for a single lat/lon point via DataDrill API.

    Args:
        lat: Latitude (negative for south).
        lon: Longitude.
        start: Start date as YYYYMMDD.
        end: End date as YYYYMMDD.
        variable_codes: Single-character SILO variable codes.

    Returns:
        DataFrame with date index and weather variables, or None on failure.
    """
    params = {
        "lat": f"{lat:.2f}",
        "lon": f"{lon:.2f}",
        "start": start,
        "finish": end,
        "format": "json",
        "comment": variable_codes,
        "username": SILO_USERNAME,
        "password": SILO_PASSWORD,
    }

    url = f"{SILO_DATADRILL_URL}?{urlencode(params)}"

    try:
        resp = requests.get(url, timeout=60)
        resp.raise_for_status()
        data = resp.json()
    except requests.RequestException as e:
        log.error("SILO request failed for (%.2f, %.2f): %s", lat, lon, e)
        return None
    except json.JSONDecodeError as e:
        log.error("SILO returned invalid JSON for (%.2f, %.2f): %s", lat, lon, e)
        return None

    if "data" not in data:
        log.error("SILO response missing 'data' key for (%.2f, %.2f)", lat, lon)
        return None

    # Parse JSON response into DataFrame
    rows = []
    for day_entry in data["data"]:
        row = {"date": day_entry["date"]}
        for var in day_entry.get("variables", []):
            code = var["variable_code"]
            row[code] = var["value"]
            row[f"{code}_source"] = var["source"]
        rows.append(row)

    if not rows:
        return None

    df = pd.DataFrame(rows)
    df["date"] = pd.to_datetime(df["date"])
    df["lat"] = lat
    df["lon"] = lon

    # Add elevation from metadata
    df["elevation_m"] = data.get("location", {}).get("elevation", np.nan)

    return df


def download_silo_targets(
    targets: list[dict],
    start: str = DEFAULT_START,
    end: str = DEFAULT_END,
    output_dir: Path | None = None,
    delay_between_requests: float = 0.5,
) -> Path:
    """Download SILO daily data for a list of target points.

    Args:
        targets: List of dicts with 'label', 'lat', 'lon'.
        start: Start date YYYYMMDD.
        end: End date YYYYMMDD.
        output_dir: Where to save output CSV.
        delay_between_requests: Seconds between API calls (be polite).

    Returns:
        Path to the combined output CSV.
    """
    if output_dir is None:
        output_dir = WEATHER_DIR / "silo"
    output_dir.mkdir(parents=True, exist_ok=True)

    output_csv = output_dir / "silo_daily_weather.csv"

    # Load existing data to support resumption
    existing_coords: set[tuple[float, float]] = set()
    all_dfs: list[pd.DataFrame] = []
    if output_csv.exists():
        existing_df = pd.read_csv(output_csv)
        existing_df["date"] = pd.to_datetime(existing_df["date"])
        all_dfs.append(existing_df)
        for _, row in existing_df.drop_duplicates(subset=["lat", "lon"]).iterrows():
            existing_coords.add((row["lat"], row["lon"]))
        log.info("Loaded %d existing records from %s (%d locations)",
                 len(existing_df), output_csv, len(existing_coords))

    # Filter targets to only those not yet downloaded
    targets_to_fetch = [
        t for t in targets
        if (t["lat"], t["lon"]) not in existing_coords
    ]

    if not targets_to_fetch:
        log.info("All %d target locations already downloaded", len(targets))
        return output_csv

    log.info("Downloading SILO data for %d locations (%d already done)",
             len(targets_to_fetch), len(existing_coords))
    log.info("Date range: %s to %s", start, end)

    t_start = time.monotonic()
    success_count = 0
    fail_count = 0

    for i, target in enumerate(targets_to_fetch):
        lat, lon = target["lat"], target["lon"]
        label = target["label"]

        df = fetch_silo_point(lat, lon, start, end)

        if df is not None and not df.empty:
            df["target_label"] = label
            all_dfs.append(df)
            success_count += 1
        else:
            fail_count += 1
            log.warning("Failed to fetch data for %s (%.2f, %.2f)", label, lat, lon)

        # Progress
        done = i + 1
        elapsed = time.monotonic() - t_start
        rate = done / elapsed if elapsed > 0 else 0
        remaining = (len(targets_to_fetch) - done) / rate if rate > 0 else 0

        if done % 5 == 0 or done == len(targets_to_fetch):
            log.info(
                "  [%d/%d] %s | ok=%d fail=%d | %.1f req/min | ETA %.0fs",
                done, len(targets_to_fetch), label,
                success_count, fail_count,
                rate * 60, remaining,
            )

        # Polite delay between requests
        if i < len(targets_to_fetch) - 1:
            time.sleep(delay_between_requests)

    # Combine and save
    if all_dfs:
        combined = pd.concat(all_dfs, ignore_index=True)
        combined = combined.drop_duplicates(subset=["date", "lat", "lon"], keep="last")
        combined = combined.sort_values(["lat", "lon", "date"]).reset_index(drop=True)
        combined.to_csv(output_csv, index=False)
        log.info("Saved %d records to %s", len(combined), output_csv)
    else:
        log.warning("No data downloaded")

    elapsed = time.monotonic() - t_start
    log.info("Done: %d ok, %d failed in %.1f min", success_count, fail_count, elapsed / 60)

    return output_csv


# ---------------------------------------------------------------------------
# SILO S3 NetCDF — gridded annual files
# ---------------------------------------------------------------------------


def download_silo_netcdf(
    variables: list[str] | None = None,
    years: list[int] | None = None,
    output_dir: Path | None = None,
) -> list[Path]:
    """Download SILO annual NetCDF files from S3.

    Each file is ~400MB and covers all of Australia at 0.05° resolution.
    Files contain daily grids for the entire year.

    Args:
        variables: List of SILO variable names to download.
        years: List of years. Default: [2025, 2026] for calibration period.
        output_dir: Download directory.

    Returns:
        List of downloaded file paths.
    """
    if variables is None:
        variables = SILO_NETCDF_VARS
    if years is None:
        years = [2025, 2026]
    if output_dir is None:
        output_dir = WEATHER_DIR / "silo_netcdf"
    output_dir.mkdir(parents=True, exist_ok=True)

    downloaded = []
    total = len(variables) * len(years)
    done = 0

    for var in variables:
        for year in years:
            done += 1
            filename = f"{year}.{var}.nc"
            local_path = output_dir / filename
            url = f"{SILO_S3_BASE}/{var}/{filename}"

            if local_path.exists() and local_path.stat().st_size > 1_000_000:
                log.info("[%d/%d] Already exists: %s (%.0f MB)",
                         done, total, filename, local_path.stat().st_size / 1e6)
                downloaded.append(local_path)
                continue

            log.info("[%d/%d] Downloading %s (~400 MB)...", done, total, filename)
            try:
                t0 = time.monotonic()
                resp = requests.get(url, stream=True, timeout=600)
                resp.raise_for_status()

                with open(local_path, "wb") as f:
                    total_bytes = 0
                    for chunk in resp.iter_content(chunk_size=8 * 1024 * 1024):
                        f.write(chunk)
                        total_bytes += len(chunk)

                elapsed = time.monotonic() - t0
                speed = total_bytes / elapsed / 1e6
                log.info("  Downloaded %.0f MB in %.0fs (%.1f MB/s)",
                         total_bytes / 1e6, elapsed, speed)
                downloaded.append(local_path)

            except requests.RequestException as e:
                log.error("  Failed to download %s: %s", filename, e)
                if local_path.exists():
                    local_path.unlink()

    log.info("Downloaded %d/%d NetCDF files to %s", len(downloaded), total, output_dir)
    return downloaded


# ---------------------------------------------------------------------------
# ERA5 — hourly reanalysis (optional, requires cdsapi)
# ---------------------------------------------------------------------------


def download_era5(
    start: str = DEFAULT_START,
    end: str = DEFAULT_END,
    output_dir: Path | None = None,
) -> Path | None:
    """Download ERA5 hourly reanalysis data for NSW.

    Requires:
        - pip install cdsapi
        - ~/.cdsapirc configured with CDS API key
        - Accept ERA5 terms at https://cds.climate.copernicus.eu/

    Downloads 2m temperature, 2m dewpoint, 10m u/v wind, total precipitation,
    surface pressure, and surface solar radiation.

    Args:
        start: Start date YYYYMMDD.
        end: End date YYYYMMDD.
        output_dir: Download directory.

    Returns:
        Path to downloaded NetCDF file, or None on failure.
    """
    try:
        import cdsapi
    except ImportError:
        log.error(
            "cdsapi not installed. Install with: pip install cdsapi\n"
            "Then configure ~/.cdsapirc with your CDS API key.\n"
            "See: https://cds.climate.copernicus.eu/how-to-api"
        )
        return None

    if output_dir is None:
        output_dir = WEATHER_DIR / "era5"
    output_dir.mkdir(parents=True, exist_ok=True)

    start_dt = datetime.strptime(start, "%Y%m%d")
    end_dt = datetime.strptime(end, "%Y%m%d")

    # ERA5 variables relevant for fire detection
    variables = [
        "2m_temperature",
        "2m_dewpoint_temperature",
        "10m_u_component_of_wind",
        "10m_v_component_of_wind",
        "total_precipitation",
        "surface_pressure",
        "surface_solar_radiation_downwards",
        "skin_temperature",  # Land surface temperature proxy
    ]

    # Download month by month to keep request sizes manageable
    downloaded_files = []
    current = start_dt.replace(day=1)

    while current <= end_dt:
        year = current.strftime("%Y")
        month = current.strftime("%m")

        # Determine day range for this month
        month_start = max(current, start_dt)
        next_month = (current.replace(day=28) + timedelta(days=4)).replace(day=1)
        month_end = min(next_month - timedelta(days=1), end_dt)

        days = [
            (month_start + timedelta(days=d)).strftime("%d")
            for d in range((month_end - month_start).days + 1)
        ]

        filename = f"era5_nsw_{year}{month}.nc"
        local_path = output_dir / filename

        if local_path.exists() and local_path.stat().st_size > 100_000:
            log.info("Already exists: %s (%.0f MB)", filename, local_path.stat().st_size / 1e6)
            downloaded_files.append(local_path)
            current = next_month
            continue

        log.info("Requesting ERA5 for %s-%s (days %s-%s)...",
                 year, month, days[0], days[-1])

        try:
            client = cdsapi.Client()
            client.retrieve(
                "reanalysis-era5-single-levels",
                {
                    "product_type": ["reanalysis"],
                    "variable": variables,
                    "year": [year],
                    "month": [month],
                    "day": days,
                    "time": [f"{h:02d}:00" for h in range(24)],
                    "data_format": "netcdf",
                    "area": [
                        NSW_BBOX["north"],
                        NSW_BBOX["west"],
                        NSW_BBOX["south"],
                        NSW_BBOX["east"],
                    ],
                },
                str(local_path),
            )
            log.info("  Downloaded: %s (%.0f MB)",
                     filename, local_path.stat().st_size / 1e6)
            downloaded_files.append(local_path)

        except Exception as e:
            log.error("  ERA5 request failed for %s-%s: %s", year, month, e)
            if local_path.exists():
                local_path.unlink()

        current = next_month

    if downloaded_files:
        log.info("ERA5 download complete: %d files in %s", len(downloaded_files), output_dir)
        return output_dir
    return None


# ---------------------------------------------------------------------------
# Analysis / summary helpers
# ---------------------------------------------------------------------------


def summarize_weather_data(csv_path: Path) -> None:
    """Print a summary of the downloaded SILO weather data."""
    if not csv_path.exists():
        log.warning("No data file at %s", csv_path)
        return

    df = pd.read_csv(csv_path)
    df["date"] = pd.to_datetime(df["date"])

    print(f"\n{'='*70}")
    print("SILO WEATHER DATA SUMMARY")
    print(f"{'='*70}")
    print(f"File: {csv_path}")
    print(f"Records: {len(df)}")
    print(f"Locations: {df.groupby(['lat','lon']).ngroups}")
    print(f"Date range: {df['date'].min().date()} to {df['date'].max().date()}")
    print(f"Days: {df['date'].nunique()}")

    # Variable statistics
    print(f"\n{'Variable':<20} {'Mean':>8} {'Std':>8} {'Min':>8} {'Max':>8} {'Missing':>8}")
    print("-" * 70)
    for var in SILO_VARIABLES_OF_INTEREST:
        if var in df.columns:
            col = df[var]
            missing = col.isna().sum()
            print(f"{var:<20} {col.mean():8.1f} {col.std():8.1f} "
                  f"{col.min():8.1f} {col.max():8.1f} {missing:8d}")

    # Data source quality
    print(f"\n{'Source codes (25=interpolated station, 26=derived, 42=satellite, 75=long-term avg)':}")
    for var in ["max_temp", "daily_rain", "radiation"]:
        src_col = f"{var}_source"
        if src_col in df.columns:
            counts = df[src_col].value_counts().to_dict()
            print(f"  {var}: {counts}")

    print()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main():
    parser = argparse.ArgumentParser(
        description="Download historical weather data for fire detection ML",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Data sources:
  SILO — Daily interpolated grids (5km), free, no auth needed.
         Variables: temperature, rain, humidity, radiation, pressure.
         NO WIND DATA. For wind, use ERA5.
  ERA5 — Hourly reanalysis (30km), has wind. Requires cdsapi setup.

Examples:
  %(prog)s --mode targets                     # SILO daily for calibration targets
  %(prog)s --mode grid --spacing 1.0          # SILO daily on 1° NSW grid
  %(prog)s --mode netcdf                      # SILO annual NetCDF grids (~400MB each)
  %(prog)s --mode era5                        # ERA5 hourly for NSW
  %(prog)s --mode targets --test              # Quick test (one point, 3 days)
        """,
    )
    parser.add_argument(
        "--mode",
        choices=["targets", "grid", "netcdf", "era5"],
        default="targets",
        help="Download mode (default: targets)",
    )
    parser.add_argument(
        "--start", default=DEFAULT_START,
        help="Start date YYYYMMDD (default: %(default)s)",
    )
    parser.add_argument(
        "--end", default=DEFAULT_END,
        help="End date YYYYMMDD (default: %(default)s)",
    )
    parser.add_argument(
        "--spacing", type=float, default=0.5,
        help="Grid spacing in degrees for --mode grid (default: 0.5)",
    )
    parser.add_argument(
        "--variables", nargs="+",
        help="SILO NetCDF variables to download (default: all key variables)",
    )
    parser.add_argument(
        "--test", action="store_true",
        help="Quick test mode: one location, 3 days",
    )
    parser.add_argument(
        "--summary-only", action="store_true",
        help="Just print summary of existing data, don't download",
    )
    args = parser.parse_args()

    WEATHER_DIR.mkdir(parents=True, exist_ok=True)

    if args.summary_only:
        csv_path = WEATHER_DIR / "silo" / "silo_daily_weather.csv"
        summarize_weather_data(csv_path)
        return

    if args.mode == "targets":
        if args.test:
            # Quick test: one point, 3 days
            targets = [{"label": "test_point", "lat": -33.50, "lon": 148.00}]
            start, end = "20251126", "20251128"
            log.info("TEST MODE: 1 point, 3 days")
        else:
            targets = load_calibration_targets()
            start, end = args.start, args.end

        csv_path = download_silo_targets(targets, start, end)
        summarize_weather_data(csv_path)

    elif args.mode == "grid":
        targets = generate_nsw_grid(args.spacing)
        csv_path = download_silo_targets(targets, args.start, args.end)
        summarize_weather_data(csv_path)

    elif args.mode == "netcdf":
        variables = args.variables or SILO_NETCDF_VARS
        # Determine years from date range
        start_year = int(args.start[:4])
        end_year = int(args.end[:4])
        years = list(range(start_year, end_year + 1))
        downloaded = download_silo_netcdf(variables, years)
        log.info("Downloaded %d NetCDF files", len(downloaded))
        for p in downloaded:
            log.info("  %s (%.0f MB)", p.name, p.stat().st_size / 1e6)

    elif args.mode == "era5":
        result = download_era5(args.start, args.end)
        if result:
            log.info("ERA5 data saved to %s", result)
        else:
            log.error("ERA5 download failed")

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
