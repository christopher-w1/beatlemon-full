// ---------------- API Base ----------------
const DOC_DIR = new URL(".", window.location.href);
const API_BASE = new URL("./api/", DOC_DIR).toString().replace(/\/$/, "");
console.log("API_BASE:", API_BASE);

// ---------------- Utilities ----------------
const DEFAULT_TIMEOUT_MS = 10000;

function getSessionKeyOrThrow() {
  const key = localStorage.getItem("session_key");
  if (!key) throw new Error("Missing session_key (not logged in)");
  return key;
}

function getSessionIdOrThrow() {
  const id = localStorage.getItem("session_id");
  if (!id) throw new Error("Missing session_id (not logged in)");
  return id;
}

function authHeaders() {
  try {
    const token = getSessionKeyOrThrow();
    return { Authorization: `Bearer ${token}` };
  } catch {
    return {};
  }
}

async function request(path, {
  method = "GET",
  query = null,
  body = undefined,
  headers = {},
  timeoutMs = DEFAULT_TIMEOUT_MS,
  cache = "no-store"
} = {}) {
  const controller = new AbortController();
  const t = setTimeout(() => controller.abort(), timeoutMs);

  try {
    const url = new URL(path, API_BASE + "/");
    if (query && typeof query === "object") {
      for (const [k, v] of Object.entries(query)) {
        if (v !== undefined && v !== null) url.searchParams.set(k, String(v));
      }
    }

    const init = {
      method,
      headers: {
        ...("Content-Type" in headers || body === undefined ? {} : { "Content-Type": "application/json" }),
        ...authHeaders(),
        ...headers,
      },
      cache,
      signal: controller.signal,
    };
    if (body !== undefined) {
      init.body = typeof body === "string" ? body : JSON.stringify(body);
      if (!("Content-Type" in init.headers)) {
        init.headers["Content-Type"] = "application/json";
      }
    }

    const res = await fetch(url.toString(), init);
    const ct = res.headers.get("content-type") || "";
    const isJson = ct.includes("application/json");

    if (!res.ok) {
      let detail = "";
      try {
        detail = isJson ? JSON.stringify(await res.json()) : await res.text();
      } catch {
        /* ignore */
      }
      const msg = detail ? detail : `HTTP ${res.status}`;
      throw new Error(`Request failed: ${method} ${url.pathname} → ${msg}`);
    }
    if (isJson) return await res.json();
    return await res.text();
  } finally {
    clearTimeout(t);
  }
}

// ---------------- Revised API calls ----------------
async function apiRegisterUser({ registration_key, email, username, password, lastfm_user }) {
  return await request("register", {
    method: "POST",
    body: { registration_key, email, username, password, lastfm_user }
  });
}

async function apiLoginUser({ email, password }) {
  const data = await request("login", {
    method: "POST",
    body: { email, password }
  });
  if (data?.session_key) {
    localStorage.setItem("session_key", data.session_key);
  }
  return data;
}

async function apiLogoutUser() {
  const data = await request("logout", { method: "POST" });
  localStorage.removeItem("session_key");
  return data;
}

async function api_search_songs(query, limit = 20) {
  const data = await request("search_songs", {
    method: "POST",
    body: { query, result_limit: limit }
  });
  const songs = Array.isArray(data) ? data : data?.songs;
  console.log(`Search results for "${query}":`, songs);
  return songs || [];
}

function api_get_cover_url(coverHash, size = null) {
  const url = new URL("get_cover_art", API_BASE + "/");
  url.searchParams.set("cover_hash", coverHash);
  if (size) url.searchParams.set("size", size);
  return url.toString();
}

function api_get_song_url(song_hash) {
  return new URL(`stream/${encodeURIComponent(song_hash)}`, API_BASE + "/").toString();
}

async function api_get_song_data(songHash) {
  const data = await request("get_song_details", {
    method: "POST",
    body: { song_hash: songHash }
  });
  return data?.song || {};
}

async function api_get_ping({ rounds = 5, timeoutMs = 500 } = {}) {
  const samples = [];
  for (let i = 0; i < rounds; i++) {
    const controller = new AbortController();
    const t = setTimeout(() => controller.abort(), timeoutMs);
    try {
      const t0 = performance.now();
      const res = await fetch(`${API_BASE}/ping`, { method: "GET", cache: "no-store", signal: controller.signal });
      if (!res.ok) throw new Error(`Ping failed: ${res.status}`);
      const dt = performance.now() - t0;
      samples.push(dt);
    } catch (e) {
      console.warn("Ping sample failed:", e?.message || e);
    } finally {
      clearTimeout(t);
    }
  }
  if (samples.length === 0) {
    console.warn("No successful ping samples; falling back to 25 ms");
    return 25;
  }
  const sorted = samples.slice().sort((a, b) => a - b);
  let median;
  const n = sorted.length;
  if (n % 2 === 1) {
    median = sorted[(n - 1) >> 1];
  } else {
    median = (sorted[n / 2 - 1] + sorted[n / 2]) / 2;
  }
  const result = Math.round(median);
  console.log(`Ping samples: ${samples.map(v => Math.round(v)).join(", ")} → median=${result} ms`);
  return result;
}


async function api_update_session(currentSongHash, currentPlayingIndex,
  playlistHashes, hostPing, playbackTimestamp, sessionId) {
  const payload = {
    host_ping: hostPing,
    current_song: currentSongHash,
    current_index: currentPlayingIndex,
    playlist: playlistHashes,
    playback_timestamp: playbackTimestamp
  };
  const data = await request(`session/update/${encodeURIComponent(sessionId)}`, {
    method: "POST",
    body: payload
  });
  console.log("Session updated:", payload);
  return data?.guest_commands || [];
}

async function apiGetSession(sessionId) {
  return await request(`session/get/${encodeURIComponent(sessionId)}`, {
    method: "GET",
    cache: "no-store"
  });
}

async function apiGetRecommendations(songHash, n = 10, songSeed = null) {
  if (!songHash) throw new Error("songHash is required");
  const sessionId = getSessionIdOrThrow();
  const body = { song_hash: songHash, seed_hash: songSeed, session_id: sessionId, limit: n };
  const data = await request("recommendations/song", { method: "POST", body });
  return data?.recommendations || [];
}

async function apiGetPersonalMix(n = 10) {
  const sessionId = getSessionIdOrThrow();
  const body = { session_id: sessionId, limit: n };
  const data = await request("recommendations/personal", { method: "POST", body });
  return data?.recommendations || [];
}

async function apiGetRecommendationsGenre(genre) {
  if (!genre) throw new Error("Genre is required");
  const data = await request(`recommendations/genre/${encodeURIComponent(genre)}`, { method: "GET" });
  return data?.recommendations || [];
}

async function apiGetLyrics(song_hash) {
  if (!song_hash) throw new Error("song_hash is required");
  try {
    const data = await request(`lyrics/song/${encodeURIComponent(song_hash)}`, {
      method: "GET",
      cache: "no-store"
    });
    return data?.lyrics || "<i>No lyrics found.</i>";
  } catch (error) {
    return "<i>No lyrics found.</i>";
  }
}

async function apiGetRecommendationsByScene() {
  const data = await request("recommendations/main-genres/10", { method: "GET" });
  return data?.recommendations || {};
}

async function apiRateSong(song_hash, action) {
  if (!song_hash || !action) throw new Error("Missing song_hash or action");
  const email = localStorage.getItem("email");
  if (!email) throw new Error("Missing email");
  const data = await request("song/rate", {
    method: "POST",
    body: { song_hash, action, email }
  });
  return data;
}

async function apiCheckAuth() {
    const sessionId = localStorage.getItem("session_id");
    const sessionKey = localStorage.getItem("session_key");

    if (!sessionId || !sessionKey) return false;

    try {
        const response = await fetch(`${API_BASE}/check_auth`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ session_id: sessionId, session_key: sessionKey })
        });

        if (!response.ok) {
            console.warn(`Auth check failed: ${response.status}`);
            return false;
        }

        const data = await response.json();
        return data.status === "ok";
    } catch (err) {
        console.error("Auth check error:", err);
        return false;
    }
}

async function apiGetUserSettings() {
    const sessionId = localStorage.getItem("session_id");
    if (!sessionId) throw new Error("Missing session_id in localStorage");

    const url = new URL(`${API_BASE}/user/settings`);
    url.searchParams.set("session_id", sessionId);

    const response = await fetch(url.toString(), {
        method: "GET"
    });

    if (!response.ok) {
        const err = await response.json().catch(() => ({}));
        throw new Error(err.detail || `Failed to fetch settings: ${response.status}`);
    }

    const data = await response.json();
    return data.settings || {};
}

async function apiSaveUserSettings(settingsObj) {
    const sessionId = localStorage.getItem("session_id");
    if (!sessionId) throw new Error("Missing session_id in localStorage");

    const response = await fetch(`${API_BASE}/user/settings`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
            session_id: sessionId,
            settings: settingsObj
        })
    });

    if (!response.ok) {
        const err = await response.json().catch(() => ({}));
        throw new Error(err.detail || `Failed to save settings: ${response.status}`);
    }

    return true;
}

async function apiUpdateUserSetting(key, value) {
    if (typeof key !== "string") throw new Error("Setting key must be a string");

    const settings = await apiGetUserSettings();
    settings[key] = value;
    await apiSaveUserSettings(settings);
}