from typing import Optional
from backend.model_song import Song
from backend.model_album import Album
from hashlib import sha256
import difflib

CHAR_REPLACEMENTS = {
    " ": "_",
    "/": "_",
    "\\": "_",
    ":": "_",
    "*": "_",
    "?": "_",
    '"': "_",
    "<": "_",
    ">": "_",
    "|": "_",
    "and": "&",
}

INVALID_NAME_UPDATES = ["various artists", "unkown artist", "unknown", "verschiedene interpreten"]

class Artist:
    def __init__(self, name: str, genres: Optional[list[str]] = None):
        self.hash = sha256(name.encode()).hexdigest()
        self.name = name
        self.genres = genres
        self.play_count = 0
        self.songs: list[Song] = []
        self.albums: list[Album] = []
        
    def to_dict(self) -> dict:
        """
        Convert the artist object to a dictionary representation.
        This method is useful for serialization or saving the artist data to a file.

        Returns:
            dict: _description_
        """
        return {
            "hash": self.hash,
            "name": self.name,
            "genres": self.genres or [],
            "play_count": self.play_count,
            "songs": [song.get_hash() for song in self.songs],
            "albums": [album.hash for album in self.albums]
        }
        
    @classmethod
    def from_dict(cls, data: dict, song_map: dict[str, Song], album_map: dict[str, Album]) -> "Artist":
        """
        Create an Artist object from a dictionary.
        This method is useful for deserializing the artist data from a file.

        Args:
            data (dict): The dictionary containing artist data.
            song_map (dict[str, Song]): A mapping of song hashes to Song objects.
            album_map (dict[str, Album]):  A mapping of album hashes to Album objects.

        Returns:
            Artist: _description_
        """
        artist = cls(name=data.get("name", ""), genres=data.get("genres", []))
        artist.play_count = data.get("play_count", 0)
        artist.hash = data.get("hash", "")

        # Restore song references
        song_hashes = data.get("songs", [])
        artist.songs = [song for song in [song_map.get(h, None) for h in song_hashes] if song]

        # Restore album references
        album_hashes = data.get("albums", [])
        artist.albums = [album_map[h] for h in album_hashes if h in album_map]

        return artist


        
    @staticmethod
    def get_simple_name(name: str) -> str:
        """
        Returns a simplified version of the artist name.
        This method replaces common characters with their simplified versions.
        """
        for key, value in CHAR_REPLACEMENTS.items():
            name = name.replace(key, value)
        return name.lower().strip()
        
    def get_hash(self) -> str:
        """ 
        Returns the hash of the artist. 
        If the hash is not set, it generates a new one based on the artist's name.
        """
        if not self.hash:
            self.hash = sha256(self.name.encode()).hexdigest()
        return self.hash
    
    
    
    def _update_most_common_name(self):
        """
        Update the artist name based on the most common name in the songs.
        """
        if not self.songs:
            return
        names = {}
        for song in self.songs:
            if song.album_artist and str(song.album_artist).lower() not in INVALID_NAME_UPDATES:
                names[song.album_artist] = names.get(song.album_artist, 0) + 1
        max_count = 0
        for name, count in names.items():
            if difflib.SequenceMatcher(None, name, self.name).ratio() > 0.8:
                if count == len(self.songs):
                    self.name = name
                elif count > max_count:
                    self.name = name
                    max_count = count
                
    def update_self(self) -> None:
        """
        Update the artist's metadata based on the songs and albums.
        This method will update the artist's name, genres, and play count based on the songs and albums.
        """
        if not self.songs:
            return
        self.play_count = sum(song.play_count for song in self.songs)
        self._update_most_common_name()
                
    def force_update_name(self, name: str):
        self.name = name
        
    def is_artist_of(self, song: Song) -> bool:
        """
        Check if this artist is the artist of the given song.
        This method checks if the artist's name matches the album artist or any of the other artists in the song.
        It also handles common character replacements to ensure a match.

        Args:
            song (Song): The song to check.

        Returns:
            bool: True if this artist is the artist of the song, False otherwise.
        """
        clean_artist_names = song.album_artist.split(",") if song.album_artist else []
        clean_artist_names += song.other_artists if song.other_artists else []
        clean_artist_names = [self.get_simple_name(name) for name in clean_artist_names]
        
        clean_name = self.name.lower().strip()
        for key, value in CHAR_REPLACEMENTS.items():
            clean_name = clean_name.replace(key, value)
        if clean_name in clean_artist_names:
            return True
        return False
    
    def add_song(self, song: Song):
        """
        Add a song to the artist's list of songs and update the play count.

        Args:
            song (Song): The song to add.
        """
        if not self.songs:
            self.songs = []
        if not song in self.songs:
            self.songs.append(song)
        self.play_count += (song.play_count + song.lastfm_playcount)
        self.genres = list(set(song.genres) | set(self.genres if self.genres else []))
        self._update_most_common_name()

    def __repr__(self):
        return f"Artist(name={self.name}, genre={', '.join(self.genres)})" if self.genres else f"Artist(name={self.name})"