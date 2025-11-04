def _jaccard_index(xs: list, ys: list) -> float:
    if not xs or not ys:
        return 0
    return (len(set(xs) & set(ys)) / max(1, len(set(xs) | set(ys))))

import re
import unicodedata

def normalize_name(name: str) -> str:
    if not isinstance(name, str):
        name = str(name or "")
    s = unicodedata.normalize("NFKD", name)
    s = s.encode("ascii", "ignore").decode("ascii")
    s = s.lower()
    s = re.sub(r"[^a-z0-9]", "_", s)
    s = re.sub(r"_+", "_", s).strip("_")
    return s
