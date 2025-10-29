def _jaccard_index(xs: list, ys: list) -> float:
    if not xs or not ys:
        return 0
    return (len(set(xs) & set(ys)) / max(1, len(set(xs) | set(ys))))