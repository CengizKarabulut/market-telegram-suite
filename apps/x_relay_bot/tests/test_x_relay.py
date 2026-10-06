import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from x_relay import (
    best_video_url,
    load_state,
    media_for_post,
    post_text,
    render_post_html,
    save_state,
    split_html_message,
)


class RelayTests(unittest.TestCase):
    def test_note_tweet_wins_for_long_posts(self):
        post = {"text": "kısa", "note_tweet": {"text": "uzun metin"}}
        self.assertEqual(post_text(post), "uzun metin")

    def test_html_is_escaped(self):
        post = {
            "text": "ASELS < 200 & test",
            "created_at": "2026-10-06T08:45:00.000Z",
        }
        rendered = render_post_html("Alpha", post, True)
        self.assertIn("ASELS &lt; 200 &amp; test", rendered)
        self.assertIn("06.10.2026 11:45", rendered)
        self.assertIn("🔒", rendered)

    def test_best_video_variant_prefers_highest_bitrate(self):
        media = {
            "variants": [
                {"content_type": "application/x-mpegURL", "url": "https://hls"},
                {
                    "content_type": "video/mp4",
                    "bit_rate": 256000,
                    "url": "https://low",
                },
                {
                    "content_type": "video/mp4",
                    "bit_rate": 832000,
                    "url": "https://high",
                },
            ]
        }
        self.assertEqual(best_video_url(media), "https://high")

    def test_media_mapping(self):
        post = {"attachments": {"media_keys": ["p1", "v1"]}}
        media = {
            "p1": {"type": "photo", "url": "https://photo"},
            "v1": {
                "type": "video",
                "variants": [
                    {
                        "content_type": "video/mp4",
                        "bit_rate": 1,
                        "url": "https://video",
                    }
                ],
            },
        }
        self.assertEqual(
            media_for_post(post, media),
            [
                {"type": "photo", "url": "https://photo"},
                {"type": "video", "url": "https://video"},
            ],
        )

    def test_state_round_trip(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "state.json"
            self.assertEqual(
                load_state(path),
                {"initialized": False, "last_seen_id": None},
            )
            save_state(path, "12345")
            self.assertEqual(
                load_state(path),
                {"initialized": True, "last_seen_id": "12345"},
            )

    def test_long_message_splits(self):
        chunks = split_html_message("A " * 5000, limit=1000)
        self.assertGreater(len(chunks), 1)
        self.assertTrue(all(len(chunk) <= 1000 for chunk in chunks))


if __name__ == "__main__":
    unittest.main()
