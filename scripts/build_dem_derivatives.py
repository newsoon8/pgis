#!/usr/bin/env python3
"""
Build DEM derivative rasters from SRTM/GeoTIFF tiles.

Outputs one GeoTIFF per input tile under:
  slope/
  aspect/
  hillshade/
  flow_accumulation/
  twi/

The hydrology outputs use a simple D8 flow model per tile. This is useful for a
first service layer, but it has tile-edge effects. For production basin-scale
hydrology, mosaic/condition the DEM first or use WhiteboxTools/SAGA/GRASS.
"""

from __future__ import annotations

import argparse
import math
from collections import deque
from pathlib import Path
from typing import Any

try:
    import numpy as np
    import rasterio
except ImportError as exc:
    np = None
    rasterio = None
    IMPORT_ERROR = exc
else:
    IMPORT_ERROR = None


NODATA_FLOAT = -9999.0
NODATA_UINT8 = 0


def cell_size_meters(dataset: Any) -> tuple[float, float]:
    transform = dataset.transform
    dx = abs(transform.a)
    dy = abs(transform.e)

    if dataset.crs and dataset.crs.is_geographic:
        bounds = dataset.bounds
        lat = (bounds.top + bounds.bottom) / 2
        lat_rad = math.radians(lat)
        dx_m = dx * 111_320.0 * math.cos(lat_rad)
        dy_m = dy * 110_540.0
        return dx_m, dy_m

    return dx, dy


def output_profile(src: Any, dtype: str, nodata: float | int) -> dict:
    profile = src.profile.copy()
    profile.update(
        driver="GTiff",
        count=1,
        dtype=dtype,
        nodata=nodata,
        compress="deflate",
        predictor=2 if dtype != "uint8" else 1,
        tiled=True,
        blockxsize=256,
        blockysize=256,
        BIGTIFF="IF_SAFER",
    )
    return profile


def read_dem(src: Any) -> Any:
    arr = src.read(1, masked=True).astype("float32")
    dem = arr.filled(np.nan)
    dem[~np.isfinite(dem)] = np.nan
    return dem


def terrain_gradient(dem: Any, dx_m: float, dy_m: float) -> tuple[Any, Any]:
    valid_mean = float(np.nanmean(dem))
    filled = np.where(np.isfinite(dem), dem, valid_mean)
    dz_drow, dz_dx = np.gradient(filled, dy_m, dx_m)
    dz_dx = dz_dx.astype("float32")
    dz_drow = dz_drow.astype("float32")
    dz_dx[~np.isfinite(dem)] = np.nan
    dz_drow[~np.isfinite(dem)] = np.nan
    return dz_dx, dz_drow


def slope_aspect_hillshade(
    dem: Any,
    dx_m: float,
    dy_m: float,
    azimuth_deg: float = 315.0,
    altitude_deg: float = 45.0,
) -> tuple[Any, Any, Any, Any]:
    dz_dx, dz_drow = terrain_gradient(dem, dx_m, dy_m)
    slope_rad = np.arctan(np.sqrt(dz_dx * dz_dx + dz_drow * dz_drow))
    slope_deg = np.degrees(slope_rad).astype("float32")

    # Aspect is downslope direction in compass degrees, clockwise from north.
    down_east = -dz_dx
    down_north = dz_drow
    aspect = (np.degrees(np.arctan2(down_east, down_north)) + 360.0) % 360.0
    aspect = aspect.astype("float32")

    azimuth_rad = math.radians(azimuth_deg)
    altitude_rad = math.radians(altitude_deg)
    aspect_rad = np.radians(aspect)
    shade = (
        np.sin(altitude_rad) * np.cos(slope_rad)
        + np.cos(altitude_rad) * np.sin(slope_rad) * np.cos(azimuth_rad - aspect_rad)
    )
    hillshade = np.clip(255.0 * shade, 0, 255).astype("uint8")

    invalid = ~np.isfinite(dem)
    slope_deg[invalid] = NODATA_FLOAT
    aspect[invalid] = NODATA_FLOAT
    hillshade[invalid] = NODATA_UINT8
    slope_rad[invalid] = np.nan
    return slope_deg, aspect, hillshade, slope_rad.astype("float32")


def d8_receivers(dem: Any, dx_m: float, dy_m: float) -> tuple[Any, Any]:
    nrows, ncols = dem.shape
    valid = np.isfinite(dem)
    receiver = np.full(dem.size, -1, dtype=np.int64)
    best = np.zeros(dem.shape, dtype="float32")

    padded = np.pad(dem, 1, mode="constant", constant_values=np.nan)
    rows, cols = np.indices(dem.shape)
    flat_idx = (rows * ncols + cols).astype(np.int64)

    neighbors = [
        (-1, 0, dy_m),
        (1, 0, dy_m),
        (0, -1, dx_m),
        (0, 1, dx_m),
        (-1, -1, math.hypot(dx_m, dy_m)),
        (-1, 1, math.hypot(dx_m, dy_m)),
        (1, -1, math.hypot(dx_m, dy_m)),
        (1, 1, math.hypot(dx_m, dy_m)),
    ]

    for dr, dc, distance in neighbors:
        neighbor = padded[1 + dr : 1 + dr + nrows, 1 + dc : 1 + dc + ncols]
        drop = (dem - neighbor) / distance
        target_rows = rows + dr
        target_cols = cols + dc
        in_bounds = (target_rows >= 0) & (target_rows < nrows) & (target_cols >= 0) & (target_cols < ncols)
        update = valid & in_bounds & np.isfinite(neighbor) & (drop > best) & (drop > 0)
        best[update] = drop[update]
        receiver[flat_idx[update]] = (target_rows[update] * ncols + target_cols[update]).astype(np.int64)

    return receiver, valid.reshape(-1)


def flow_accumulation(dem: Any, dx_m: float, dy_m: float) -> Any:
    receiver, valid_flat = d8_receivers(dem, dx_m, dy_m)
    size = dem.size
    inflow = np.zeros(size, dtype=np.int32)
    rec_valid = receiver[receiver >= 0]
    if rec_valid.size:
        inflow += np.bincount(rec_valid, minlength=size).astype(np.int32)

    accum = np.zeros(size, dtype="float32")
    accum[valid_flat] = 1.0

    queue = deque(np.flatnonzero(valid_flat & (inflow == 0)))
    processed = 0
    while queue:
        idx = queue.popleft()
        processed += 1
        rec = receiver[idx]
        if rec >= 0:
            accum[rec] += accum[idx]
            inflow[rec] -= 1
            if inflow[rec] == 0:
                queue.append(rec)

    # Remaining cells are usually flats/depressions/cycles. Keep their local counts.
    out = accum.reshape(dem.shape)
    out[~np.isfinite(dem)] = NODATA_FLOAT
    return out


def topographic_wetness_index(flow_accum: Any, slope_rad: Any, dx_m: float, dy_m: float) -> Any:
    cell_length = math.sqrt(dx_m * dy_m)
    specific_catchment_area = np.maximum(flow_accum, 1.0) * cell_length
    tan_slope = np.maximum(np.tan(slope_rad), 0.001)
    twi = np.log(specific_catchment_area / tan_slope).astype("float32")
    invalid = (flow_accum == NODATA_FLOAT) | ~np.isfinite(slope_rad)
    twi[invalid] = NODATA_FLOAT
    return twi


def write_raster(path: Path, data: Any, profile: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with rasterio.open(path, "w", **profile) as dst:
        dst.write(data, 1)


def process_tile(src_path: Path, out_dir: Path, overwrite: bool, skip_hydrology: bool) -> None:
    stem = src_path.stem
    outputs = {
        "slope": out_dir / "slope" / f"{stem}_slope_deg.tif",
        "aspect": out_dir / "aspect" / f"{stem}_aspect_deg.tif",
        "hillshade": out_dir / "hillshade" / f"{stem}_hillshade.tif",
        "flow_accumulation": out_dir / "flow_accumulation" / f"{stem}_flow_accum.tif",
        "twi": out_dir / "twi" / f"{stem}_twi.tif",
    }
    if not overwrite and all(path.exists() for path in outputs.values()):
        print(f"[skip] {src_path.name}")
        return

    print(f"[read] {src_path.name}")
    with rasterio.open(src_path) as src:
        dem = read_dem(src)
        dx_m, dy_m = cell_size_meters(src)
        slope, aspect, hillshade, slope_rad = slope_aspect_hillshade(dem, dx_m, dy_m)

        float_profile = output_profile(src, "float32", NODATA_FLOAT)
        uint8_profile = output_profile(src, "uint8", NODATA_UINT8)

        write_raster(outputs["slope"], slope, float_profile)
        write_raster(outputs["aspect"], aspect, float_profile)
        write_raster(outputs["hillshade"], hillshade, uint8_profile)
        print(f"[ok] slope/aspect/hillshade for {src_path.name}")

        if skip_hydrology:
            return

        print(f"[flow] D8 flow accumulation for {src_path.name}")
        flow = flow_accumulation(dem, dx_m, dy_m)
        twi = topographic_wetness_index(flow, slope_rad, dx_m, dy_m)
        write_raster(outputs["flow_accumulation"], flow, float_profile)
        write_raster(outputs["twi"], twi, float_profile)
        print(f"[ok] flow_accumulation/twi for {src_path.name}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Build DEM derivative GeoTIFF layers.")
    parser.add_argument("input_dir", type=Path, help="Directory containing SRTM GeoTIFF tiles.")
    parser.add_argument("output_dir", type=Path, help="Directory where derivative subfolders will be created.")
    parser.add_argument("--pattern", default="*.tif", help="Input glob pattern. Default: *.tif")
    parser.add_argument("--overwrite", action="store_true", help="Overwrite existing outputs.")
    parser.add_argument("--skip-hydrology", action="store_true", help="Only build slope/aspect/hillshade.")
    args = parser.parse_args()

    if IMPORT_ERROR is not None:
        raise SystemExit(
            "Missing DEM build dependency. Install with:\n"
            "  python3 -m pip install -r scripts/requirements-dem.txt\n\n"
            f"Original error: {IMPORT_ERROR}"
        )

    tiles = sorted(args.input_dir.glob(args.pattern))
    if not tiles:
        raise SystemExit(f"No input files matched {args.input_dir / args.pattern}")

    args.output_dir.mkdir(parents=True, exist_ok=True)
    print(f"[start] {len(tiles)} tile(s)")
    for tile in tiles:
        process_tile(tile, args.output_dir, args.overwrite, args.skip_hydrology)
    print("[done]")


if __name__ == "__main__":
    main()
