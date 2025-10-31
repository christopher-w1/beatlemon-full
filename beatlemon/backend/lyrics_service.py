import asyncio, json, os, requests, re
from collections import defaultdict, Counter
from typing import Optional

class LyricsService:
    def __init__(self, lyrics_dir: str = "data/lyrics"):
        self.lyrics_dir = lyrics_dir
        self._lyrics: dict[str, str] = {}
        self._locks: dict[str, asyncio.Lock] = defaultdict(asyncio.Lock)
        self._loaded_files: set[str] = set()
        os.makedirs(lyrics_dir, exist_ok=True)

    def _get_filename(self, song_hash: str) -> str:
        return os.path.join(self.lyrics_dir, f"{song_hash[:2].lower()}.json")

    async def get_lyrics(self, song_hash: str, artist: str, title: str) -> Optional[str]:
        if song_hash in self._lyrics:
            return self._lyrics[song_hash]
        filename = self._get_filename(song_hash)
        lock = self._locks[filename]
        async with lock:
            if filename not in self._loaded_files:
                await self._load_file(filename)
                self._loaded_files.add(filename)
            if song_hash in self._lyrics:
                return self._lyrics[song_hash]
            lyrics = await self._fetch_lyrics(artist, title)
            if lyrics:
                lyrics = self.normalize_lyrics(lyrics)
                self._lyrics[song_hash] = lyrics
                await self._save_to_file(filename, song_hash, lyrics)
                return lyrics
            return None

    async def _load_file(self, filename: str) -> None:
        if not os.path.exists(filename):
            return
        try:
            def sync_read():
                with open(filename, "r", encoding="utf-8") as f:
                    return json.load(f)
            data = await asyncio.to_thread(sync_read)
            self._lyrics.update(data)
        except Exception as e:
            print(f"Failed to load {filename}: {e}")

    async def _save_to_file(self, filename: str, song_hash: str, lyrics: str) -> None:
        try:
            def sync_write():
                data = {}
                if os.path.exists(filename):
                    with open(filename, "r", encoding="utf-8") as f:
                        data = json.load(f)
                data[song_hash] = lyrics
                with open(filename, "w", encoding="utf-8") as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
            await asyncio.to_thread(sync_write)
        except Exception as e:
            print(f"Failed to write {filename}: {e}")

    async def _fetch_lyrics(self, artist: str, title: str) -> Optional[str]:
        def fetch():
            try:
                url = f"https://api.lyrics.ovh/v1/{artist}/{title}"
                response = requests.get(url, timeout=10)
                if response.status_code == 200:
                    return response.json().get("lyrics")
            except Exception as e:
                print(f"Fetch failed: {e}")
            return None

        return await asyncio.to_thread(fetch)
    
    def normalize_lyrics(self, text: str) -> str:
        """
        Normalize lyric line spacing depending on detected pattern.
        Detects whether the source uses 1 or 2 line breaks between lines
        and preserves stanza separation accordingly.
        """
        text = text.replace("\r\n", "\n").strip()

        parts = re.split(r'(\n+)', text)
        breaks = [p for p in parts if p.startswith("\n")]
        counts = [len(b) for b in breaks]

        most_common = Counter(counts).most_common(1)
        common_breaks = most_common[0][0] if most_common else 1

        if common_breaks <= 1:
            text = re.sub(r'\n{3,}', '\n\n', text)
            text = re.sub(r'[ \t]+\n', '\n', text)
            text = re.sub(r'\n[ \t]+', '\n', text)
        else:
            text = re.sub(r'\n{4,}', '\n\n\n', text)
            text = re.sub(r'(?<!\n)\n{3}(?!\n)', '\n\n', text)
            
        return text.strip()

if __name__=="__main__":
    async def main():
        service = LyricsService()
        lyrics = await service.get_lyrics("AABBCCDD1122", "Slipknot", "Unsainted")
        if lyrics:
            print(lyrics[:300])
        else:
            print("Lyrics not found.")

    asyncio.run(main())