import sqlite3
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from meshops.services.maps import MapService


class MapServiceTests(unittest.TestCase):
    def test_discovers_mbtiles_metadata_and_matches_coverage(self):
        with TemporaryDirectory() as directory:
            map_path = Path(directory) / "burning-man.mbtiles"
            self.create_mbtiles(map_path)

            service = MapService(Path(directory))
            maps = service.discover()

            self.assertEqual(len(maps), 1)
            self.assertEqual(maps[0].name, "Burning Man 2026")
            self.assertEqual(maps[0].min_zoom, 10)
            self.assertEqual(maps[0].max_zoom, 16)
            self.assertEqual(maps[0].tile_format, "png")
            self.assertEqual(
                service.map_for_coordinate(40.786, -119.205),
                maps[0],
            )
            self.assertIsNone(service.map_for_coordinate(38.573, -121.429))

    def test_reads_xyz_tile_from_tms_mbtiles_storage(self):
        with TemporaryDirectory() as directory:
            map_path = Path(directory) / "burning-man.mbtiles"
            self.create_mbtiles(map_path)
            service = MapService(Path(directory))

            tile = service.tile("burning-man", zoom=10, column=512, row=0)

            self.assertIsNotNone(tile)
            self.assertEqual(tile.data, b"test tile")
            self.assertEqual(tile.media_type, "image/png")
            self.assertIsNone(
                service.tile("burning-man", zoom=9, column=0, row=0)
            )

    def test_ignores_invalid_mbtiles_files(self):
        with TemporaryDirectory() as directory:
            map_path = Path(directory) / "invalid.mbtiles"
            map_path.write_text("not a database", encoding="utf-8")

            self.assertEqual(MapService(Path(directory)).discover(), [])

    @staticmethod
    def create_mbtiles(path: Path):
        with sqlite3.connect(path) as database:
            database.execute("CREATE TABLE metadata (name TEXT, value TEXT)")
            database.execute(
                """
                CREATE TABLE tiles (
                    zoom_level INTEGER,
                    tile_column INTEGER,
                    tile_row INTEGER,
                    tile_data BLOB
                )
                """
            )
            database.executemany(
                "INSERT INTO metadata VALUES (?, ?)",
                [
                    ("name", "Burning Man 2026"),
                    ("bounds", "-119.3,40.7,-119.1,40.9"),
                    ("minzoom", "10"),
                    ("maxzoom", "16"),
                    ("format", "png"),
                ],
            )
            database.execute(
                "INSERT INTO tiles VALUES (?, ?, ?, ?)",
                (10, 512, 1023, b"test tile"),
            )


if __name__ == "__main__":
    unittest.main()
