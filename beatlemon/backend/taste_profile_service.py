import os, json, asyncio, hashlib
from collections import defaultdict
from backend.model_song import Song
from backend.library_service import LibraryService
from backend.general_utils import normalize_name as nn

CURRENT_PROFILE_VERSION = 1

class TasteProfileService:
    def __init__(self, library_service: LibraryService,
                 storage_dir: str = "data/taste_profiles"):
        self.storage_dir = storage_dir
        self.library_service = library_service
        os.makedirs(self.storage_dir, exist_ok=True)
        self._likes: dict[str, list[str]] = defaultdict(list)
        self._dislikes: dict[str, list[str]] = defaultdict(list)
        self._profile_pos: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
        self._profile_neg: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
        self._locks: dict[str, asyncio.Lock] = defaultdict(asyncio.Lock)
        self._loaded_users: set[str] = set()
        self._version: dict[str, int] = {} 

    def _get_filename(self, user_email: str) -> str:
        hashed_email = hashlib.sha256(user_email.encode()).hexdigest()
        return os.path.join(self.storage_dir, f"{hashed_email}.json")

    async def _load_user_email(self, user_email: str) -> None:
        filename = self._get_filename(user_email)
        if user_email in self._loaded_users:
            return

        if os.path.exists(filename):
            def read():
                with open(filename, "r", encoding="utf-8") as f:
                    return json.load(f)

            data = await asyncio.to_thread(read)
            self._likes[user_email] = data.get("likes", [])
            self._dislikes[user_email] = data.get("dislikes", [])
            self._profile_pos[user_email] = defaultdict(int, data.get("positive_profile", {}))
            self._profile_neg[user_email] = defaultdict(int, data.get("negative_profile", {}))
            self._version[user_email] = data.get("profile_version", 0)
            if self._version[user_email] != CURRENT_PROFILE_VERSION:
                await self._rebuild_profiles(user_email)

        self._loaded_users.add(user_email)

    async def _rebuild_profiles(self, user_email: str) -> None:
        """Recalculate the profiles from current likes/dislikes."""
        print(f"[TasteProfile] Rebuilding profile for {user_email} (version mismatch)")
        self._profile_pos[user_email].clear()
        self._profile_neg[user_email].clear()

        for h in self._likes[user_email]:
            song = await self.library_service.get_song(h)
            if not song:
                self._likes[user_email].remove(h)
                continue
            self._add_to_profile(self._profile_pos[user_email], song)
        for h in self._dislikes[user_email]:
            song = await self.library_service.get_song(h)
            if not song:
                self._likes[user_email].remove(h)
                continue
            self._add_to_profile(self._profile_neg[user_email], song)

        self._version[user_email] = CURRENT_PROFILE_VERSION
        await self._save_user_email(user_email)

    async def _save_user_email(self, user_email: str) -> None:
        filename = self._get_filename(user_email)

        data = {
            "likes": list(self._likes[user_email]),
            "dislikes": list(self._dislikes[user_email]),
            "positive_profile": dict(self._profile_pos[user_email]),
            "negative_profile": dict(self._profile_neg[user_email]),
            "profile_version": CURRENT_PROFILE_VERSION
        }

        def write():
            with open(filename, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)

        await asyncio.to_thread(write)

    async def like_song(self, user_email: str, song: Song) -> None:
        lock = self._locks[user_email]
        async with lock:
            await self._load_user_email(user_email)

            if song.hash in self._dislikes[user_email]:
                self._dislikes[user_email].remove(song.hash)
                self._remove_from_profile(self._profile_neg[user_email], song)

            if song.hash not in self._likes[user_email]:
                self._likes[user_email].append(song.hash)
                self._add_to_profile(self._profile_pos[user_email], song)
                await self._save_user_email(user_email)

    async def dislike_song(self, user_email: str, song: Song) -> None:
        lock = self._locks[user_email]
        async with lock:
            await self._load_user_email(user_email)

            if song.hash in self._likes[user_email]:
                self._likes[user_email].remove(song.hash)
                self._remove_from_profile(self._profile_pos[user_email], song)

            if song.hash not in self._dislikes[user_email]:
                self._dislikes[user_email].append(song.hash)
                self._add_to_profile(self._profile_neg[user_email], song)
                await self._save_user_email(user_email)

    def _add_to_profile(self, profile: dict[str, int], song: Song) -> None:
        profile[f"artist${nn(song.album_artist)}"] += 10
        profile[f"album${nn(song.album)}"] += 1
        for artist in (set(song.other_artists) - set([song.album_artist])):
            profile[f"artist${nn(artist)}"] += 5
        for genre in song.genres:
            profile[f"genre${nn(genre)}"] += 10

    def _remove_from_profile(self, profile: dict[str, int], song: Song) -> None:
        profile[f"artist${nn(song.album_artist)}"] -= 10
        profile[f"album${nn(song.album)}"] -= 1
        for artist in (set(song.other_artists) - set([song.album_artist])):
            profile[f"artist${nn(artist)}"] -= 5
        for genre in song.genres:
            profile[f"genre${nn(genre)}"] -= 1

        for key in list(profile):
            if profile[key] <= 0:
                del profile[key]

    async def remove_rating(self, user_email: str, song: Song) -> None:
        lock = self._locks[user_email]
        async with lock:
            await self._load_user_email(user_email)
            if song.hash in self._likes[user_email]:
                self._likes[user_email].remove(song.hash)
                self._remove_from_profile(self._profile_pos[user_email], song)
            if song.hash in self._dislikes[user_email]:
                self._dislikes[user_email].remove(song.hash)
                self._remove_from_profile(self._profile_neg[user_email], song)
            await self._save_user_email(user_email)


    async def get_likes(self, user_email: str) -> list[str]:
        await self._load_user_email(user_email)
        return self._likes[user_email]

    async def get_dislikes(self, user_email: str) -> list[str]:
        await self._load_user_email(user_email)
        return self._dislikes[user_email]

    async def get_positive_profile(self, user_email: str) -> dict[str, float]:
        await self._load_user_email(user_email)
        return dict(self._profile_pos[user_email])

    async def get_negative_profile(self, user_email: str) -> dict[str, float]:
        await self._load_user_email(user_email)
        return dict(self._profile_neg[user_email])
    
    async def guess_likability(self, user_email: str, song: Song) -> float:
        await self._load_user_email(user_email)
        pos, neg = self._profile_pos[user_email], self._profile_neg[user_email]
        p_total, n_total = 1, 1
        for artist in song.other_artists + [song.album_artist]:
            p_total += pos.get(f"artist${nn(artist)}", 0)
            n_total += neg.get(f"artist${nn(artist)}", 0)
        for genre in song.genres:
            p_total += pos.get(f"genre${nn(genre)}", 0)
            n_total += neg.get(f"genre${nn(genre)}", 0)
        p_total += pos.get(f"album${nn(song.album)}", 0)
        n_total += neg.get(f"album${nn(song.album)}", 0)
        if n_total > p_total:
            return p_total / n_total # approximates 0
        if p_total > n_total:
            return ((1 - (n_total / p_total)) ** 2 )* 10 # approximates 10
        return 1
    
    async def get_user_rating(self, user_email: str, song: Song) -> str:
        await self._load_user_email(user_email)
        if song.hash in self._likes[user_email]:
            return "like"
        elif song.hash in self._dislikes[user_email]:
            return "dislike"
        else:
            return "dontcare"


