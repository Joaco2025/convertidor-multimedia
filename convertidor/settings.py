"""Preferencias persistentes del usuario (JSON en %APPDATA%)."""
from __future__ import annotations

import json
import os

from .paths import config_dir, downloads_dir

DEFAULTS = {
    "theme": "System",
    "download_dir": downloads_dir(),
    "dl_kind": "audio",
    "dl_audio_format": "mp3",
    "dl_audio_bitrate": "192",
    "dl_video_format": "mp4",
    "dl_video_height": "1080",
    "dl_playlist": False,
    "dl_thumbnail": True,
    "dl_metadata": True,
    "dl_subtitles": False,
    "dl_cookies": "Ninguno",
    "dl_parallel": 2,
    "cv_category": "video",
    "cv_format": {"video": "mp4", "audio": "mp3", "image": "jpg"},
    "cv_same_folder": True,
    "cv_output_dir": downloads_dir(),
    "cv_video_quality": "Media",
    "cv_video_height": "Original",
    "cv_video_copy": False,
    "cv_audio_bitrate": "192",
    "cv_audio_channels": "Original",
    "cv_image_quality": 90,
    "cv_image_max": "Original",
    "cv_pdf_merge": True,
    "cv_parallel": 1,
}


class Settings:
    def __init__(self) -> None:
        self.path = os.path.join(config_dir(), "settings.json")
        self.data = json.loads(json.dumps(DEFAULTS))
        try:
            with open(self.path, encoding="utf-8") as fh:
                stored = json.load(fh)
            for k, v in stored.items():
                if k in self.data and isinstance(v, type(self.data[k])):
                    if isinstance(v, dict):
                        self.data[k].update(v)
                    else:
                        self.data[k] = v
        except (OSError, ValueError):
            pass

    def __getitem__(self, key):
        return self.data[key]

    def __setitem__(self, key, value) -> None:
        self.data[key] = value

    def save(self) -> None:
        try:
            with open(self.path, "w", encoding="utf-8") as fh:
                json.dump(self.data, fh, indent=2, ensure_ascii=False)
        except OSError:
            pass
