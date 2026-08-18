"""Quick test to verify YouTube search works"""
import yt_dlp

print("Testing YouTube search...")
print("=" * 50)

try:
    ydl_opts = {
        'quiet': False,
        'extract_flat': True,
        'no_warnings': False,
        'ignoreerrors': True
    }
    
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        print("Searching for: music")
        info = ydl.extract_info("ytsearch5:music", download=False)
    
    if info:
        entries = info.get('entries', [])
        print(f"\n✅ Got {len(entries)} results")
        
        if entries:
            print("\nFirst 3 results:")
            for i, entry in enumerate(entries[:3], 1):
                if entry:
                    title = entry.get('title', 'N/A')
                    channel = entry.get('uploader', 'N/A')
                    video_id = entry.get('id', 'N/A')
                    url = entry.get('url') or entry.get('webpage_url') or f"https://youtube.com/watch?v={video_id}"
                    print(f"\n{i}. {title}")
                    print(f"   Channel: {channel}")
                    print(f"   URL: {url}")
        else:
            print("❌ No entries found")
    else:
        print("❌ No info returned")
        
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "=" * 50)
print("Test complete")
