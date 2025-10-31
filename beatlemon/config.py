import os
import json

class Config:
    def __init__(self, path: str):
        self.path = path
        if self.exists():
            self.load()
        else:
            self.setup_interactive()

    def exists(self) -> bool:
        return os.path.exists(self.path)

    def load(self):
        with open(self.path, "r", encoding="utf-8") as f:
            data = json.load(f)
        for k, v in data.items():
            setattr(self, k, v)

    def save(self):
        data = {k: v for k, v in self.__dict__.items() if k != "path"}
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def setup_interactive(self):
        print("Setting up configuration (only once)...")
        self.lastfm_api_key = input("Enter your LASTFM_API_KEY: ").strip()
        self.registration_key = input("Enter your secret registration key: ").strip()
        self.music_dir = input("Enter the absolute path to your MUSIC_DIR: ").strip()
        self.rest_api_port = int(input("Enter your REST_API_PORT (e.g. 8080): ").strip())
        self.save()
        print(f"Config written to {self.path}")
