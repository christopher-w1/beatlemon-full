import os, hashlib, re
from mutagen import File # type: ignore
from mutagen.mp3 import MP3
from mutagen.flac import FLAC
from mutagen.mp4 import MP4, MP4Tags
from mutagen.oggvorbis import OggVorbis
from datetime import datetime
from backend.filesys_utils import find_cover_art, calculate_loudness
from hashlib import sha256

VARIOUS_ARTISTS = [
    "various artists",
    "verschiedene interpreten",
    "verschiedene künstler"
]

class Song:
    def __init__(self, file_path: str = "", skip_analysis: bool = False):
        self.file_path = file_path
        self.track_number = 0
        self.disc_number = 0
        self.title = ""
        self.album_artist = ""
        self.other_artists = []
        self.album = ""
        self.duration = 0
        self.release_year = 0
        self.genres = []
        self.play_count = 0
        self.popularity = 0.5
        self.last_played = ""
        self.lyrics = ""
        self.explicit = False
        self.bitrate = 0
        self.format = ""
        self.file_size = 0
        self.cover_art = ""
        self.loudness = 0
        self.peak = 0
        self.lastfm_playcount = 0
        self.lastfm_tags = []
        self.hash = ""
        self.additional_data = {}

        if not file_path:
            return
        print(f"Scanning file: {self.file_path}")

        self.file_size = os.path.getsize(file_path)
        audio = File(file_path, easy=True)
        raw = File(file_path)

        ext = os.path.splitext(file_path)[1].lower()
        self.format = ext[1:]  # "mp3", "flac", etc.

        if ext == ".mp3":
            metadata = MP3(file_path)
        elif ext == ".flac":
            metadata = FLAC(file_path)
        elif ext == ".m4a":
            metadata = MP4(file_path)
        elif ext == ".ogg":
            metadata = OggVorbis(file_path)
        else:
            raise ValueError("Unsupported file format")

        if not metadata or not metadata.info:
            raise ValueError("Could not read metadata")

        if hasattr(metadata.info, 'bitrate') and metadata.info.bitrate: # type: ignore
            self.bitrate = int(metadata.info.bitrate) // 1024 # type: ignore
        elif self.duration and self.duration > 0:
            self.bitrate = int((self.file_size * 8) / self.duration) // 1024

        if raw and hasattr(raw, 'info') and hasattr(metadata.info, 'length'):
            self.duration = int(raw.info.length)

        if not audio:
            raise ValueError("Could not read audio file")

        def _get_tag_entry(tags, key, default=""):
            try:
                return tags.get(key, [default])[0]
            except Exception:
                return default

        def _get_tag_list(tags, key) -> list:
            try:
                return tags.get(key, [])
            except Exception:
                return []

        if ext == ".m4a" and type(metadata.tags) == MP4Tags:
            tags = metadata.tags or {}
            self.title = _get_tag_entry(tags, "\xa9nam")
            self.album = _get_tag_entry(tags, "\xa9alb")
            self.album_artist = _get_tag_entry(tags, "aART") or _get_tag_entry(tags, "\xa9ART")
            artists = _get_tag_list(tags, "\xa9ART")
            self.other_artists = artists if len(artists) > 1 else _get_tag_list(tags, "aART") + artists
            self.genres = _get_tag_list(tags, "\xa9gen")
            date = _get_tag_entry(tags, "\xa9day", "0")
            self.release_year = int(date[:4]) if date else 0
            self.lyrics = _get_tag_entry(tags, "\xa9lyr")
            track_info = _get_tag_list(tags, "trkn")
            self.track_number = track_info[0][0] if track_info else 0
            disc_info = _get_tag_list(tags, "disk")
            self.disc_number = disc_info[0][0] if disc_info else 0
        else:
            tags = audio.tags or {}
            self.title = _get_tag_entry(tags, "title")
            self.album = _get_tag_entry(tags, "album")
            self.album_artist = _get_tag_entry(tags, "albumartist") or _get_tag_entry(tags, "artist")
            self.other_artists = tags.get("artist", [_get_tag_list(tags, "albumartist")])
            self.genres = _get_tag_list(tags, "genre")
            date = _get_tag_entry(tags, "date", "0")
            self.release_year = int(date[:4]) if date else 0
            self.lyrics = _get_tag_entry(tags, "lyrics")
            track_str = _get_tag_entry(tags, "tracknumber", "0")
            self.track_number = int(track_str.split("/")[0]) if track_str else 0
            disc_str = _get_tag_entry(tags, "discnumber", "0")
            self.disc_number = int(disc_str.split("/")[0]) if disc_str else 0

        split_pattern = r',|;|/| feat\.? '
        self.other_artists = list({
            artist.strip()
            for entry in self.other_artists
            for artist in re.split(split_pattern, entry)
            if artist.strip() and artist.strip() != "Various Artists"
        })

        self.get_hash()

        if "explicit" in tags:
            self.explicit = _get_tag_entry(tags, "explicit").lower() in ["1", "true", "yes"]
        elif "lyrics" in tags and "explicit" in _get_tag_entry(tags, "lyrics", "").lower():
            self.explicit = True

        self.play_count = 0
        self.last_played = datetime.now().isoformat()
        self.cover_art = find_cover_art(file_path)

        if not skip_analysis:
            self.update_loudness()

    def update_loudness(self):
        self.loudness, self.peak = calculate_loudness(self.file_path)

    def check_file(self) -> bool:
        if not os.path.exists(self.file_path):
            print(f"[ERROR] File does not exist: {self.file_path}")
            return False
        if not os.access(self.file_path, os.R_OK):
            print(f"[ERROR] File is not readable: {self.file_path}")
            return False
        return True

    def file_changed(self) -> bool:
        if not self.check_file():
            return False
        current_size = os.path.getsize(self.file_path)
        if current_size != self.file_size:
            print(f"[INFO] File size changed for {self.file_path}: {self.file_size} -> {current_size}")
            self.file_size = current_size
            return True
        return False

    def add_genres(self, genres: list[str]):
        self.genres.extend(genres)
        self.genres = list(set(self.genres))

    def inc_play_count(self):
        self.play_count += 1
        self.last_played = datetime.now().isoformat()

    def maximize_play_count(self, play_count: int):
        self.play_count = max(play_count, self.play_count)
        self.last_played = datetime.now().isoformat()

    def get_genres(self) -> str:
        return ", ".join(self.genres) if self.genres else "Unknown Genre"

    def get_artists(self) -> str:
        various = False
        artists = []
        for artist in [self.album_artist] + self.other_artists:
            if artist.lower().strip() in VARIOUS_ARTISTS:
                various = True
            elif len(artist) > 2:
                artists.append(artist)
        return ", ".join(list(set(artists))) if artists else (
            "Various Artists" if various else "Unknown Artist")

    def get_title(self) -> str:
        return self.title if self.title else "Unknown Title"

    def to_dict(self) -> dict:
        return {
            "file_path": self.file_path,
            "track_number": self.track_number,
            "disc_number": self.disc_number,
            "title": self.title,
            "album_artist": self.album_artist,
            "other_artists": self.other_artists,
            "artists": self.get_artists(),
            "album": self.album,
            "duration": self.duration,
            "release_year": self.release_year,
            "genres": self.genres,
            "play_count": self.play_count,
            "popularity": self.popularity,
            "last_played": self.last_played,
            "lyrics": self.lyrics,
            "explicit": self.explicit,
            "bitrate": self.bitrate,
            "format": self.format,
            "file_size": self.file_size,
            "cover_art": self.cover_art,
            "cover_hash": sha256(str(self.cover_art).encode()).hexdigest(),
            "loudness": self.loudness,
            "peak": self.peak,
            "lastfm_playcount": self.lastfm_playcount,
            "lastfm_tags": self.lastfm_tags,
            "hash": self.hash,
            "additional_data": self.additional_data
        }
        
    def to_simple_dict(self) -> dict:
        return {
            "hash": self.hash,
            "title": self.title,
            "artists": self.get_artists(),
            "album": self.album,
            "track_number": self.track_number,
            "disc_number": self.disc_number,
            "duration": self.duration,
            "release_year": self.release_year,
            "genres": self.genres,
            "play_count": self.play_count + self.lastfm_playcount,
            "lyrics": self.lyrics,
            "cover_hash": sha256(str(self.cover_art).encode()).hexdigest(),
            "loudness": self.loudness,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Song":
        song = cls()
        song.file_path = data.get("file_path", "")
        song.track_number = data.get("track_number", 0)
        song.disc_number = data.get("disc_number", 0)
        song.title = data.get("title", "")
        song.album_artist = data.get("album_artist", "")
        song.other_artists = data.get("other_artists", [])
        song.album = data.get("album", "")
        song.duration = data.get("duration", 0)
        song.release_year = data.get("release_year", 0)
        song.genres = data.get("genres", [])
        song.play_count = data.get("play_count", 0)
        song.popularity = data.get("popularity", 0.5)
        song.last_played = data.get("last_played", "")
        song.lyrics = data.get("lyrics", "")
        song.explicit = data.get("explicit", False)
        song.bitrate = data.get("bitrate", 0)
        song.format = data.get("format", "")
        song.file_size = data.get("file_size", 0)
        song.cover_art = data.get("cover_art", "")
        song.loudness = data.get("loudness", 0)
        song.peak = data.get("peak", 0)
        song.lastfm_playcount = data.get("lastfm_playcount", 0)
        song.lastfm_tags = data.get("lastfm_tags", [])
        song.hash = data.get("hash", "")
        song.additional_data = data.get("additional_data", {})
        song._fix_genres()
        return song

    def _fix_genres(self):
        if not self.genres:
            return
        fixed = []
        for genre in self.genres:
            parts = re.split(r'[,&/;]| and |\s+\|\s+|\s+/\s+|\s+-\s+', genre)
            fixed.extend(part.strip() for part in parts if part.strip())
        self.genres = sorted(set(fixed), key=fixed.index)

    def pretty_print(self):
        print(f"File Path: {self.file_path}")
        print(f"Title: {self.title}")
        print(f"Album: {self.album}")
        print(f"Track Number: {self.track_number}")
        print(f"Artist: {self.get_artists()}")
        print(f"Duration: {self.duration} seconds")
        print(f"Release Year: {self.release_year}")
        print(f"Genres: {', '.join(self.genres)}")
        print(f"Play Count: {self.play_count}")
        print(f"Last Played: {self.last_played}")
        print(f"Loudness: {self.loudness} LUFS")
        print(f"Peak: {self.peak} dBFS")
        print(f"Bitrate: {self.bitrate} kbps")
        print(f"Format: {self.format}")

    def get_hash(self) -> str:
        if not self.hash:
            self.hash = hashlib.sha256(
                (f"{self.get_artists()}|{self.album}|{self.disc_number}.{self.track_number}|{self.title}").encode()
            ).hexdigest()
        return self.hash

    def __str__(self):
        return f"{self.title} by {self.album_artist} from the album {self.album} ({self.duration} seconds)"