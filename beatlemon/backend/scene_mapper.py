import asyncio
from datetime import date
import re, random
from collections import defaultdict
from time import time
from backend.general_utils import _jaccard_index
from backend.model_song import Song

BASE_GENRE_PATTERNS = {
    r"metal|grind|doom|sludge|thrash|black|death|heavy|viking|metalcore|post hardcore": "metal",
    r"hip[- ]?hop|rap|trap|grime": "rap",
    r"synthwave|dark wave|new wave|synthpop|darkwave|synth rock|post punk|goth|gothic": "gothic",
    r"medieval|mittelalter|folk rock|medieval rock|pagan": "medieval",
    r"rock|punk|grunge|garage|emo|indie rock|psychedelia|alternative": "rock",
    r"industrial|ebm|neue deutsche härte|shock rock|gothic rock|aggrotech": "industrial",
    r"techno|house|trance|idm|edm|dnb|d b|drum and bass|dubstep": "electronic",
    r"classical|baroque|symphony|concerto|romantic": "classical",
    r"jazz|swing|bebop|fusion|big band": "jazz",
    r"blues|soul|funk|r&b|r b|rnb|rhythm and blues": "blues",
    r"folk|country|americana|bluegrass": "folk",
    r"reggae|ska|dub": "reggae",
    r"ambient|drone|new age|soundscape": "ambient",
    r"world|afro|latin|balkan|ethno|tango": "world",
    r"soundtrack|ost|score|filme|videospiele|filmmusik": "soundtrack",
}

POP_PATTERNS = r"pop|hyperpop|k[- ]?pop|charts|wochen|weeks|dance"

class SceneMapper:
    def __init__(self) -> None:
        self.cache_map = {}
        self.lock = asyncio.Lock()

    def map_genre(self, subgenres: list[str]) -> str:
        genres = {}
        n_max = 0
        best_match = "other"
        for subgenre in subgenres:
            s = subgenre.strip().lower()
            for pattern, main_genre in BASE_GENRE_PATTERNS.items():
                if re.search(pattern, s):
                    n = genres.get(main_genre, 0) + 1
                    genres[main_genre] = n
                    if n > n_max:
                        best_match, n_max = main_genre, n
        return best_match


    async def sample_songs_by_scene(self, songs: list[Song], n: int) -> dict[str, list[Song]]:
        scene_to_songs = defaultdict(list)
        
        # handle pop and oldies seperately
        current_date = int(date.today().strftime("%Y"))
        for s in songs:
            if any(re.search(POP_PATTERNS, g) for g in s.genres):
                if s.release_year >= current_date - 30 or not s.release_year:
                    scene_to_songs["pop"].append(s)
                else:
                    scene_to_songs["oldies"].append(s)
                    
        # handle rest
        for song in songs:
            if not hasattr(song, "genres") or not hasattr(song, "popularity"):
                continue
            async with self.lock:
                if not song.hash in self.cache_map:
                    scene = self.map_genre(song.genres)
                    self.cache_map[song.hash] = scene
                else:
                    scene = self.cache_map.get(song.hash, "other")
            scene_to_songs[scene].append(song)

        # choose
        result = {}
        for scene, group in scene_to_songs.items():
            if not group:
                result[scene] = []
                continue

            unique_group = list(set(group))
            result[scene] = []

            for _ in range(min(n, len(unique_group))):
                weights = [max(s.popularity*(1 * _jaccard_index(s.genres, result[scene][-1].genres) > 0
                                            if result[scene] else 1), 0.01) for s in unique_group]
                sampled = random.choices(unique_group, weights=weights, k=1)[0]
                result[scene].append(sampled)
                unique_group.remove(sampled)
                    
        scene_dict_serialized = {
            scene: [song.to_simple_dict() for song in songs]
            for scene, songs in result.items() if len(songs) >= n
        }

        return scene_dict_serialized