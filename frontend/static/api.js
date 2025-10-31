// ---------------- API Functions ----------------
const parent_url_2 = window.location.href.split('/').slice(0, -1).join('/');
const API_BASE = `${parent_url_2}/api`;

console.log(`api_base=${API_BASE}, parent_url=${parent_url_2}`)

async function apiRegisterUser({ registration_key, email, username, password, lastfm_user }) {
    const response = await fetch(`${API_BASE}/register`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ registration_key, email, username, password, lastfm_user })
    });

    if (!response.ok) {
        const err = await response.json().catch(() => ({}));
        throw new Error(err.detail || `Registration failed with status ${response.status}`);
    }

    return await response.json();
}

async function apiLoginUser({ email, password }) {
    const response = await fetch(`${API_BASE}/login`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, password })
    });

    if (!response.ok) {
        const err = await response.json().catch(() => ({}));
        throw new Error(err.detail || `Login failed with status ${response.status}`);
    }

    return await response.json();
}

async function apiLogoutUser(session_key) {
    const response = await fetch(`${API_BASE}/logout`, {
        method: "POST",
        headers: {
            "Content-Type": "application/json",
            "Authorization": `Bearer ${session_key}`
        }
    });

    if (!response.ok) {
        const err = await response.json().catch(() => ({}));
        throw new Error(err.detail || `Logout failed with status ${response.status}`);
    }

    return await response.json();
}

async function api_search_songs(query, limit = 20) {
    try {
        const response = await fetch(`${API_BASE}/search_songs`, {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify({
                query: query,
                result_limit: limit
            })
        });

        if (!response.ok) {
            const err = await response.json();
            throw new Error(err.detail || "Search failed");
        }

        const data = await response.json();
        const songs = Array.isArray(data) ? data : data.songs;
        console.log(`Search results for "${query}":`, songs);
        return songs || [];
    } catch (error) {
        console.error("Error in api_search_songs:", error);
        return [];
    }
}

function api_get_cover_url(coverHash, size = null) {
    const url = new URL(`${API_BASE}/get_cover_art`);
    url.searchParams.append("cover_hash", coverHash);
    if (size) url.searchParams.append("size", size);
    return url.toString();
}

function api_get_song_url(song_hash) {
    const url = new URL(`${API_BASE}/stream/${song_hash}`);
    return url.toString();
}
    
async function api_get_song_data(songHash) {
    const url = `${API_BASE}/get_song_details`;

    const response = await fetch(url, {
        method: "POST",
        headers: {
            "Content-Type": "application/json"
        },
        body: JSON.stringify({ song_hash: songHash })
    });

    if (!response.ok) {
        throw new Error(`Failed to fetch song data: ${response.status}`);
    }

    const data = await response.json();
    return data.song || {};
}

async function api_get_ping() {
    let sum = 0;
    try {
        for (let i = 0; i < 4; i++) {
            const start = performance.now();
            const response = await fetch(`${API_BASE}/ping`, { method: "GET", cache: "no-store" });
            if (!response.ok) throw new Error(`Ping failed: ${response.status}`);
            const end = performance.now();
            const api_ping = Math.round(end - start);
            console.log(`API ping: ${api_ping} ms`);
            sum += api_ping;
        }
        console.log(`Average ping: ${sum/4} ms`);
        return sum/4;
    } catch (err) {
        console.error("API ping error:", err);
        return 25;
    }
}

async function api_update_session( currentSongHash, currentPlayingIndex,
    playlistHashes, hostPing, playbackTimestamp, sessionId ) {
    const payload = {
        host_ping: hostPing,
        current_song: currentSongHash,
        current_index: currentPlayingIndex,
        playlist: playlistHashes,
        playback_timestamp: playbackTimestamp
    };
    const response = await fetch(`${API_BASE}/session/update/${sessionId}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
    });
    if (!response.ok) {
        throw new Error(`Failed to update session: ${response.status}`);
    }
    console.log(`Session updated: ${payload}`)
    const data = await response.json();
    return data.guest_commands || [];
}

async function apiGetSession(sessionId) {
    const response = await fetch(`${API_BASE}/session/get/${sessionId}`);
    if (!response.ok) {
        throw new Error(`Failed to get session: ${response.status}`);
    }
    return await response.json();
}


async function apiGetRecommendations(songHash, n = 10, songSeed=null, sessionId=null) {
    if (!songHash) throw new Error("songHash is required");

    const url = new URL(`${API_BASE}/recommendations/song/${songHash}`);
    if (songSeed) {
        url.searchParams.append("seed_hash", songSeed);
    }
    if (sessionId) {
        url.searchParams.append("session_id", sessionId);
    }
    const response = await fetch(url.toString());
    if (!response.ok) {
        throw new Error(`Failed to fetch recommendations: ${response.status}`);
    }

    const data = await response.json();
    return data.recommendations || [];
}

async function apiGetRecommendationsGenre(genre) {
    if (!genre) throw new Error("Genre is required");

    const url = new URL(`${API_BASE}/recommendations/genre/${genre}`);

    const response = await fetch(url.toString());
    if (!response.ok) {
        throw new Error(`Failed to fetch recommendations: ${response.status}`);
    }

    const data = await response.json();
    return data.recommendations || [];
}

async function apiGetLyrics(song_hash) {
    if (!song_hash) throw new Error("song_hash is required");
    const sessionKey = localStorage.getItem("session_key");
    if (!sessionKey) throw new Error("No session_key found in localStorage");
    const url = new URL(`${API_BASE}/lyrics/song/${encodeURIComponent(song_hash)}`);

    try {
        const response = await fetch(url.toString(), {
            method: "GET",
            headers: {
                "X-Session": sessionKey
            }
        });

        if (!response.ok) {
            if (response.status === 404) {
                return "<i>No lyrics found.</i>";
            }
            return `<i>Failed to fetch lyrics: ${response.status}</i>`;
        }

        const data = await response.json();
        return data.lyrics || "<i>No lyrics found.</i>";

    } catch (err) {
        console.error("apiGetLyrics error:", err);
        return "<i>Lyrics request failed.</i>";
    }
}

async function apiGetRecommendationsByScene() {
    const url = new URL(`${API_BASE}/recommendations/main-genres/10`);

    const response = await fetch(url.toString());
    if (!response.ok) {
        throw new Error(`Failed to fetch recommendations: ${response.status}`);
    }

    const data = await response.json();
    return data.recommendations || {};
}
