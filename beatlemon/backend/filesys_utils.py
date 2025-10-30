import os, subprocess, re
from typing import Optional
from mutagen import File # type: ignore
from mutagen.flac import FLAC, Picture
from mutagen.mp3 import MP3
from mutagen.mp4 import MP4
from mutagen.oggvorbis import OggVorbis
from PIL import Image
from io import BytesIO

def find_song_paths(music_dir: str) -> list:
    """
    Find all song paths in the music directory recursively.
    :param music_dir: Path to the music directory.
    :return: List of song paths.
    """
    song_paths = []
    def find_rec(music_dir: str):
        #print(f"Checking {music_dir}")
        if not os.path.exists(music_dir):
            return
        # Check if path is a music file
        if os.path.isfile(music_dir):
            if music_dir.endswith(('.mp3', '.flac', '.m4a', '.ogg')):
                song_paths.append(music_dir)
            return
        # Check if path is a directory
        if os.path.isdir(music_dir):
            for item in os.listdir(music_dir):
                item_path = os.path.join(music_dir, item)
                find_rec(item_path)
            return
        return
    find_rec(music_dir)
    return [path for path in song_paths if not os.path.isdir(path)]


def calculate_loudness(file_path: str) -> tuple[Optional[float], Optional[float]]:
    loudness = None
    peak = None
    try:
        result = subprocess.run(["r128gain", "-d", file_path], capture_output=True, text=True, check=True)
        output = result.stdout + result.stderr
        loudness_match = re.search(r"loudness\s*=\s*(-?\d+\.\d+)\s*LUFS", output)
        peak_match = re.search(r"sample peak\s*=\s*(-?\d+\.\d+)\s*dBFS", output)
        if loudness_match:
            loudness = float(loudness_match.group(1))
        if peak_match:
            peak = float(peak_match.group(1))
        #print(f"[INFO] Loudness for '{file_path}':\n{loudness} LUFS, Peak: {peak} dBFS")
    except Exception as e:
        pass
        #print(f"[ERROR] Loudness analysis failed for {file_path}: {e}")
    return loudness, peak

def extract_cover(file_path: str) -> str:
    print(f"Try to extract cover from {file_path} ...")
    audio = File(file_path)
    directory = os.path.dirname(file_path)
    image_data = None
    ext = os.path.splitext(file_path)[1].lower()
    
    try:
        if ext == ".flac":
            audio = FLAC(file_path)
            if audio.pictures:
                image_data = audio.pictures[0].data

        elif ext == ".mp3":
            audio = MP3(file_path)
            if audio.tags:
                for tag in audio.tags.values():
                    if hasattr(tag, "FrameID") and tag.FrameID == "APIC":
                        image_data = tag.data
                        break

        elif ext in [".m4a", ".mp4", ".aac"]:
            audio = MP4(file_path)
            if "covr" in audio:
                covr_data = audio["covr"]
                if isinstance(covr_data, list) and len(covr_data) > 0:
                    image_data = bytes(covr_data[0])

        elif ext == ".ogg":
            audio = OggVorbis(file_path)
            if "METADATA_BLOCK_PICTURE" in audio:
                import base64
                b64_data = audio["METADATA_BLOCK_PICTURE"][0]
                raw_data = base64.b64decode(b64_data)
                picture = Picture()
                picture.load(raw_data)
                image_data = picture.data
    except:
        return ""
                
    if image_data:
        cover_path = os.path.join(directory, "cover.jpg")
        try:
            image = Image.open(BytesIO(image_data))
            image.save(cover_path, format="JPEG")
            return cover_path
        except Exception as e:
            return ""
    return ""

def find_cover_art(file_path: str) -> str:
    directory = file_path if os.path.isdir(file_path) else os.path.dirname(file_path)
    #print(f"Try to find cover in {directory}...")
    image_extensions = [".jpg", ".jpeg", ".png", ".webp"]
    preferred_names = ["cover", "folder", "front", "album"]
    any_image = ""
    for fname in os.listdir(directory):
        name, ext = os.path.splitext(fname)
        if ext.lower() in image_extensions:
            if name.lower() in preferred_names:
                return os.path.join(directory, fname)
            any_image = os.path.join(directory, fname)
    if not any_image and not os.path.isdir(file_path):
        return extract_cover(file_path)
    return any_image