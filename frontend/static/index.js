// ---------- GLOBAL VARIABLES & IMPORTS ----------

const audioPlayer = document.getElementById('audio-player');
const progressContainer = document.getElementById("progress-container");
const progressBar = document.getElementById("progress-bar");
const progressTime = document.getElementById("progress-time");
const autoDjBtn = document.getElementById("auto-dj-btn");

let targetLoudness = -12;
let apiPing = 0;
let playlist = []; 
let currentPlayingIndex = -1;
let currentVolume = 0.8;
let isPlaying = false;
let currentSong = null;
let playlistVisible = true;
let settingsVisible = false;
let useAutoDj = false;
let autoDjQueueLength = 4;
let localMode = true;
let showBigCover = true;
let preventGenreDrift = true;


// ----------------- UI Functions -----------------

function updateUserGreeting() {
    const username = localStorage.getItem("username") || "unknown user";
    document.getElementById("user-greeting").innerHTML = `Hello, <b class="user-name">${username}</b><b>!</b>`;
}

function showMessage(message) {
    document.getElementById("user-greeting").innerHTML = `${message}`;
}

function togglePlaylist() {
    playlistVisible = !playlistVisible;
    const playlist = document.getElementById("playlist");
    const playlistToggleBtn = document.getElementById("toggle-playlist-btn");
    playlistToggleBtn.classList.toggle("active", playlistVisible);
    playlist.classList.toggle("hidden", !playlistVisible);
    console.log("visible:", playlistVisible,
              "has .hidden:", playlist?.classList.contains("hidden"),
              "inline display:", playlist?.style.display || "(none)");
    if (playlistVisible) {
        settingsVisible = false;
        document.getElementById("settings").classList.toggle("hidden", !settingsVisible);
        document.getElementById("toggle-settings-btn").classList.toggle("active", settingsVisible);
    }
}

function toggleSettings() {
    settingsVisible = !settingsVisible;
    if (settingsVisible) {
        document.getElementById("playlist").classList.toggle("hidden", true);
    } else {
        document.getElementById("playlist").classList.toggle("hidden", !playlistVisible);
    }
    document.getElementById("settings").classList.toggle("hidden", !settingsVisible);
    document.getElementById("toggle-settings-btn").classList.toggle("active", settingsVisible);
}

function toggleAutoDj() {
    useAutoDj = !useAutoDj;
    autoDjBtn.classList.toggle("active", useAutoDj);
    console.log(`useAutoDj=${useAutoDj}`)
}

function toggleCover() {
    showBigCover = !showBigCover;
    document.getElementById("sidebar-cover").classList.toggle("hidden", !showBigCover);
}

function showView(viewId) {
    const views = [
        "recommendations-view",
        "library-view",
        "playback-view"
    ];

    for (const id of views) {
        const el = document.getElementById(id);
        if (el) el.classList.add("hidden");
    }

    const active = document.getElementById(viewId);
    if (active) active.classList.remove("hidden");

    document.querySelectorAll("#top-panel button").forEach(btn =>
        btn.classList.remove("active")
    );
    const clicked = document.querySelector(
        `#top-panel button[onclick*="${viewId.split('-')[0]}"]`
    );
    if (clicked) clicked.classList.add("active");
}

function setBackgroundColor(tone, saturation, brightness) {
    const { r, g, b } = hslToRgb(tone, saturation, brightness);
    document.documentElement.style.setProperty('--background-color', `rgb(${r}, ${g}, ${b})`);
    document.body.style.backgroundColor = `rgb(${r}, ${g}, ${b})`;
}

function updateBackground() {
    const tone = +document.getElementById('tone-slider').value;
    const sat = +document.getElementById('saturation-slider').value;
    const bright = +document.getElementById('brightness-slider').value;

    document.getElementById('tone-val').textContent = tone;
    document.getElementById('sat-val').textContent = sat;
    document.getElementById('bright-val').textContent = bright;

    setBackgroundColor(tone, sat, bright);
    setTheme(bright);
}

function setTheme(brightness) {
  const root = document.documentElement;
  root.dataset.theme = (brightness > 40) ? 'bright' : 'dark';
}

// ----------------- SONG SEARCH ------------------

function initSearch() {
    const searchInput = document.getElementById("search-input");
    const searchButton = document.getElementById("search-button");

    searchInput.addEventListener("input", () => {
        const query = searchInput.value.trim();
        if (query.length >= 3) {
            searchForSong(query);
        } else {
            clearSearch();
        }
    });

    searchButton.addEventListener("click", () => {
        const query = searchInput.value.trim();
        if (query.length >= 3) {
            searchForSong(query);
        } else {
            clearSearch();
        }
    });
}

function clearSearch() {
    const container = document.getElementById("search-results");
    if (!container) return;
    container.innerHTML = "";
}

async function searchForSong(query) {
    console.log(`Searching for ${query}...`);
    const results = await api_search_songs(query);
    if (results && Array.isArray(results)) {
        renderSearchResults(results);
    } else {
        console.warn("Unexpected search result format:", results);
        renderSearchResults([]);
    }
}

function renderSearchResults(results) {
    clearSearch();
    const container = document.getElementById("search-results");
    
    const searchMsg = document.createElement("div");
    if (!results || results.length === 0) {
        searchMsg.textContent = "No results found.";
        searchMsg.style.opacity = "0.5";
        container.appendChild(searchMsg);
        return;
    } else {
        searchMsg.textContent = "Search Results";
    }
    container.appendChild(searchMsg);

    results.forEach((song, index) => {
        const el = document.createElement("div");
        el.classList.add("search-result");
        el.dataset.hash = song.hash;
        el.dataset.index = index;

        // Dauer formatieren (Sekunden → M:SS)
        const duration = song.duration
            ? `${Math.floor(song.duration / 60)}:${String(song.duration % 60).padStart(2, "0")}`
            : "--:--";

        const artist = song.artists;
        const cover_url = api_get_cover_url(song.cover_hash);
        const release_year = song.release_year ? `[${song.release_year}]` : '';

        el.innerHTML = innerHTML = `
        <img src="${cover_url}" class="cover" />
        <div class="info">
            <div class="text">
                <p class="title">${song.title}</p>
                <p class="artist">${artist}</p>
                <p class="album">${song.album} ${release_year}</p>
            </div>
        </div>
        <div class="duration">${duration}</div>
        <div class="button-row">
            <button class="mini-btn" title="Play" onclick=startPlaybackSongHash("${song.hash}")><i data-lucide="play">P</i></button>
            <button class="mini-btn" title="Add"  onclick=enqueueSongFromHash("${song.hash}")><i data-lucide="plus">+</i></button>
            <button class="mini-btn" title="Info"><i data-lucide="info">i</i></button>
        </div>
        <div class="classic-info">
        <p>${song.title}</p> 
        <p>${artist}</p> 
        <p>${song.album}</p> 
        <p>${release_year}</p>
        <p>${duration}</p> 
        </div>
        `;

        container.appendChild(el);
    });
    lucide.createIcons();
}

// ---------------- VOLUME CONTROL ----------------

// Function to set the volume and update the volume bar
function setVolume(volume) {
    volume = Math.max(0, Math.min(1, volume));

    const volumeBar = document.getElementById("volume-bar");
    if (!volumeBar) return;

    volumeBar.style.width = (volume * 100) + "%";
    currentVolume = volume;

    let loudness = (currentSong && currentSong.loudness) ?? -6;
    let gainDb = (targetLoudness - loudness)*0.71; 
    let loudnessFactor = Math.min(Math.pow(10, gainDb / 20), 1);
    audioPlayer.volume = Math.min(1, Math.max(0, volume * loudnessFactor));

    console.log(
        "Volume set to",
        Math.round(volume * 100) + "% (loudness adjusted:",
        Math.round(volume * loudnessFactor * 100) + "%)"
    );
}


function initVolumeControl() {
    const volumeContainer = document.getElementById("volume-container");
    let isDragging = false;

    const updateVolume = (clientX) => {
        const rect = volumeContainer.getBoundingClientRect();
        const clickX = clientX - rect.left;
        const newVolume = Math.max(0, Math.min(1, clickX / rect.width));
        setVolume(newVolume);
    };

    volumeContainer.addEventListener("mousedown", (e) => {
        isDragging = true;
        updateVolume(e.clientX);
    });

    window.addEventListener("mousemove", (e) => {
        if (isDragging) {
            updateVolume(e.clientX);
        }
    });

    window.addEventListener("mouseup", () => {
        isDragging = false;
    });

    volumeContainer.addEventListener("click", (e) => {
        updateVolume(e.clientX);
    });

    setVolume(currentVolume);
}



// ---------------- PLAYLIST MANAGEMENT ----------------

function clearPlaylist() {
    const playlistContainer = document.getElementById("playlist-item-container");
    playlistContainer.innerHTML = "";
    playlist = [];
}

function markPlaying(index) {
    document.querySelectorAll(".playlist-item.playing")
            .forEach(el => el.classList.remove("playing"));
    const el = document.getElementById(`track-${index}`);
    if (el) el.classList.add("playing");
}

function skipToSong(index) {
    console.log(`Skipping to index=${index}`)
    if (index == currentPlayingIndex) {
        if (!isPlaying) startLocalPlayback();
        console.log("Song is already playing!");
        return;
    }
    if (localMode) {
        song = playlist[index];
        stopLocalPlayback();
        currentPlayingIndex = index;
        currentSong = song;
        startLocalPlayback();
    }
}

async function invokeAutoDJ() {
    if (!currentSong || !playlist) {
        return;
    }
    let seed_hash = null;
    if (preventGenreDrift) {
        seed_hash =  playlist[0].hash;
    }
    const session_id = localStorage.getItem("session_id");
    let new_songs = await apiGetRecommendations(currentSong.hash, autoDjQueueLength, seed_hash, session_id);
    new_songs = new_songs.slice(0, autoDjQueueLength);
    new_songs.forEach(song => {
        addPlaylistItem(song);
    });
}

// Function to create and append a playlist element to the playlist container
function addPlaylistItem(song) {
    let index = playlist.length;
    let duration_formatted = formatTime(song.duration);
    playlist[index] = song;
    const playlistContainer = document.getElementById("playlist-item-container");
    const playlistItem = document.createElement("div");
    const coverUrl = api_get_cover_url(song.cover_hash);
    playlistItem.classList.add("playlist-item");
    playlistItem.id = `track-${index}`;
    playlistItem.dataset.hash = song.hash;
    playlistItem.dataset.index = index;
    playlistItem.onclick = () => skipToSong(index);
    playlistItem.innerHTML = `
        <img src="${coverUrl}" class="cover" />
        <div class="info">
            <div class="text">
                <p class="title"><i class="playback-indicator" data-lucide="play"></i> ${song.title}</p>
                <p class="artist">${song.artists}</p>
            </div>
        </div>
        <div class="duration">${duration_formatted}</div>
    `;
    console.log(`Adding song at index ${index}`)
    playlistContainer.appendChild(playlistItem);
}

// Function to render the entire playlist from a list of song dictionaries
function renderPlaylist(songs) {
    clearPlaylist();
    songs.forEach((song) => {
        addPlaylistItem(song);
    });
}

function replacePlaylist(songs) {
    if (localMode && songs) {
        stopLocalPlayback();
        currentPlayingIndex = 0;
        playlist = [];
        renderPlaylist(songs);
        currentSong = playlist[0];
    }
}

// -------------- RECOMMENDATIONS ----------------

async function createGenreCard(genre) {
    try {
        const songs = await apiGetRecommendationsGenre(genre);
        if (!songs || !songs.length) {
            console.warn(`No songs for genre "${genre}" available.`);
            return;
        }

        const card = document.createElement("div");
        card.className = "genre-recommendation";
        card.innerHTML = `
            <img src="static/icons8-music.png" alt="">
            Genre: <b>${genre}</b>
        `;

        card.onclick = () => replacePlaylist(songs);

        document.getElementById("genre-recommendations").appendChild(card);
    } catch (err) {
        console.error(`Error while creating genre card "${genre}":`, err);
    }
}

async function createSceneCards() {
    try {
        const allRecommendations = await apiGetRecommendationsByScene();

        for (const [scene, songs] of Object.entries(allRecommendations)) {
            if (!songs.length) continue;
            const first_song = songs[0];
            const img_url = api_get_cover_url(first_song.cover_hash);

            const card = document.createElement("div");
            card.className = "genre-recommendation";
            card.innerHTML = `
                <img src="${img_url}">
                <b>${capitalize(scene)}</b>
            `;

            card.onclick = () => replacePlaylist(songs);

            document.getElementById("genre-recommendations").appendChild(card);
        }
    } catch (err) {
        console.error("Error while creating genre cards:", err);
    }
}

function capitalize(str) {
    return str.charAt(0).toUpperCase() + str.slice(1);
}

// ----------------- PLAYBACK --------------------

async function startPlaybackSongHash(hash) {
    if (localMode) {
        stopLocalPlayback();
        // Grab song data
        const song = await api_get_song_data(hash);
        currentSong = song;
        currentPlayingIndex = 0;
        // Fill playlist
        clearPlaylist();
        addPlaylistItem(song);
        // Play audio
        startLocalPlayback();
    }
}

async function enqueueSongFromHash(hash) {
    if (localMode) {
        const song = await api_get_song_data(hash);
        if (!song) {
            console.warn("Song not found:", hash);
            return;
        }
        addPlaylistItem(song);
    }
}

function nextTrack() {
    if (localMode) {
        let new_index = currentPlayingIndex + 1;
        let nextPlaylistElement = document.getElementById(`track-${new_index}`);
        if (!nextPlaylistElement) {
            stopLocalPlayback();
            return;
        }
        skipToSong(new_index);
    }
}

function prevTrack() {
    if (localMode) {
        new_index = Math.max(currentPlayingIndex - 1, 0);
        let nextPlaylistElement = document.getElementById(`track-${new_index}`);
        if (!nextPlaylistElement) {
            return;
        }
        skipToSong(new_index)
    }
}

function togglePlayback() {
    if (localMode) {
        if (isPlaying) {
            stopLocalPlayback();
        } else {
            startLocalPlayback();
        }
    }
}

function startLocalPlayback() {
    if (!currentSong) {
        return;
    }
    if (!audioPlayer.src.endsWith(currentSong.hash)) {
        audioPlayer.src = api_get_song_url(currentSong.hash);
        updateLyrics();
    }
    const cover_url = api_get_cover_url(currentSong.cover_hash)
    document.getElementById("sidebar-cover").innerHTML=`<img src="${cover_url}">`
    document.getElementById("playback-cover").innerHTML=`<img src="${cover_url}">`
    document.getElementById("sidebar-cover").classList.toggle("hidden", !showBigCover);
    setVolume(currentVolume);
    isPlaying = true;
    broadcastCurrentState();
    audioPlayer.play().catch(err => {
        console.error("Playback error:", err);
        return;
    });
    document.getElementById("play-pause-btn").innerHTML = `<i data-lucide="pause"></i>`;
    lucide.createIcons();
    markPlaying(currentPlayingIndex);
    showMessage(`Now Playing: ${currentSong.artists} - ${currentSong.title}`)
    if ((currentPlayingIndex + 1 >= playlist.length) && useAutoDj) {
        invokeAutoDJ();
    }
}

async function updateLyrics() {
    const lyrics = await externalGetLyrics(currentSong.artists.split(",")[0], currentSong.title);
    document.getElementById("lyrics").innerHTML =
    lyrics ? lyrics.replace(/\n/g, "<br>")
      .replace(/(<br>\s*){1,2}(?!<br>)/g, "<br>")
      .replace(/(<br>\s*){3,}/g, "<br><br>")
    : "<i>No lyrics available.</i>";
}

function stopLocalPlayback() {
    broadcastCurrentState();
    audioPlayer.pause();
    isPlaying = false;
    const playPauseBtn = document.getElementById("play-pause-btn");
    playPauseBtn.innerHTML = `<i data-lucide="play"></i>`;
    lucide.createIcons();
    showMessage("Playback paused")
}

function initAudioPlayer() {
    audioPlayer.addEventListener("timeupdate", () => {
        if (!audioPlayer.duration) return;
        const percent = (audioPlayer.currentTime / audioPlayer.duration) * 100;
        progressBar.style.width = percent + "%";
        progressTime.textContent = `${formatTime(audioPlayer.currentTime)} / ${formatTime(audioPlayer.duration)}`;
    });

    audioPlayer.addEventListener("ended", () => {
        if (localMode) {
            nextTrack();
        }
    });
}

function setPlaybackProgress(progress) {
    if (localMode) {
        audioPlayer.currentTime = progress * audioPlayer.duration;
        broadcastCurrentState();
    }
}

function initProgressBar() {
    const progressContainer = document.getElementById("progress-container");

    const updatePlaybackProgress = (clientX) => {
        const rect = progressContainer.getBoundingClientRect();
        const clickX = clientX - rect.left;
        const newProgress = Math.max(0, Math.min(1, clickX / rect.width));
        setPlaybackProgress(newProgress);
    };

    progressContainer.addEventListener("click", (e) => {
        updatePlaybackProgress(e.clientX);
    });
}


// ------------------ LOGOUT --------------------

async function logout() {
    const session_key = localStorage.getItem("session_key");
    if (!session_key) {
        console.error("No session key found");
    } else {
        try {
        await apiLogoutUser(session_key);
        localStorage.removeItem("session_key");
        localStorage.removeItem("session_id");
        localStorage.removeItem("username");
        localStorage.removeItem("email");
        window.location.href = "login.html";
        } catch (err) {
            console.error("Logout failed:", err);
        }
    }
    // Reload window to redirect to login page
    const parent_url = window.location.href.split('/').slice(0, -1).join('/');
    window.location.href = `${parent_url}/login.html`;
}


// -------------- HELPER FUNCTIONS ----------------

function formatTime(seconds) {
    const m = Math.floor(seconds / 60);
    const s = Math.floor(seconds % 60).toString().padStart(2, "0");
    return `${m}:${s}`;
}

function broadcastCurrentState() {
    let playlistHashes = [];
    if (playlist) {
        playlistHashes = playlist.map(song => song.hash);
    }
    let hash = null;
    if (currentSong) {
        hash = currentSong.hash;
    }
    
    const sessionId = localStorage.getItem("session_id") || "default-session";
    api_update_session(
        hash, 
        currentPlayingIndex,
        playlistHashes, 
        apiPing, 
        audioPlayer.currentTime, 
        sessionId
    );
}

// ---------------- INITIALIZATION ----------------

function initColorControls() {
    ['tone-slider', 'saturation-slider', 'brightness-slider'].forEach(id =>
    document.getElementById(id).addEventListener('input', updateBackground)
    );
}

async function createGenreCards() {
    const genres = ["Pop", "Rock", "Metal", "RnB",
        "Electro", "Industrial", "Dark Wave", "Post Punk"
    ];
    for (const genre of genres) {
        await createGenreCard(genre);
    }
}
    

document.addEventListener("DOMContentLoaded", () => {
    updateUserGreeting();
    initVolumeControl();
    initSearch();
    initAudioPlayer();
    initProgressBar();
    toggleAutoDj();
    initColorControls();
    apiPing = api_get_ping();
    setTheme(25);
    createSceneCards();
    showView("recommendations-view")
});