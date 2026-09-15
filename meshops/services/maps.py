"""Discover and serve locally installed MBTiles map packages."""

from dataclasses import dataclass
from pathlib import Path
import sqlite3


DEFAULT_MAPS_DIRECTORY = Path("/var/lib/meshops/maps")


@dataclass(frozen=True)
class MapBounds:
    """Geographic extent declared by an MBTiles package."""

    west: float
    south: float
    east: float
    north: float

    def contains(self, latitude: float, longitude: float) -> bool:
        return (
            self.south <= latitude <= self.north
            and self.west <= longitude <= self.east
        )


@dataclass(frozen=True)
class OfflineMap:
    """Metadata needed to select an installed map."""

    name: str
    path: Path
    bounds: MapBounds | None
    min_zoom: int | None
    max_zoom: int | None
    tile_format: str | None

    @property
    def identifier(self) -> str:
        """Return the stable filename-based identifier used by the tile route."""

        return self.path.stem

    def covers(self, latitude: float, longitude: float) -> bool:
        return self.bounds is not None and self.bounds.contains(latitude, longitude)


@dataclass(frozen=True)
class MapTile:
    """A tile read from an MBTiles package for an HTTP response."""

    data: bytes
    media_type: str


class MapService:
    """Discover, select, and read locally installed MBTiles packages."""

    def __init__(self, maps_directory: Path = DEFAULT_MAPS_DIRECTORY):
        self.maps_directory = maps_directory

    def discover(self) -> list[OfflineMap]:
        """Return valid MBTiles files installed in the configured directory."""

        if not self.maps_directory.is_dir():
            return []

        maps = []

        for path in sorted(self.maps_directory.glob("*.mbtiles")):
            offline_map = self._read_mbtiles(path)

            if offline_map is not None:
                maps.append(offline_map)

        return maps

    def map_for_coordinate(
        self,
        latitude: float,
        longitude: float,
    ) -> OfflineMap | None:
        """Return the first installed map covering a coordinate, if any."""

        for offline_map in self.discover():
            if offline_map.covers(latitude, longitude):
                return offline_map

        return None

    def tile(
        self,
        map_identifier: str,
        zoom: int,
        column: int,
        row: int,
    ) -> MapTile | None:
        """Return an XYZ tile from an installed map, if it exists."""

        offline_map = self._map_by_identifier(map_identifier)

        if offline_map is None or not self._valid_tile(offline_map, zoom, column, row):
            return None

        # MBTiles stores rows in TMS order; Leaflet requests XYZ rows.
        tms_row = (1 << zoom) - 1 - row

        try:
            with sqlite3.connect(
                f"file:{offline_map.path}?mode=ro",
                uri=True,
            ) as database:
                result = database.execute(
                    """
                    SELECT tile_data
                    FROM tiles
                    WHERE zoom_level = ? AND tile_column = ? AND tile_row = ?
                    """,
                    (zoom, column, tms_row),
                ).fetchone()
        except (OSError, sqlite3.Error):
            return None

        if result is None:
            return None

        return MapTile(
            data=result[0],
            media_type=self._media_type(offline_map.tile_format),
        )

    def _map_by_identifier(self, map_identifier: str) -> OfflineMap | None:
        for offline_map in self.discover():
            if offline_map.identifier == map_identifier:
                return offline_map

        return None

    @staticmethod
    def _valid_tile(
        offline_map: OfflineMap,
        zoom: int,
        column: int,
        row: int,
    ) -> bool:
        if zoom < 0 or column < 0 or row < 0:
            return False

        if offline_map.min_zoom is not None and zoom < offline_map.min_zoom:
            return False

        if offline_map.max_zoom is not None and zoom > offline_map.max_zoom:
            return False

        world_size = 1 << zoom
        return column < world_size and row < world_size

    def _read_mbtiles(self, path: Path) -> OfflineMap | None:
        """Read standard metadata without modifying the package."""

        try:
            with sqlite3.connect(f"file:{path}?mode=ro", uri=True) as database:
                rows = database.execute(
                    "SELECT name, value FROM metadata"
                ).fetchall()
        except (OSError, sqlite3.Error):
            return None

        metadata = dict(rows)

        return OfflineMap(
            name=metadata.get("name", path.stem),
            path=path,
            bounds=self._parse_bounds(metadata.get("bounds")),
            min_zoom=self._parse_zoom(metadata.get("minzoom")),
            max_zoom=self._parse_zoom(metadata.get("maxzoom")),
            tile_format=metadata.get("format"),
        )

    @staticmethod
    def _parse_bounds(value: str | None) -> MapBounds | None:
        if value is None:
            return None

        try:
            west, south, east, north = (float(item) for item in value.split(","))
        except ValueError:
            return None

        if west > east or south > north:
            return None

        if not (-180 <= west <= 180 and -180 <= east <= 180):
            return None

        if not (-90 <= south <= 90 and -90 <= north <= 90):
            return None

        return MapBounds(west=west, south=south, east=east, north=north)

    @staticmethod
    def _parse_zoom(value: str | None) -> int | None:
        try:
            return int(value) if value is not None else None
        except ValueError:
            return None

    @staticmethod
    def _media_type(tile_format: str | None) -> str:
        formats = {
            "jpg": "image/jpeg",
            "jpeg": "image/jpeg",
            "png": "image/png",
            "webp": "image/webp",
        }
        return formats.get((tile_format or "").lower(), "application/octet-stream")
