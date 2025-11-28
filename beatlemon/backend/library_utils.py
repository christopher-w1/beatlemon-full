from typing import List
import random
from backend.general_utils import _jaccard_index
from backend.model_song import Song
from backend.taste_profile_service import TasteProfileService


def calc_song_similarity(song1: Song, song2: Song) -> float:
    """
    Calculate the similarity between two songs based on their file names.
    :param song1: Path to the first song.
    :param song2: Path to the second song.
    :return: Similarity score between 0 and 1.
    """
    if (song1.file_path == song2.file_path or
        (song1.album == song2.album and 
        song1.album_artist == song2.album_artist)):
        return 1.0
    
    genre_score     = _jaccard_index(song1.genres, song2.genres)
    tag_score       = _jaccard_index(song1.lastfm_tags, song2.lastfm_tags)
    artist_score    = _jaccard_index(song1.other_artists + [song1.album_artist], 
                                     song2.other_artists + [song2.album_artist])
    date_score      = 1 / (max((song1.release_year - song2.release_year)*0.2, 
                               (song2.release_year - song1.release_year)*0.2, 1))
    
    return min(1, max(genre_score, tag_score, artist_score)*date_score)

async def song_recommendations(
    song: Song,
    all_songs: list[Song],
    seed: Song | None = None,
    threshold: float = 0.1,
    number: int = 10,
    scene: str | None = None,
    previous_hashes: list[str] = [],
    user_email: str | None  = None,
    profile_service: TasteProfileService | None = None) -> list[Song]:
    """
    Get weighted random recommendations for a song, considering artist diversity
    and recent playback history.

    - Candidate weight ~ similarity * popularity * seed-similarity (if any)
    - Weight divided by (1 + number of same-artist songs in current playlist)
    - Avoid repeats within last 20 songs unless no other options exist
    """
    previous_songs = [s for s in all_songs if s.hash in previous_hashes]

    # Candidate selection
    candidates = []
    for s in all_songs:
        if s == song or s.duration < 120:
            continue

        base_sim = calc_song_similarity(song, s)
        if base_sim < threshold:
            continue

        seed_sim = max(0.01, calc_song_similarity(seed, s)) if seed else 1.0
        popularity = max(0.01, min(1.0, s.popularity))
        similarity = base_sim * popularity * seed_sim
        candidates.append((s, similarity))

    if not candidates:
        return []

    # Normalize similarity
    max_sim = max([sim for s, sim in candidates if s.album_artist != song.album_artist] + [0.01])
    if max_sim > 0:
        candidates = [(s, sim / max_sim) for s, sim in candidates]

    # Adjust by artist frequency
    def artist_penalty(song_obj: Song):
        count = len([x for x in previous_songs[:10] if x.album_artist == song_obj.album_artist])
        return 1 / max(1, count)

    weighted_candidates = [(s, sim * artist_penalty(s)) for s, sim in candidates]
    if user_email and profile_service:
        dislikes = await profile_service.get_dislikes(user_email)
        weighted_candidates = [(s, sim * await profile_service.guess_likability(
            user_email, s )) for s, sim in weighted_candidates if 
            s.hash not in dislikes]

    # Split between "fresh" and "recently played" songs
    fresh_candidates = [(s, w) for s, w in weighted_candidates if s.hash not in previous_hashes]
    stale_candidates = [(s, w) for s, w in weighted_candidates if s.hash in previous_hashes]

    chosen = []

    # Prefer fresh songs first
    source = fresh_candidates if fresh_candidates else weighted_candidates

    while len(chosen) < number and source:
        songs, weights = zip(*source)
        pick = random.choices(songs, weights=weights, k=1)[0]
        chosen.append(pick)
        # remove picked song from pool
        source = [(s, w) for s, w in source if s != pick]

        # Wenn fresh leer und wir noch Lücken haben → aus stale auffüllen
        if not source and len(chosen) < number and stale_candidates:
            source = stale_candidates
            stale_candidates = []

    return chosen[:number]


import random

def song_recommendations_genre(genre: str,
                               all_songs: list["Song"],
                               threshold: float = 0.2,
                               number: int = 10) -> list["Song"]:
    g = genre.lower()
    candidates = [(s, s.popularity)
                  for s in all_songs if getattr(s, "duration", 0) >= 120
                  and ("pop" in g or not any("pop" in gg for gg in s.genres))
                  and any(g in gg for gg in s.genres)]

    if not candidates:
        return []

    songs, probs = zip(*candidates)
    probs = list(probs)

    total = sum(probs)
    if total <= 0:
        weights = [1.0] * len(songs)
    else:
        weights = [p / total for p in probs] 

    picks = random.choices(songs, weights=weights, k=number)

    recommendations = list(dict.fromkeys(picks))

    if len(recommendations) < number:
        remaining = [s for s in songs if s not in recommendations]
        random.shuffle(remaining)
        recommendations.extend(remaining[:number - len(recommendations)])

    return recommendations[:number]


async def personal_song_recommendations(
    user_email: str, profile_service: "TasteProfileService",
    all_songs: List["Song"], n: int = 10 ) -> List["Song"]:
    """
    Recommend n songs purely from the users taste profile.
    """
    candidates: list[tuple["Song", float]] = []

    for s in all_songs:
        if getattr(s, "duration", 0) < 120:
            continue

        try:
            lik = await profile_service.guess_likability(user_email, s)
        except Exception:
            lik = 1.0

        popularity = getattr(s, "popularity", 0.5)
        try:
            popularity = float(popularity)
        except Exception:
            popularity = 0.5

        popularity = max(0.01, min(1.0, popularity))
        weight = max(0.0, float(lik)) * popularity
        if weight > 0.0:
            candidates.append((s, weight))

    if not candidates:
        return random.sample(all_songs, min(n, len(all_songs)))

    max_w = max(w for _, w in candidates)
    pool = [(s, (w / max_w) if max_w > 0 else 0.0) for s, w in candidates]

    chosen: list["Song"] = []
    artist_counts: dict[str, int] = {}

    while pool and len(chosen) < n:
        adjusted = []
        for s, w in pool:
            count = artist_counts.get(getattr(s, "album_artist", ""), 0)
            adjusted.append((s, w / (1 + count)))

        songs, weights = zip(*adjusted)
        pick = random.choices(songs, weights=weights, k=1)[0]
        chosen.append(pick)

        artist = getattr(pick, "album_artist", "")
        artist_counts[artist] = artist_counts.get(artist, 0) + 1
        pool = [(s, w) for s, w in pool if s is not pick]

    return chosen[:n]