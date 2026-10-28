"""Small, cached, keyless Photon search for explicit dispatcher requests."""
import asyncio
from collections import OrderedDict
import math
import time
import httpx


class SearchBusy(Exception):
    pass


class SearchUnavailable(Exception):
    pass


def normalize_features(data):
    if not isinstance(data, dict) or not isinstance(data.get("features"), list):
        raise SearchUnavailable()
    results, seen = [], set()
    for feature in data["features"]:
        if not isinstance(feature, dict):
            continue
        geometry, props = feature.get("geometry"), feature.get("properties")
        if not isinstance(geometry, dict) or not isinstance(props, dict) or geometry.get("type") != "Point":
            continue
        point = geometry.get("coordinates")
        if not isinstance(point, list) or len(point) != 2:
            continue
        lon, lat = point
        if any(isinstance(v, bool) or not isinstance(v, (float, int)) or not math.isfinite(v) for v in point):
            continue
        if not (-90 <= lat <= 90 and -180 <= lon <= 180):
            continue
        parts = []
        street = " ".join(str(props.get(name) or "") for name in ("street", "housenumber")).strip()
        for value in (props.get("name"), street, props.get("city"), props.get("state"), props.get("country")):
            if isinstance(value, str) and value.strip() and value.strip() not in parts:
                parts.append(value.strip())
        label = ", ".join(parts)[:255]
        identity = (round(lat, 4), round(lon, 4), label.casefold())
        if label and identity not in seen:
            seen.add(identity)
            results.append({"label": label, "latitude": lat, "longitude": lon})
        if len(results) == 5:
            break
    return results


class PhotonSearch:
    def __init__(self, client, endpoint, *, interval=1.1, ttl=300, max_cache=128, clock=time.monotonic):
        self.client, self.endpoint = client, endpoint
        self.interval, self.ttl, self.max_cache = interval, ttl, max_cache
        self.clock = clock
        self.cache = OrderedDict()
        self.users = OrderedDict()
        self.lock = asyncio.Lock()
        self.last_request = -float("inf")

    async def search(self, query, username):
        query = " ".join(query.split())
        if not 3 <= len(query) <= 200:
            raise ValueError("Query must contain 3 to 200 characters")
        key = query.casefold()
        now = self.clock()
        cached = self.cache.get(key)
        if cached is not None and cached[0] > now:
            self.cache.move_to_end(key)
            return [dict(result) for result in cached[1]]
        if self.lock.locked():
            raise SearchBusy()
        async with self.lock:
            now = self.clock()
            recent = [stamp for stamp in self.users.pop(username, []) if now-stamp < 60]
            if len(recent) >= 10:
                self.users[username] = recent
                raise SearchBusy()
            self.users[username] = recent + [now]
            while len(self.users) > 1024:
                self.users.popitem(last=False)
            pause = self.interval - (now - self.last_request)
            if pause > 0:
                await asyncio.sleep(pause)
            self.last_request = self.clock()
            try:
                response = await asyncio.wait_for(self.client.get(self.endpoint, params={
                    "q": query, "limit": 5, "lat": 51.16, "lon": 71.47,
                    "bbox": "70.8,50.8,72.0,51.7",
                }), timeout=5)
                response.raise_for_status()
                results = normalize_features(response.json())
            except (httpx.HTTPError, ValueError, TypeError, asyncio.TimeoutError) as error:
                raise SearchUnavailable() from error
            self.cache[key] = (self.clock() + self.ttl, results)
            self.cache.move_to_end(key)
            while len(self.cache) > self.max_cache:
                self.cache.popitem(last=False)
            return [dict(result) for result in results]
