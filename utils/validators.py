"""
URL validation and site support checking utilities.
"""
import re
from typing import Tuple
from urllib.parse import urlparse
import logging


def validate_url(url: str) -> Tuple[bool, str]:
    """
    Validate URL format and basic structure.
    
    Args:
        url: URL string to validate
    
    Returns:
        Tuple of (is_valid, error_message)
    """
    if not url or not url.strip():
        return False, "URL cannot be empty"
    
    url = url.strip()
    
    # Basic URL structure validation
    try:
        result = urlparse(url)
        if not all([result.scheme, result.netloc]):
            return False, "Invalid URL format - missing scheme or domain"
        
        if result.scheme not in ['http', 'https']:
            return False, "URL must use HTTP or HTTPS protocol"
        
        return True, ""
    except Exception as e:
        return False, f"Invalid URL: {str(e)}"


def is_supported_site(url: str) -> Tuple[bool, str]:
    """
    Check if URL is from a supported site (basic check).
    
    Args:
        url: URL to check
    
    Returns:
        Tuple of (is_supported, site_name)
    """
    url_lower = url.lower()
    
    supported_sites = {
        'youtube.com': 'YouTube',
        'youtu.be': 'YouTube',
        'vimeo.com': 'Vimeo',
        'dailymotion.com': 'Dailymotion',
        'twitch.tv': 'Twitch',
        'facebook.com': 'Facebook',
        'instagram.com': 'Instagram',
        'twitter.com': 'Twitter',
        'x.com': 'Twitter/X',
        'tiktok.com': 'TikTok',
        'soundcloud.com': 'SoundCloud',
        'bandcamp.com': 'Bandcamp',
    }
    
    for domain, name in supported_sites.items():
        if domain in url_lower:
            return True, name
    
    # yt-dlp supports many more sites, so we'll be permissive
    # This is just to provide helpful feedback
    return True, "Other (yt-dlp supported)"


def validate_multiple_urls(urls_text: str) -> Tuple[list, list]:
    """
    Validate multiple URLs from text (one per line).
    
    Args:
        urls_text: Text containing URLs separated by newlines
    
    Returns:
        Tuple of (valid_urls, errors) where errors is list of (url, error_msg)
    """
    valid_urls = []
    errors = []
    
    lines = urls_text.strip().split('\n')
    for line in lines:
        line = line.strip()
        if not line:
            continue
        
        is_valid, error_msg = validate_url(line)
        if is_valid:
            valid_urls.append(line)
        else:
            errors.append((line, error_msg))
    
    return valid_urls, errors


def extract_video_id(url: str) -> str:
    """
    Extract video ID from YouTube URL.
    
    Args:
        url: YouTube URL
    
    Returns:
        Video ID or empty string
    """
    patterns = [
        r'(?:v=|/)([0-9A-Za-z_-]{11}).*',
        r'(?:embed/)([0-9A-Za-z_-]{11})',
        r'(?:watch\?v=)([0-9A-Za-z_-]{11})'
    ]
    
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    
    return ""


def sanitize_filename(filename: str) -> str:
    """
    Sanitize filename by removing invalid characters.
    
    Args:
        filename: Original filename
    
    Returns:
        Sanitized filename
    """
    # Remove invalid characters for Windows/Linux
    invalid_chars = r'[<>:"/\\|?*]'
    sanitized = re.sub(invalid_chars, '_', filename)
    
    # Remove leading/trailing spaces and dots
    sanitized = sanitized.strip('. ')
    
    # Limit length
    if len(sanitized) > 255:
        sanitized = sanitized[:255]
    
    return sanitized
