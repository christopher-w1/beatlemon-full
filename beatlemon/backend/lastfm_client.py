import requests
from typing import Optional

class LastFMClient:
    API_URL = "http://ws.audioscrobbler.com/2.0/"
    
    def __init__(self, api_key: str):
        self.api_key = api_key

    def get_track_info(self, artist: str, title: str) -> Optional[dict]:
        """
        Get track information from Last.fm API.
        This method will return the track information including playcount and tags.

        Args:
            artist (str): Artist name
            title (str): Song title

        Returns:
            Optional[dict]: Track information including playcount and tags
        """
        params = {
            "method": "track.getInfo",
            "api_key": self.api_key,
            "artist": artist,
            "track": title,
            "format": "json"
        }
        response = requests.get(self.API_URL, params=params)

        if response.status_code != 200:
            #print(f"[ERROR] Last.fm request failed: {response.status_code}")
            return None

        data = response.json()
        if "error" in data:
            #print(f"[ERROR] Last.fm: {data['message']}")
            return None

        return data.get("track")

    def get_playcount(self, artist: str, title: str) -> Optional[int]:
        track_info = self.get_track_info(artist, title)
        if track_info and "playcount" in track_info:
            return int(track_info["playcount"])
        return None

    def get_tags(self, artist: str, title: str) -> list[str]:
        track_info = self.get_track_info(artist, title)
        if not track_info:
            return []

        tags = track_info.get("toptags", {}).get("tag", [])
        return [tag["name"] for tag in tags if "name" in tag]
