"""
Unit tests for core models.
"""
import unittest
from core.models import DownloadItem, DownloadQueue, DownloadStats, FormatPreset


class TestDownloadItem(unittest.TestCase):
    """Test DownloadItem class"""
    
    def test_create_item(self):
        """Test creating a download item"""
        item = DownloadItem(
            url="https://www.youtube.com/watch?v=test",
            download_type="video",
            quality="1080p",
            options={},
            output_template="%(title)s.%(ext)s"
        )
        
        self.assertIsNotNone(item.id)
        self.assertEqual(item.url, "https://www.youtube.com/watch?v=test")
        self.assertEqual(item.download_type, "video")
        self.assertEqual(item.status, "Queued")
        self.assertEqual(item.progress, 0.0)
    
    def test_to_dict(self):
        """Test converting item to dictionary"""
        item = DownloadItem(
            url="https://test.com",
            download_type="audio",
            quality="Best",
            options={},
            output_template="test.mp3"
        )
        item.title = "Test Title"
        
        data = item.to_dict()
        
        self.assertEqual(data['url'], "https://test.com")
        self.assertEqual(data['title'], "Test Title")
        self.assertEqual(data['download_type'], "audio")
    
    def test_from_dict(self):
        """Test creating item from dictionary"""
        data = {
            'id': 'test-id',
            'url': 'https://test.com',
            'title': 'Test',
            'download_type': 'video',
            'quality': '720p',
            'status': 'Completed',
            'output_template': 'test.mp4'
        }
        
        item = DownloadItem.from_dict(data)
        
        self.assertEqual(item.id, 'test-id')
        self.assertEqual(item.title, 'Test')
        self.assertEqual(item.quality, '720p')


class TestDownloadQueue(unittest.TestCase):
    """Test DownloadQueue class"""
    
    def test_add_remove(self):
        """Test adding and removing items"""
        queue = DownloadQueue()
        item = DownloadItem("url", "video", "1080p", {}, "template")
        
        queue.add(item)
        self.assertEqual(len(queue.items), 1)
        
        queue.remove(item)
        self.assertEqual(len(queue.items), 0)
    
    def test_get_next(self):
        """Test getting next queued item"""
        queue = DownloadQueue()
        
        item1 = DownloadItem("url1", "video", "1080p", {}, "template")
        item2 = DownloadItem("url2", "video", "1080p", {}, "template")
        item2.paused = True
        
        queue.add(item1)
        queue.add(item2)
        
        next_item = queue.get_next()
        self.assertEqual(next_item, item1)


class TestDownloadStats(unittest.TestCase):
    """Test DownloadStats class"""
    
    def test_add_download(self):
        """Test adding download to statistics"""
        stats = DownloadStats()
        
        item = DownloadItem("url", "video", "1080p", {}, "template")
        item.status = "Completed"
        item.file_size = 1024 * 1024 * 100  # 100MB
        item.channel = "Test Channel"
        
        stats.add_download(item)
        
        self.assertEqual(stats.total_downloads, 1)
        self.assertEqual(stats.successful_downloads, 1)
        self.assertEqual(stats.failed_downloads, 0)
        self.assertEqual(stats.total_size_bytes, 1024 * 1024 * 100)
        self.assertEqual(stats.channels["Test Channel"], 1)
    
    def test_success_rate(self):
        """Test success rate calculation"""
        stats = DownloadStats()
        stats.total_downloads = 10
        stats.successful_downloads = 8
        
        self.assertEqual(stats.get_success_rate(), 80.0)


if __name__ == '__main__':
    unittest.main()
