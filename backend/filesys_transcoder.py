import subprocess
import os
import mutagen
import shutil

DEFAULT_ENCODERS = {
    "mp3": "libmp3lame",
    "ogg": "libvorbis",
    "opus": "libopus",
    "aac": "aac",  
    "m4a": "aac",  
    "flac": "flac",
    "wav": "pcm_s16le",
    "alac": "alac"
}

def has_encoder(name: str) -> bool:
    try:
        result = subprocess.run(["ffmpeg", "-hide_banner", "-encoders"], capture_output=True, text=True)
        return name in result.stdout
    except Exception:
        return False

def get_encoder_for_format(fmt: str) -> str | None:
    fmt = fmt.lower()
    if fmt in ("aac", "m4a") and has_encoder("libfdk_aac"):
        return "libfdk_aac"
    default_encoder = DEFAULT_ENCODERS.get(fmt)
    if default_encoder and has_encoder(default_encoder):
        return default_encoder
    return None

class Transcoding:
    def __init__(self, song_hash: str, src_file: str, target_format: str, target_bitrate: int | None, cache_dir: str, volume_change: float = 0):
        self.song_hash = song_hash
        self.src_file = src_file
        self.target_format = target_format.lower()
        self.target_bitrate = target_bitrate
        self.cache_dir = cache_dir
        self.volume_change = volume_change
        os.makedirs(self.cache_dir, exist_ok=True)
        self.output_file = self._build_output_path()

    def _build_output_path(self) -> str:
        bitrate_str = f"{self.target_bitrate}k" if self.target_bitrate else "default"
        name = f"{self.song_hash}_{bitrate_str}.{self.target_format}"
        return os.path.join(self.cache_dir, name)
    
    def _get_original_format(self) -> str:
        return os.path.splitext(self.src_file)[1][1:].lower()

    def _get_original_bitrate(self) -> int | None:
        try:
            audio = mutagen.File(self.src_file)  # type: ignore
            if audio and hasattr(audio.info, 'bitrate'):
                return audio.info.bitrate // 1000  # in kbit/s
        except Exception as e:
            print(f"Warning: Failed to read bitrate of {self.src_file}: {e}")
        return None

    def should_transcode(self) -> bool:
        original_format = self._get_original_format()
        original_bitrate = self._get_original_bitrate()

        format_differs = original_format != self.target_format
        bitrate_lower = (
            self.target_bitrate is not None and
            original_bitrate is not None and
            (self.target_bitrate + 10) < original_bitrate
        )
        
        do_transcode = format_differs or bitrate_lower
        if do_transcode:
            print(f"Transcoding from {original_format}/{original_bitrate} to {self.target_format}/{self.target_bitrate}")
        return do_transcode

    def run(self) -> str:
        if os.path.exists(self.output_file):
            return self.output_file

        if not self.should_transcode():
            # Originalformat & Bitrate sind akzeptabel → nur kopieren
            shutil.copy2(self.src_file, self.output_file)
            return self.output_file
        
        encoder = get_encoder_for_format(self.target_format)
        #if not encoder:
        #    raise ValueError(f"Unsupported target format or encoder: {self.target_format}")


        command = [
            "ffmpeg",
            "-i", self.src_file,
            "-vn",             
            "-y",
        ]
        
        if self.volume_change:
            command += ["-filter:a", f"volume={self.volume_change}dB"]
        
        if encoder:
            command += ["-c:a", encoder]
        
        if self.target_bitrate:
            command += ["-b:a", f"{self.target_bitrate}k"]

        command.append(self.output_file)
        print(command)

        result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if result.returncode != 0:
            raise RuntimeError(f"Transcoding failed: {result.stderr.decode()}")

        return self.output_file
