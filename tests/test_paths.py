import os
import unittest

from modi_flappy.paths import asset_path, project_root


class AssetPathTests(unittest.TestCase):
    def test_images_resolve_under_assets_images(self):
        self.assertEqual(
            asset_path("bird.jpg", "project"),
            os.path.join("project", "assets", "images", "bird.jpg"),
        )

    def test_audio_resolves_under_assets_audio(self):
        self.assertEqual(
            asset_path("music.mp3", "project"),
            os.path.join("project", "assets", "audio", "music.mp3"),
        )

    def test_web_paths_are_relative_to_the_project(self):
        self.assertEqual(
            asset_path("death.wav", ""),
            os.path.join("assets", "audio", "death.wav"),
        )

    def test_project_root_is_repository_root(self):
        self.assertEqual(
            project_root(),
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        )


if __name__ == "__main__":
    unittest.main()
