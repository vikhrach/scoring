import hashlib
import json
import logging
from typing import Optional

from scoring import store


def get_score(
    store: store.Store,
    phone: Optional[str] = None,
    email: Optional[str] = None,
    birthday: Optional[str] = None,
    gender: Optional[int] = None,
    first_name: Optional[str] = None,
    last_name: Optional[str] = None,
) -> float:
    key_parts = [
        first_name or "",
        last_name or "",
        phone or "",
        birthday or "",
    ]
    key = "uid:" + hashlib.md5("".join(key_parts).encode("utf-8")).hexdigest()

    # Try to get from cache
    score = store.cache_get(key)
    if score is not None:
        return float(score)

    # Calculate score
    score = 0.0
    if phone:
        score += 1.5
    if email:
        score += 1.5
    if birthday and gender is not None:
        score += 1.5
    if first_name and last_name:
        score += 0.5

    # Cache the score for 60 minutes
    store.cache_set(key, score, 60 * 60)
    return score


def get_interests(store, cid: str) -> list:
    r = store.get(f"i:{cid}")
    logging.info(f" Cache value {r} ")
    if r:
        return json.loads(r)
    else:
        raise KeyError(f"Values with key {cid} doesn't exist in cache'")
