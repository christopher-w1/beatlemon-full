import asyncio
import os
import msgpack
import time
from backend.model_album import Album
from backend.model_song import Song
from backend.model_artist import Artist
from hashlib import sha256
from tqdm import tqdm
from typing import List, Tuple
from concurrent.futures import ProcessPoolExecutor, as_completed
from backend.lastfm_client import LastFMClient
from backend.filesys_utils import calculate_loudness
from backend.model_song import Song
from backend.model_album import Album
from backend.model_artist import Artist
from backend.filesys_utils import find_song_paths
from backend.wikicrawler import get_band_genres
from config import Config

VARIOUS_TERMS = ["various artists", "verschiedene interpreten", "verschiedene künstler", "various"]

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


def save_msgpack(path: str, data):
    """Write Python object to a .msgpack file."""
    with open(path, "wb") as f:
        msgpack.pack(data, f, use_bin_type=True)


def load_msgpack(path: str):
    """Read Python object from a .msgpack file."""
    with open(path, "rb") as f:
        msg = msgpack.unpack(f, raw=False)
        return msg if isinstance(msg, list) else []


def fetch_lastfm_data_minimal(args: Tuple[str, str, str, str]) -> Tuple[str, int, List[str]]:
    song_id, artist, title, api_key = args
    client = LastFMClient(api_key)
    info = client.get_track_info(artist, title)
    if not info:
        return (song_id, 0, [])
    
    try:
        playcount = int(info.get("playcount", 0))
    except:
        playcount = 0

    tags_raw = info.get("toptags", {}).get("tag", [])
    if isinstance(tags_raw, dict):
        tags_raw = [tags_raw]
    tags = [t.get("name", "").strip() for t in tags_raw if t.get("name")]

    return (song_id, playcount, tags)


def update_lastfm_serial_with_throttling(lastfm_api_key: str, songs: List[Song], delay_per_request: float = 0.25) -> None:
    """
    Get Last.fm data for a list of songs with throttling.
    :param songs: List of Song objects to update.
    """

    id_map = {}
    tasks = []

    for song in songs:
        song_id = str(song.file_path)
        artists = [a for a in song.other_artists + [song.album_artist] if a not in VARIOUS_TERMS] or ["Various Artists"]
        title = song.title

        if artists and title:
            id_map[song_id] = song
            tasks.append((song_id, artists, title, lastfm_api_key))

    for args in tqdm(tasks, desc="Fetching LastFM data", unit="song"):
        song_id, artists, title, lastfm_api_key = args
        playcount, tags = None, None
        for artist in artists:
            start_time = time.time()
            _, playcount, tags = fetch_lastfm_data_minimal((song_id, artist, title, lastfm_api_key))
            if not playcount:
                _, playcount, tags = fetch_lastfm_data_minimal((song_id, Artist.get_simple_name(artist), str(title).split("(")[0].strip(), lastfm_api_key))

            song = id_map.get(song_id)
            if song:
                song.lastfm_playcount = playcount
                song.lastfm_tags = tags
                song.additional_data["lastfm_update"] = "success" if playcount else "fail"

            time_taken = time.time() - start_time
            if time_taken < delay_per_request:
                time.sleep(delay_per_request - time_taken)
          
    
def init_library():
    is_new = False
    if not os.path.exists("data"):
        print("Creating library directory...")
        os.makedirs("data", exist_ok=True)
        is_new = True
    # Make json files if they don't exist
    if not os.path.exists("data/songs.msgpack"):
        with open("data/songs.msgpack", "w", encoding="utf-8") as f:
            save_msgpack("data/songs.msgpack", [])
        is_new = True
    if not os.path.exists("data/albums.msgpack"):
        with open("data/albums.msgpack", "w", encoding="utf-8") as f:
            save_msgpack("data/albums.msgpack", [])
        is_new = True
    if not os.path.exists("data/artists.msgpack"):
        with open("data/artists.msgpack", "w", encoding="utf-8") as f:
            save_msgpack("data/artists.msgpack", [])
        is_new = True
    return is_new


def load_library() -> tuple[list[Song], list[Album], list[Artist]]:
    print("Loading library from ./data...")
    
    # Check if the output directory exists
    if init_library():
        return [], [], []

    # SONGS
    song_dicts = load_msgpack("data/songs.msgpack")
    song_objects = [Song.from_dict(d) for d in tqdm(song_dicts, desc="Loading Songs")]
    song_map = {s.get_hash(): s for s in song_objects}
    print(f"✓ Loaded {len(song_objects)} songs")

    # ALBUMS
    album_dicts = load_msgpack("data/albums.msgpack")
    album_objects = [Album.from_dict(d, song_map) for d in tqdm(album_dicts, desc="Loading Albums")]
    album_map = {a.hash: a for a in album_objects}
    print(f"✓ Loaded {len(album_objects)} albums")

    # ARTISTS
    artist_dicts = load_msgpack("data/artists.msgpack")
    artist_objects = [Artist.from_dict(d, song_map, album_map) for d in tqdm(artist_dicts, desc="Loading Artists")]
    print(f"✓ Loaded {len(artist_objects)} artists")

    print("✓ Library successfully loaded.")

    return song_objects, album_objects, artist_objects


def scan_library(lastfm_api_key: str, music_dir: str, verbose: bool = False) -> tuple[list[Song], list[Album], list[Artist]]:

    was_updated = False

    # Load existing library
    existing_songs, existing_albums, existing_artists = load_library()
    existing_song_map = {s.get_hash(): s for s in existing_songs}
    existing_paths = {str(s.file_path) for s in existing_songs}

    # Scan new files
    song_paths = find_song_paths(music_dir)
    print(f"Scanning {len(song_paths)} songs from disk...")

    updated_songs: list[Song] = []
    new_songs: list[Song] = []

    for i, song_path in enumerate(song_paths):
        if song_path in existing_paths:
            # Existing file -> skip analysis
            existing_song = next(s for s in existing_songs if str(s.file_path) == song_path)
            updated_songs.append(existing_song)
        else:
            # New file -> create new Song object
            new_song = Song(song_path, skip_analysis=True)
            is_new = True
            was_updated = True
            # Check if the song already exists in the library and was moved
            for existing_song in existing_songs:
                if new_song.get_hash() == existing_song.get_hash():
                    print(f"Song {new_song.file_path} already exists in library as {existing_song.file_path}")
                    print(f"Assuming the song was moved, updating file path...")
                    existing_song.file_path = new_song.file_path
                    existing_songs.remove(existing_song)
                    updated_songs.append(existing_song)
                    is_new = False
                    break
            if is_new:
                new_songs.append(new_song)
                updated_songs.append(new_song)

        if verbose:
            print(f"[{i + 1}/{len(song_paths)}] {song_path} {'(new)' if song_path not in existing_paths else ''}")

          
    # Remove songs that were deleted
    for existing_song in existing_songs:
        if str(existing_song.file_path) not in song_paths:
            print(f"Song {existing_song.file_path} was deleted")
            updated_songs.remove(existing_song)
            was_updated = True
            
    if was_updated:
        with open("data/songs.msgpack", "w", encoding="utf-8") as f:
            save_msgpack("data/songs.msgpack", [s.to_dict() for s in updated_songs])
            
    # Calculate loudness and peak for songs without analysis
    songs_to_analyze = [s for s in updated_songs if not s.loudness]
    if songs_to_analyze:
        print(f"Calculating loudness for {len(songs_to_analyze)} songs...")
        was_updated = False
        futures = {}
        
        with ProcessPoolExecutor() as executor:
            for song in songs_to_analyze:
                future = executor.submit(calculate_loudness, str(song.file_path))
                futures[future] = song

            for future in tqdm(as_completed(futures), total=len(futures), desc="Analyzing loudness"):
                song = futures[future]
                try:
                    loudness, peak = future.result()
                    if loudness is not None:
                        song.loudness = loudness
                        song.peak = peak
                    was_updated = True
                except Exception as e:
                    pass

        if was_updated:
            save_msgpack("data/songs.msgpack", [s.to_dict() for s in updated_songs])
    
    
    song_without_lastfm = [s for s in updated_songs if not s.lastfm_playcount and not s.additional_data.get("lastfm_update", False)]
    if song_without_lastfm:
        print(f"Updating Last.fm data for {len(song_without_lastfm)} songs...")
        update_lastfm_serial_with_throttling(lastfm_api_key, song_without_lastfm)
        was_updated = True

    songs_without_wiki = [s for s in updated_songs if not s.additional_data.get("wiki_update", False)]
        
    if not was_updated and not songs_without_wiki:
        print("Library is up to date. No changes detected.")
        return existing_songs, existing_albums, existing_artists
    
    if songs_without_wiki:
        artist_genre_map = {}
        for song in songs_without_wiki:
            for a in ([song.album_artist] + song.other_artists):
                if a.lower() in VARIOUS_TERMS: continue
                artist_name = Artist.get_simple_name(a)
                artist_genre_map[artist_name] = []
        print(f"Updating genre tags for {len(songs_without_wiki)} songs...")
        for artist_name in tqdm(artist_genre_map.keys(), desc="Processed artists"):
            artist_genre_map[artist_name] = get_band_genres(artist_name)
        for song in tqdm(songs_without_wiki, desc="Processed songs"):
            song_genres = set()
            for a in ([song.album_artist] + song.other_artists):
                if a.lower() in VARIOUS_TERMS: continue
                artist_name = Artist.get_simple_name(a)
                song_genres = song_genres.union(set(artist_genre_map.get(artist_name, [])))
            if song_genres:
                song.genres = list(song_genres)
            song.additional_data['wiki_update'] = True
                
    # Map songs to albums
    album_paths = list(set(os.path.dirname(path) for path in song_paths))
    album_objects: list[Album] = []
    for album_path in album_paths:
        album = Album(album_path)
        songs_in_album = [
            s for s in updated_songs
            if album_path.lower().replace("\\", "/") in str(s.file_path).lower().replace("\\", "/")
        ]
        for song in songs_in_album:
            album.add_song(song)
        album_objects.append(album)
    album_map = {a.hash: a for a in album_objects}
    
    # Guess loudness and peak for songs without analysis
    for album in album_objects:
        if album.loudness:
            for song in album.songs:
                if not song.loudness:
                    song.loudness = album.loudness
                if not song.peak:
                    song.peak = album.peak

    # Map songs to artists
    print("Mapping songs to artists...")
    artist_dict: dict[str, Artist] = {}
    for song in tqdm(updated_songs, desc="Processed songs"):
        for artist_name in [song.album_artist] + song.other_artists:
            if artist_name:
                simple_name = Artist.get_simple_name(artist_name)
                if simple_name not in artist_dict.keys():
                    #print("Adding artist", artist_name, f"because {simple_name} not in dict")
                    artist_dict[simple_name] = Artist(artist_name)
                artist_dict[simple_name].add_song(song)
    artist_objects = list(artist_dict.values())
    print(f"{len(artist_objects)} artists found | Dictionary size: {len(artist_dict)}")

    # Map albums to artists
    print("Mapping albums to artists...")
    for artist in tqdm(artist_objects, desc="Processed artists"):
        for album in album_objects:
            for song in album.songs:
                if song.play_count or song.lastfm_playcount:
                    song.popularity = (song.play_count + song.lastfm_playcount) / max(1, artist.play_count)
                if song in artist.songs and album not in artist.albums:
                    artist.albums.append(album)

    # Speichern
    print("Saving updated library...")
    os.makedirs("output", exist_ok=True)
    save_msgpack("data/songs.msgpack", [s.to_dict() for s in updated_songs])
    save_msgpack("data/albums.msgpack", [a.to_dict() for a in album_objects])
    save_msgpack("data/artists.msgpack", [a.to_dict() for a in artist_objects])
    print(f"✓ Library updated successfully with {len(new_songs)} new songs.")
    return updated_songs, album_objects, artist_objects

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
            lastfm_key, music_dir = self.config.lastfm_api_key, self.config.music_dir
            snapshot = await asyncio.to_thread(scan_library, lastfm_key, music_dir)
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
