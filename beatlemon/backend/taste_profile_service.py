import os, json, asyncio, hashlib
from collections import defaultdict
from backend.model_song import Song

class TasteProfileService:
    def __init__(self, storage_dir: str = "data/taste_profiles"):
        self.storage_dir = storage_dir
        os.makedirs(self.storage_dir, exist_ok=True)
        self._likes: dict[str, list[str]] = defaultdict(list)
        self._dislikes: dict[str, list[str]] = defaultdict(list)
        self._profile_pos: dict[str, dict[str, float]] = defaultdict(lambda: defaultdict(float))
        self._profile_neg: dict[str, dict[str, float]] = defaultdict(lambda: defaultdict(float))
        self._locks: dict[str, asyncio.Lock] = defaultdict(asyncio.Lock)
        self._loaded_users: set[str] = set()

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
            self._profile_pos[user_email] = defaultdict(float, data.get("positive_profile", {}))
            self._profile_neg[user_email] = defaultdict(float, data.get("negative_profile", {}))

        self._loaded_users.add(user_email)

    async def _save_user_email(self, user_email: str) -> None:
        filename = self._get_filename(user_email)

        data = {
            "likes": list(self._likes[user_email]),
            "dislikes": list(self._dislikes[user_email]),
            "positive_profile": dict(self._profile_pos[user_email]),
            "negative_profile": dict(self._profile_neg[user_email]),
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

    def _add_to_profile(self, profile: dict[str, float], song: Song) -> None:
        profile[f"artist${song.album_artist}"] += 1.0
        profile[f"album${song.album}"] += 0.1
        for artist in song.other_artists:
            profile[f"artist${artist}"] += 0.5
        for genre in song.genres:
            profile[f"genre${genre}"] += 1.0

    def _remove_from_profile(self, profile: dict[str, float], song: Song) -> None:
        profile[f"artist${song.album_artist}"] -= 1.0
        profile[f"album${song.album}"] -= 0.1
        for artist in song.other_artists:
            profile[f"artist${artist}"] -= 0.5
        for genre in song.genres:
            profile[f"genre${genre}"] -= 1.0

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
        total_score = 0.0
        total_weight = 0.0
        for artist in song.other_artists + [song.album_artist]:
            p, n = pos.get(f"artist${artist}", 0.0), neg.get(f"artist${artist}", 0.0)
            if p > 0 or n > 0:
                total_score += (p - n) / (p + n)
                total_weight += 1
        for genre in song.genres:
            p, n = pos.get(f"genre${genre}", 0.0), neg.get(f"genre${genre}", 0.0)
            if p > 0 or n > 0:
                total_score += (p - n) / (p + n)
                total_weight += 1
        p, n = pos.get(f"album${song.album}", 0.0), neg.get(f"album${song.album}", 0.0)
        if p > 0 or n > 0:
            total_score += (p - n) / (p + n)
            total_weight += 1
        if total_weight == 0.0:
            return 1.0
        avg_score = total_score / total_weight
        if avg_score < 0:
            return -1.0 / (avg_score - 1.0)
        if avg_score > 0:
            return min(10, 1 + avg_score)
        return 1
    
    async def get_user_rating(self, user_email: str, song: Song) -> str:
        await self._load_user_email(user_email)
        if song.hash in self._likes[user_email]:
            return "like"
        elif song.hash in self._dislikes[user_email]:
            return "dislike"
        else:
            return "dontcare"


