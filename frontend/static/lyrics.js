/**
 * Get lyrics from lyrics.ovh
 * @param {string} artist
 * @param {string} title
 * @returns {Promise<string>} Lyrics
 */
async function externalGetLyrics(artist, title) {
  const url = `https://api.lyrics.ovh/v1/${encodeURIComponent(artist)}/${encodeURIComponent(title)}`;
  try {
    const res = await fetch(url, { method: "GET", cache: "no-store" });
    if (!res.ok) {
      if (res.status === 404) return "";
      throw new Error(`Lyrics request failed: ${res.status}`);
    }
    const data = await res.json();
    return (data && data.lyrics) ? String(data.lyrics) : "";
  } catch (err) {
    console.error("apiGetLyrics error:", err);
    return "";
  }
}