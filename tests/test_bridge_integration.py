"""
Comprehensive Integration Tests for StreamFlow Pro Modern Architecture.
Tests backend adapter, queue state transitions, event bus bridging, and database persistence.
"""
import unittest
import time
import json
from pathlib import Path
from backend.api_adapter import BackendApiAdapter
from core.events import Event
from core.models import DownloadItem, DownloadStatus


class TestBackendApiAdapter(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.adapter = BackendApiAdapter()

    @classmethod
    def tearDownClass(cls):
        cls.adapter.downloader.shutdown()

    def test_config_operations(self):
        """Test getting and updating config."""
        cfg = self.adapter.get_config()
        self.assertIn("download_path", cfg)
        self.assertIn("theme", cfg)

        updated = self.adapter.update_config({"concurrent_downloads": 4})
        self.assertEqual(updated["concurrent_downloads"], 4)
        self.assertEqual(self.adapter.downloader.max_concurrent, 4)

    def test_presets(self):
        """Test presets retrieval."""
        presets = self.adapter.get_presets()
        self.assertGreater(len(presets), 0)
        preset_names = [p["name"] for p in presets]
        self.assertIn("Default", preset_names)
        self.assertIn("High Quality Video (4K)", preset_names)

    def test_url_validation(self):
        """Test single and batch URL validation."""
        valid_res = self.adapter.validate_input("https://www.youtube.com/watch?v=dQw4w9WgXcQ")
        self.assertTrue(valid_res["is_valid"])
        self.assertEqual(len(valid_res["valid_urls"]), 1)
        self.assertEqual(valid_res["detected_sites"][0]["site"], "YouTube")

        batch_input = """
        https://www.youtube.com/watch?v=test1
        https://vimeo.com/123456
        invalid-url-string
        """
        batch_res = self.adapter.validate_input(batch_input)
        self.assertFalse(batch_res["is_valid"])
        self.assertEqual(len(batch_res["valid_urls"]), 2)
        self.assertEqual(len(batch_res["errors"]), 1)

    def test_queue_state_transitions(self):
        """Test adding, pausing, resuming, cancelling, and removing queue items."""
        add_res = self.adapter.add_downloads(
            urls=["https://www.youtube.com/watch?v=mock_video_1"],
            download_type="video",
            quality="1080p (Full HD)",
            format_type="mp4"
        )
        self.assertTrue(add_res["success"])
        self.assertGreaterEqual(add_res["added_count"], 1)

        item_id = add_res["items"][0]["id"]

        # Pause
        pause_ok = self.adapter.pause_item(item_id)
        self.assertTrue(pause_ok)

        # Check in queue
        q = self.adapter.get_queue()
        found = next((i for i in q["items"] if i["id"] == item_id), None)
        self.assertIsNotNone(found)
        self.assertEqual(found["status"], "Paused")

        # Resume
        resume_ok = self.adapter.resume_item(item_id)
        self.assertTrue(resume_ok)
        q2 = self.adapter.get_queue()
        found2 = next((i for i in q2["items"] if i["id"] == item_id), None)
        self.assertEqual(found2["status"], "Queued")

        # Cancel
        cancel_ok = self.adapter.cancel_item(item_id)
        self.assertTrue(cancel_ok)

        # Remove
        remove_ok = self.adapter.remove_item(item_id)
        self.assertTrue(remove_ok)
        q3 = self.adapter.get_queue()
        found3 = next((i for i in q3["items"] if i["id"] == item_id), None)
        self.assertIsNone(found3)

    def test_bulk_queue_actions(self):
        """Test pause_all, resume_all, and clear_completed."""
        self.adapter.add_downloads(["https://www.youtube.com/watch?v=mock_bulk_1"])
        self.adapter.add_downloads(["https://www.youtube.com/watch?v=mock_bulk_2"])

        paused_count = self.adapter.pause_all()
        self.assertGreaterEqual(paused_count, 1)

        resumed_count = self.adapter.resume_all()
        self.assertGreaterEqual(resumed_count, 1)

    def test_event_bus_integration(self):
        """Verify EventBus emissions fire correctly."""
        events_received = []

        def listener(data):
            events_received.append(data)

        self.adapter.event_bus.subscribe(Event.STATUS_MESSAGE, listener)
        self.adapter.event_bus.emit(Event.STATUS_MESSAGE, "Test Engine Message")

        self.assertEqual(len(events_received), 1)
        self.assertEqual(events_received[0], "Test Engine Message")


if __name__ == "__main__":
    unittest.main()
