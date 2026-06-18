#!/usr/bin/env python3
"""
Build XYZ PNG map tiles from DEM/DEM derivative GeoTIFF folders.

Input directory layout:
  dem_derivatives/
    aspect/*.tif
    hillshade/*.tif
    slope/*.tif
    twi/*.tif

  or raw DEM tiles:
    srtm/*.tif

Output directory layout:
  terrain_tiles/
    elevation/{z}/{x}/{y}.png
    hillshade/{z}/{x}/{y}.png
    slope/{z}/{x}/{y}.png
    aspect/{z}/{x}/{y}.png
    twi/{z}/{x}/{y}.png

The output is standard Web Mercator XYZ tiles for Leaflet/Folium.
"""

from __future__ import annotations

import argparse
import math
import warnings
from dataclasses import dataclass
from pathlib import Path
from typing import Any

try:
    import numpy as np
    import rasterio
    from rasterio.enums import Resampling
    from rasterio.errors import NotGeoreferencedWarning
    from rasterio.transform import from_bounds
    from rasterio.vrt import WarpedVRT
    from rasterio.warp import transform_bounds
except ImportError as exc:
    np = None
    rasterio = None
    IMPORT_ERROR = exc
else:
    IMPORT_ERROR = None
    warnings.filterwarnings("ignore", category=NotGeoreferencedWarning)


WEB_MERCATOR = "EPSG:3857"
WGS84 = "EPSG:4326"
ORIGIN_SHIFT = 20037508.342789244
TILE_SIZE = 256
SUPPORTED_LAYERS = ("elevation", "hillshade", "slope", "aspect", "twi")


@dataclass
class SourceRaster:
    path: Path
    dataset: Any
    bounds_wgs84: tuple[float, float, float, float]


def lonlat_to_tile(lon: float, lat: float, zoom: int) -> tuple[int, int]:
    lat = max(min(lat, 85.05112878), -85.05112878)
    n = 2**zoom
    x = int((lon + 180.0) / 360.0 * n)
    lat_rad = math.radians(lat)
    y = int((1.0 - math.asinh(math.tan(lat_rad)) / math.pi) / 2.0 * n)
    return max(0, min(n - 1, x)), max(0, min(n - 1, y))


def tile_bounds_mercator(x: int, y: int, zoom: int) -> tuple[float, float, float, float]:
    resolution = (2 * ORIGIN_SHIFT) / (TILE_SIZE * 2**zoom)
    west = x * TILE_SIZE * resolution - ORIGIN_SHIFT
    east = (x + 1) * TILE_SIZE * resolution - ORIGIN_SHIFT
    north = ORIGIN_SHIFT - y * TILE_SIZE * resolution
    south = ORIGIN_SHIFT - (y + 1) * TILE_SIZE * resolution
    return west, south, east, north


def intersects(a: tuple[float, float, float, float], b: tuple[float, float, float, float]) -> bool:
    aw, as_, ae, an = a
    bw, bs, be, bn = b
    return aw < be and ae > bw and as_ < bn and an > bs


def open_sources(layer_dir: Path) -> list[SourceRaster]:
    sources = []
    for path in sorted(layer_dir.glob("*.tif")):
        dataset = rasterio.open(path)
        if dataset.crs:
            bounds = transform_bounds(dataset.crs, WGS84, *dataset.bounds, densify_pts=21)
        else:
            bounds = tuple(dataset.bounds)
        sources.append(SourceRaster(path=path, dataset=dataset, bounds_wgs84=bounds))
    return sources


def close_sources(sources: list[SourceRaster]) -> None:
    for source in sources:
        source.dataset.close()


def union_bounds(sources: list[SourceRaster]) -> tuple[float, float, float, float]:
    west = min(src.bounds_wgs84[0] for src in sources)
    south = min(src.bounds_wgs84[1] for src in sources)
    east = max(src.bounds_wgs84[2] for src in sources)
    north = max(src.bounds_wgs84[3] for src in sources)
    return west, south, east, north


def read_tile_data(
    sources: list[SourceRaster],
    tile_bounds_3857: tuple[float, float, float, float],
    tile_bounds_wgs84: tuple[float, float, float, float],
    resampling: Any,
) -> tuple[Any, Any]:
    data = np.full((TILE_SIZE, TILE_SIZE), np.nan, dtype="float32")
    valid = np.zeros((TILE_SIZE, TILE_SIZE), dtype=bool)
    dst_transform = from_bounds(*tile_bounds_3857, TILE_SIZE, TILE_SIZE)

    for source in sources:
        if not intersects(source.bounds_wgs84, tile_bounds_wgs84):
            continue
        with WarpedVRT(
            source.dataset,
            crs=WEB_MERCATOR,
            transform=dst_transform,
            width=TILE_SIZE,
            height=TILE_SIZE,
            resampling=resampling,
        ) as vrt:
            arr = vrt.read(1, masked=True).astype("float32")
        mask = ~np.ma.getmaskarray(arr) & np.isfinite(arr.filled(np.nan))
        data[mask] = arr.filled(np.nan)[mask]
        valid[mask] = True

    return data, valid


def interpolate_ramp(values: Any, stops: list[tuple[float, tuple[int, int, int]]]) -> Any:
    rgb = np.zeros((values.shape[0], values.shape[1], 3), dtype="uint8")
    for idx, (start_value, start_color) in enumerate(stops[:-1]):
        end_value, end_color = stops[idx + 1]
        segment = (values >= start_value) & (values <= end_value)
        t = np.clip((values - start_value) / (end_value - start_value), 0, 1)
        for channel in range(3):
            rgb[..., channel][segment] = (
                start_color[channel] + t[segment] * (end_color[channel] - start_color[channel])
            ).astype("uint8")
    rgb[values < stops[0][0]] = stops[0][1]
    rgb[values > stops[-1][0]] = stops[-1][1]
    return rgb


def aspect_to_rgb(aspect: Any) -> Any:
    hue = (aspect % 360.0) / 60.0
    chroma = 0.65
    x_val = chroma * (1 - np.abs((hue % 2) - 1))
    zeros = np.zeros_like(hue)

    rgb_prime = np.zeros((aspect.shape[0], aspect.shape[1], 3), dtype="float32")
    cases = [
        ((0 <= hue) & (hue < 1), (chroma, x_val, zeros)),
        ((1 <= hue) & (hue < 2), (x_val, chroma, zeros)),
        ((2 <= hue) & (hue < 3), (zeros, chroma, x_val)),
        ((3 <= hue) & (hue < 4), (zeros, x_val, chroma)),
        ((4 <= hue) & (hue < 5), (x_val, zeros, chroma)),
        ((5 <= hue) & (hue < 6), (chroma, zeros, x_val)),
    ]
    for mask, channels in cases:
        for channel_idx, channel_values in enumerate(channels):
            rgb_prime[..., channel_idx][mask] = channel_values[mask] if hasattr(channel_values, "shape") else channel_values

    match_value = 0.95 - chroma
    return np.clip((rgb_prime + match_value) * 255, 0, 255).astype("uint8")


def colorize(layer: str, data: Any, valid: Any) -> Any:
    rgba = np.zeros((TILE_SIZE, TILE_SIZE, 4), dtype="uint8")
    if not np.any(valid):
        return rgba

    if layer == "elevation":
        values = np.clip(np.where(valid, data, 0), 0, 2000)
        rgba[..., :3] = interpolate_ramp(
            values,
            [
                (0, (56, 124, 88)),
                (100, (104, 164, 92)),
                (300, (180, 190, 112)),
                (700, (194, 154, 104)),
                (1200, (145, 116, 103)),
                (2000, (238, 238, 232)),
            ],
        )
        rgba[..., 3][valid] = 190
    elif layer == "hillshade":
        values = np.clip(np.where(valid, data, 0), 0, 255).astype("uint8")
        rgba[..., 0] = values
        rgba[..., 1] = values
        rgba[..., 2] = values
        rgba[..., 3][valid] = 210
    elif layer == "slope":
        values = np.clip(np.where(valid, data, 0), 0, 45)
        rgba[..., :3] = interpolate_ramp(
            values,
            [
                (0, (45, 145, 95)),
                (10, (134, 190, 88)),
                (20, (246, 210, 92)),
                (35, (231, 111, 81)),
                (45, (168, 55, 70)),
            ],
        )
        rgba[..., 3][valid] = 190
    elif layer == "aspect":
        rgba[..., :3] = aspect_to_rgb(np.where(valid, data, 0))
        rgba[..., 3][valid] = 175
    elif layer == "twi":
        values = np.clip(np.where(valid, data, 4), 4, 18)
        rgba[..., :3] = interpolate_ramp(
            values,
            [
                (4, (92, 84, 164)),
                (8, (43, 131, 186)),
                (11, (102, 194, 165)),
                (14, (230, 245, 152)),
                (18, (254, 153, 41)),
            ],
        )
        rgba[..., 3][valid] = 185
    else:
        raise ValueError(f"Unsupported layer: {layer}")

    rgba[..., 3][~valid] = 0
    return rgba


def write_png(path: Path, rgba: Any, overwrite: bool) -> bool:
    if path.exists() and not overwrite:
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    with rasterio.open(
        path,
        "w",
        driver="PNG",
        width=TILE_SIZE,
        height=TILE_SIZE,
        count=4,
        dtype="uint8",
    ) as dst:
        for band in range(4):
            dst.write(rgba[..., band], band + 1)
    return True


def build_layer_tiles(
    layer: str,
    input_dir: Path,
    output_dir: Path,
    min_zoom: int,
    max_zoom: int,
    overwrite: bool,
    keep_empty: bool,
) -> None:
    layer_dir = input_dir / layer
    if layer == "elevation" and not layer_dir.exists():
        layer_dir = input_dir
    sources = open_sources(layer_dir)
    if not sources:
        print(f"[skip] {layer}: no GeoTIFF files found")
        return

    bounds = union_bounds(sources)
    resampling = Resampling.nearest if layer == "aspect" else Resampling.bilinear
    written = 0
    skipped_empty = 0

    try:
        for zoom in range(min_zoom, max_zoom + 1):
            west, south, east, north = bounds
            min_x, max_y = lonlat_to_tile(west, south, zoom)
            max_x, min_y = lonlat_to_tile(east, north, zoom)
            total = (max_x - min_x + 1) * (max_y - min_y + 1)
            print(f"[{layer}] z{zoom}: {total} tile candidates")

            for x in range(min_x, max_x + 1):
                for y in range(min_y, max_y + 1):
                    out_path = output_dir / layer / str(zoom) / str(x) / f"{y}.png"
                    if out_path.exists() and not overwrite:
                        continue

                    tile_bounds_3857 = tile_bounds_mercator(x, y, zoom)
                    tile_bounds_wgs84 = transform_bounds(WEB_MERCATOR, WGS84, *tile_bounds_3857, densify_pts=21)
                    data, valid = read_tile_data(sources, tile_bounds_3857, tile_bounds_wgs84, resampling)
                    if not keep_empty and not np.any(valid):
                        skipped_empty += 1
                        continue

                    rgba = colorize(layer, data, valid)
                    if write_png(out_path, rgba, overwrite):
                        written += 1

        print(f"[ok] {layer}: wrote {written} tile(s), skipped {skipped_empty} empty tile(s)")
    finally:
        close_sources(sources)


def parse_layers(value: str) -> list[str]:
    layers = [item.strip() for item in value.split(",") if item.strip()]
    invalid = [layer for layer in layers if layer not in SUPPORTED_LAYERS]
    if invalid:
        raise argparse.ArgumentTypeError(f"Unsupported layer(s): {', '.join(invalid)}")
    return layers


def main() -> None:
    parser = argparse.ArgumentParser(description="Build Leaflet/Folium XYZ PNG tiles from DEM derivatives.")
    parser.add_argument("input_dir", type=Path, help="Directory containing DEM derivative subfolders.")
    parser.add_argument("output_dir", type=Path, help="Directory where terrain_tiles will be created.")
    parser.add_argument("--layers", type=parse_layers, default=list(SUPPORTED_LAYERS), help="Comma-separated layer list.")
    parser.add_argument("--min-zoom", type=int, default=6, help="Minimum XYZ zoom. Default: 6")
    parser.add_argument("--max-zoom", type=int, default=10, help="Maximum XYZ zoom. Default: 10")
    parser.add_argument("--overwrite", action="store_true", help="Overwrite existing PNG tiles.")
    parser.add_argument("--keep-empty", action="store_true", help="Write fully transparent empty tiles.")
    args = parser.parse_args()

    if IMPORT_ERROR is not None:
        raise SystemExit(
            "Missing tile build dependency. Install with:\n"
            "  python3 -m pip install -r scripts/requirements-dem.txt\n\n"
            f"Original error: {IMPORT_ERROR}"
        )

    if args.min_zoom < 0 or args.max_zoom < args.min_zoom:
        raise SystemExit("Invalid zoom range.")

    args.output_dir.mkdir(parents=True, exist_ok=True)
    for layer in args.layers:
        build_layer_tiles(
            layer=layer,
            input_dir=args.input_dir,
            output_dir=args.output_dir,
            min_zoom=args.min_zoom,
            max_zoom=args.max_zoom,
            overwrite=args.overwrite,
            keep_empty=args.keep_empty,
        )
    print("[done]")


if __name__ == "__main__":
    main()
