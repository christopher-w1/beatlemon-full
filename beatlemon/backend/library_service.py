import asyncio
from backend.library_utils import scan_library
from backend.model_album import Album
from backend.model_song import Song
from backend.model_artist import Artist
from hashlib import sha256

from config import Config

def editing_distance(s1: str, s2: str) -> int:
    if len(s1) < len(s2):
        return editing_distance(s2, s1)

    if len(s2) == 0:
        return len(s1)

    previous_row = range(len(s2) + 1)
    for i, c1 in enumerate(s1):
        current_row = [i + 1]
        for j, c2 in enumerate(s2):
            insertions = previous_row[j + 1] + 1
            deletions = current_row[j] + 1
            substitutions = previous_row[j] + (c1 != c2)
            current_row.append(min(insertions, deletions, substitutions))
        previous_row = current_row
    return previous_row[-1]

class LibraryService:
    def __init__(self, config: Config):
        self.library_snapshot: tuple[list[Song], list[Album], list[Artist]] = ([], [], [])
        self.song_map: dict[str, Song] = {}
        self.cover_map: dict[str, str] = {}
        self.album_map: dict[str, Album] = {}
        self.artist_map: dict[str, Artist] = {}
        self.config = config
        self._lock = asyncio.Lock()
        self._task = None

    async def start_background_task(self):
        if self._task is None:
            self._task = asyncio.create_task(self._periodic_scan())

    async def _periodic_scan(self):
        while True:
            print("Starting library scan in background thread...")
            snapshot = await asyncio.to_thread(scan_library, self.config.lastfm_api_key, self.config.music_dir)
            print("Scan finished.")
            async with self._lock:
                self.library_snapshot = snapshot
                self.song_map = {song.get_hash(): song for song in snapshot[0]}
                self.cover_map = {sha256(str(song.cover_art).encode()).hexdigest(): 
                    song.cover_art for song in snapshot[0]}
                self.album_map = {album.hash: album for album in snapshot[1]}
                self.artist_map = {artist.name: artist for artist in snapshot[2]}
            await asyncio.sleep(600)

    async def get_snapshot(self):
        async with self._lock:
            return self.library_snapshot or ([], [], [])
        
    async def has_song(self, song_hash: str) -> bool:
        return song_hash in self.song_map
    
    async def get_song(self, song_hash: str) -> Song | None:
        return self.song_map.get(song_hash, None)
    
    async def get_song_by_string(self, metadata: str) -> Song | None:
        async with self._lock:
            for song in self.library_snapshot[0]:
                song_string = f"{song.get_artists} | {song.album} | {song.track_number} | {song.title}"
                song_string_2 = f"{song.get_artists} - {song.title} ({song.track_number} on {song.album})"
                if song_string == metadata or song_string_2 == metadata:
                    return song
        return None
    
    async def get_song_by_metadata(self, metadata: dict[str, str]) -> Song | None:
        artist = metadata.get("artist", None)
        album = metadata.get("album", None)
        title = metadata.get("title", None)
        track_number = metadata.get("track_number", None)
        match = None
        async with self._lock:
            matches = [
                song for song in self.library_snapshot[0]
                if (artist is None or artist in song.get_artists()) and
                   (album is None or song.album == album) and
                   (title is None or song.title == title) and
                   (track_number is None or song.track_number == track_number)
            ]
            if matches:
                match = matches[0]
        return match
    
    async def search_song(self, search_term: str) -> list[Song]:
        async with self._lock:
            matches: list[tuple[float, Song]] = []
            for song in self.library_snapshot[0]:
                song_string = f"{song.get_artists} - {song.title} ({song.track_number} on {song.album})"
                jaccard_value = len(set(song_string.lower().split()) & set(search_term.lower().split())) / min(1, len(set(song_string.lower().split()) | set(search_term.lower().split())))
                if jaccard_value > 0:
                    matches.append((jaccard_value, song))
            return [song for _, song in sorted(matches, key=lambda x: x[0], reverse=True)]
    
    async def get_album(self, album_hash: str) -> Album | None:
        return self.album_map.get(album_hash, None)
    
    async def get_artist(self, artist_name: str) -> Artist | None:
        async with self._lock:
            for artist in self.library_snapshot[2]:
                if artist.name == artist_name:
                    return artist
        return None
