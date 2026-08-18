"""
Format preset definitions for quick download configuration.
"""
from typing import Dict, Any, List
from core.models import FormatPreset


# Predefined format presets
PRESETS = {
    'Default': FormatPreset(
        name='Default',
        download_type='video',
        quality='1080p (Full HD)',
        format_type='mp4',
        embed_thumbnail=True,
        embed_metadata=True,
        embed_subtitles=False
    ),
    
    'High Quality Video (4K)': FormatPreset(
        name='High Quality Video (4K)',
        download_type='video',
        quality='2160p (4K)',
        format_type='mp4',
        embed_thumbnail=True,
        embed_metadata=True,
        embed_subtitles=False
    ),
    
    'Quick Video (720p)': FormatPreset(
        name='Quick Video (720p)',
        download_type='video',
        quality='720p (HD)',
        format_type='mp4',
        embed_thumbnail=True,
        embed_metadata=True,
        embed_subtitles=False
    ),
    
    'Mobile Video (480p)': FormatPreset(
        name='Mobile Video (480p)',
        download_type='video',
        quality='480p',
        format_type='mp4',
        embed_thumbnail=False,
        embed_metadata=True,
        embed_subtitles=False
    ),
    
    'Music (MP3 High Quality)': FormatPreset(
        name='Music (MP3 High Quality)',
        download_type='audio',
        quality='',
        format_type='mp3',
        embed_thumbnail=True,
        embed_metadata=True,
        embed_subtitles=False
    ),
    
    'Music (M4A)': FormatPreset(
        name='Music (M4A)',
        download_type='audio',
        quality='',
        format_type='m4a',
        embed_thumbnail=True,
        embed_metadata=True,
        embed_subtitles=False
    ),
    
    'Podcast/Audio Book (MP3)': FormatPreset(
        name='Podcast/Audio Book (MP3)',
        download_type='audio',
        quality='',
        format_type='mp3',
        embed_thumbnail=True,
        embed_metadata=True,
        embed_subtitles=False
    ),
    
    'Video with Subtitles': FormatPreset(
        name='Video with Subtitles',
        download_type='video',
        quality='1080p (Full HD)',
        format_type='mp4',
        embed_thumbnail=True,
        embed_metadata=True,
        embed_subtitles=True
    ),
    
    'Best Quality Available': FormatPreset(
        name='Best Quality Available',
        download_type='video',
        quality='Best Available',
        format_type='mp4',
        embed_thumbnail=True,
        embed_metadata=True,
        embed_subtitles=False
    ),
}


class PresetManager:
    """Manage download format presets"""
    
    def __init__(self):
        self.presets = PRESETS.copy()
        self.custom_presets: Dict[str, FormatPreset] = {}
    
    def get_preset(self, name: str) -> FormatPreset:
        """Get preset by name"""
        if name in self.presets:
            return self.presets[name]
        elif name in self.custom_presets:
            return self.custom_presets[name]
        else:
            return self.presets['Default']
    
    def get_preset_names(self) -> List[str]:
        """Get list of all preset names"""
        return list(self.presets.keys()) + list(self.custom_presets.keys())
    
    def add_custom_preset(self, preset: FormatPreset) -> None:
        """Add a custom preset"""
        self.custom_presets[preset.name] = preset
    
    def remove_custom_preset(self, name: str) -> bool:
        """Remove a custom preset"""
        if name in self.custom_presets:
            del self.custom_presets[name]
            return True
        return False
    
    def get_default_presets(self) -> Dict[str, FormatPreset]:
        """Get dictionary of default presets"""
        return self.presets.copy()
    
    def apply_preset_to_options(self, preset_name: str) -> Dict[str, Any]:
        """
        Convert preset to download options dict.
        
        Args:
            preset_name: Name of preset to apply
        
        Returns:
            Dictionary of options for download
        """
        preset = self.get_preset(preset_name)
        
        return {
            'download_type': preset.download_type,
            'quality': preset.quality,
            'format_type': preset.format_type,
            'embed_thumbnail': preset.embed_thumbnail,
            'embed_metadata': preset.embed_metadata,
            'embed_subtitles': preset.embed_subtitles
        }
