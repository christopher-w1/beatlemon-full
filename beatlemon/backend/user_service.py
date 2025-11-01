import os, json, hashlib, uuid, time, asyncio

class UserService:
    def __init__(self, users_file="data/users.json", registration_key="SUPER_SECRET_KEY"):
        self.users_file = users_file
        self.registration_key = registration_key
        self.lock = asyncio.Lock()
        self.sessions_data = {} # key -> data
        self.session_ids = {}   # id  -> key
        self.users = {}
        self.settings_cache = {}
        self.settings_dir = "data/user_settings"
        os.makedirs(self.settings_dir, exist_ok=True)
        self._load_users()

    def _load_users(self):
        os.makedirs(os.path.dirname(self.users_file), exist_ok=True)
        if os.path.exists(self.users_file):
            with open(self.users_file, "r") as f:
                self.users = json.load(f)

    async def _save_users(self):
        os.makedirs(os.path.dirname(self.users_file), exist_ok=True)
        async with self.lock:
            tmpfile = self.users_file + ".tmp"
            with open(tmpfile, "w", encoding="utf-8") as f:
                json.dump(self.users, f, ensure_ascii=False, indent=2)
            os.replace(tmpfile, self.users_file)


    @staticmethod
    def _hash_password(password, salt=None) -> tuple[str, str]:
        import os
        if salt is None:
            salt = os.urandom(16).hex()
        hashed = hashlib.sha256((salt + password).encode()).hexdigest()
        return hashed, salt

    async def register(self, registration_key, email, username, password, lastfm_user=None):
        if registration_key != self.registration_key:
            raise ValueError("Invalid registration key")
        if not email or not username or not password:
            raise ValueError("Missing required fields")
        success = False
        async with self.lock:
            if email in self.users:
                raise ValueError("Email already registered")

            hashed_pw, salt = self._hash_password(password)
            self.users[email] = {
                "username": username,
                "password_hash": hashed_pw,
                "salt": salt,
                "lastfm_user": lastfm_user,
                "registered_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            }
            success = True
        if success:
            await self._save_users()

    async def login(self, email, password) -> tuple[str, str, str]:
        user = self.users.get(email)
        if not user:
            raise ValueError("Invalid credentials")

        hashed_pw, _ = self._hash_password(password, user["salt"])
        if hashed_pw != user["password_hash"]:
            raise ValueError("Invalid credentials")

        session_key = uuid.uuid4().hex
        session_id = uuid.uuid4().hex
        self.sessions_data[session_key] = {"email": email, "created": time.time(), "last_active": time.time()}
        self.session_ids[session_id] = session_key
        return user["username"], session_key, session_id

    async def logout(self, session_key) -> None:
        async with self.lock:
            self.sessions_data.pop(session_key, None)
        
    async def refresh_session(self, session_key) -> None:
        async with self.lock:
            session = self.sessions_data.get(session_key)
            if session:
                session["last_active"] = time.time()
            
    async def validate_session(self, session_key) -> bool:
        async with self.lock:
            if session_key in self.sessions_data:
                self.sessions_data[session_key]["last_active"] = time.time()
                return True
        return False

    async def get_user_by_session_key(self, session_key) -> dict:
        session = self.sessions_data.get(session_key)
        print(f"From Key {session_key} -> Found session:{session}")
        if not session: return {}
        email = session.get("email")
        print(f"From Session {session} -> Found email:{email}")
        if not email: return {}
        user = self.users.get(email, {})
        print(f"From Email {email} -> Found user:{user}")
        return user
    
    async def get_email_by_session_id(self, session_id) -> str | None:
        session_key = self.session_ids.get(session_id)
        if not session_key: 
            print(f"Error: No session_key found for id={session_key}")
            return None
        session = self.sessions_data.get(session_key)
        if not session: 
            print(f"Error: No session found for key={session_key}")
            return None
        email = session.get("email")
        return email
    
    def _safe_filename(self, email: str) -> str:
        hashed = hashlib.sha256(email.encode()).hexdigest()
        return os.path.join(self.settings_dir, f"{hashed}.json")
    
    async def get_settings(self, email: str) -> dict:
        if email in self.settings_cache:
            return self.settings_cache[email]

        filename = self._safe_filename(email)
        if os.path.exists(filename):
            async with self.lock:
                with open(filename, "r", encoding="utf-8") as f:
                    self.settings_cache[email] = json.load(f)
        else:
            self.settings_cache[email] = {}

        return self.settings_cache[email]

    async def save_settings(self, email: str, settings: dict) -> None:
        filename = self._safe_filename(email)
        async with self.lock:
            with open(filename + ".tmp", "w", encoding="utf-8") as f:
                json.dump(settings, f, ensure_ascii=False, indent=2)
            os.replace(filename + ".tmp", filename)
        self.settings_cache[email] = settings

