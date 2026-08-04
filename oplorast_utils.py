# OPLoraST trigger-word utilities.
# Ported from ComfyUI-Lora-Auto-Trigger-Words (utils.py) with improvements:
#   - requests timeout added (original had none -> could hang)
#   - atomic cache write (os.replace) to reduce concurrent corruption
#   - cache file kept inside the plugin directory
#   - exception-safe: returns [] / None instead of crashing
import os
import json
import hashlib

import folder_paths

try:
    import requests
except Exception:  # pragma: no cover
    requests = None

_PLUGIN_DIR = os.path.dirname(os.path.abspath(__file__))
_CACHE_PATH = os.path.join(_PLUGIN_DIR, "loras_tags.json")


# --------------------------------------------------------------------------- #
# JSON cache helpers
# --------------------------------------------------------------------------- #
def _load_json(path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def _save_json_atomic(data, path):
    tmp = path + ".tmp"
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
        os.replace(tmp, path)
    except Exception as e:
        print(f"[LoRAStackAutoTriggers] cache save failed: {e}")


# --------------------------------------------------------------------------- #
# Hash + civitai
# --------------------------------------------------------------------------- #
def calculate_sha256(file_path):
    """Full-file SHA256, 1MB chunks. Returns None on failure."""
    if not file_path or not os.path.exists(file_path):
        return None
    h = hashlib.sha256()
    try:
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(1024 * 1024), b""):
                h.update(chunk)
        return h.hexdigest()
    except Exception as e:
        print(f"[LoRAStackAutoTriggers] sha256 failed: {e}")
        return None


def get_model_version_info(hash_value):
    if requests is None:
        return None
    api_url = f"https://civitai.com/api/v1/model-versions/by-hash/{hash_value}"
    try:
        resp = requests.get(api_url, timeout=(5, 15))
        if resp.status_code == 200:
            return resp.json()
        return None
    except Exception as e:
        print(f"[LoRAStackAutoTriggers] civitai request failed: {e}")
        return None


def load_and_save_tags(lora_name, force_fetch):
    """Fetch civitai trainedWords for a lora, cached to loras_tags.json."""
    cache = _load_json(_CACHE_PATH)
    if cache is None:
        cache = {}
    cached = cache.get(lora_name)
    if cached is not None and not force_fetch:
        return cached

    lora_path = folder_paths.get_full_path("loras", lora_name)
    if not lora_path or not os.path.exists(lora_path):
        cache[lora_name] = []
        _save_json_atomic(cache, _CACHE_PATH)
        return []

    print(f"[LoRAStackAutoTriggers] calculating hash for {lora_name}")
    sha = calculate_sha256(lora_path)
    if not sha:
        cache[lora_name] = []
        _save_json_atomic(cache, _CACHE_PATH)
        return []

    print(f"[LoRAStackAutoTriggers] requesting civitai info for {lora_name}")
    info = get_model_version_info(sha)
    if info is not None and "trainedWords" in info:
        words = info.get("trainedWords") or []
        print(f"[LoRAStackAutoTriggers] civitai tags found for {lora_name}: {len(words)}")
        cache[lora_name] = words
        _save_json_atomic(cache, _CACHE_PATH)
        return words

    print(f"[LoRAStackAutoTriggers] no civitai info for {lora_name}")
    cache[lora_name] = []
    _save_json_atomic(cache, _CACHE_PATH)
    return []


# --------------------------------------------------------------------------- #
# safetensors metadata
# --------------------------------------------------------------------------- #
def get_metadata(lora_name):
    """Read __metadata__ from a safetensors lora header."""
    lora_path = folder_paths.get_full_path("loras", lora_name)
    if not lora_path or not os.path.exists(lora_path):
        return None
    try:
        with open(lora_path, "rb") as f:
            header_size = int.from_bytes(f.read(8), "little", signed=False)
            if header_size <= 0:
                return None
            header = f.read(header_size)
            header_json = json.loads(header)
            return header_json.get("__metadata__")
    except Exception as e:
        print(f"[LoRAStackAutoTriggers] metadata read failed: {e}")
        return None


def sort_tags_by_frequency(meta_tags):
    """Parse ss_tag_frequency and return tags sorted by training frequency."""
    if not meta_tags or "ss_tag_frequency" not in meta_tags:
        return []
    try:
        freq = meta_tags["ss_tag_frequency"]
        if isinstance(freq, str):
            freq = json.loads(freq)
        merged = {}
        for _dataset, tags in freq.items():
            for tag, count in tags.items():
                tag = str(tag).strip()
                if not tag:
                    continue
                merged[tag] = merged.get(tag, 0) + count
        ordered = sorted(merged.items(), key=lambda kv: kv[1], reverse=True)
        return [t for t, _ in ordered]
    except Exception as e:
        print(f"[LoRAStackAutoTriggers] sort_tags failed: {e}")
        return []


# --------------------------------------------------------------------------- #
# Combined tags + selector
# --------------------------------------------------------------------------- #
def get_combined_tag_strings(lora_name, force_fetch):
    """Return (combined_tags, civitai_count, meta_only_count).

    civitai tags first, then meta-only tags, deduped. The counts let the UI
    label each tag's source (civitai vs meta).
    """
    civitai = load_and_save_tags(lora_name, force_fetch) or []
    meta = sort_tags_by_frequency(get_metadata(lora_name)) or []

    combined = []
    seen = set()
    for t in civitai:
        t = str(t).strip()
        if t and t not in seen:
            seen.add(t)
            combined.append(t)
    civitai_count = len(combined)

    for t in meta:
        t = str(t).strip()
        if t and t not in seen:
            seen.add(t)
            combined.append(t)
    meta_only_count = len(combined) - civitai_count
    return combined, civitai_count, meta_only_count


def _safe_int(value, default):
    try:
        return int(value)
    except (ValueError, TypeError):
        return default


def parse_selector(selector, tags_list):
    """ATW slice syntax: '0, 3, 5:8, -8:'. Returns ', '-joined selected tags."""
    if not tags_list:
        return ""
    if selector is None:
        selector = ""
    output = {}
    for range_index in str(selector).split(","):
        colons = range_index.count(":")
        if colons == 0:
            if range_index.strip() == "":
                continue
            index = _safe_int(range_index.strip(), None)
            if index is None:
                continue
            if abs(index) > len(tags_list) - 1:
                continue
            output[index] = tags_list[index]
        elif colons == 1:
            parts = range_index.split(":")
            start = 0 if parts[0].strip() == "" else _safe_int(parts[0].strip(), 0)
            end = len(tags_list) if parts[1].strip() == "" else _safe_int(parts[1].strip(), len(tags_list))
            if start is None:
                start = 0
            if end is None:
                end = len(tags_list)
            if start < 0:
                start = len(tags_list) + start
            if end < 0:
                end = len(tags_list) + end
            start = min(max(start, 0), len(tags_list))
            end = min(max(end, 0), len(tags_list))
            for i in range(start, end):
                output[i] = tags_list[i]
    return ", ".join(output.values())


# --------------------------------------------------------------------------- #
# Backend route
# --------------------------------------------------------------------------- #
def setup_lora_trigger_routes():
    """Register /lorastack/trigger_words on the ComfyUI PromptServer."""
    from server import PromptServer
    from aiohttp import web

    server = PromptServer.instance

    @server.routes.get("/lorastack/trigger_words")
    async def get_trigger_words(request):
        lora_name = request.rel_url.query.get("lora_name", "")
        force = request.rel_url.query.get("force", "false").lower() == "true"
        if not lora_name or lora_name == "None":
            return web.json_response(
                {"tags": [], "civitai_count": 0, "meta_count": 0, "ok": True}
            )
        try:
            combined, civ_count, meta_count = get_combined_tag_strings(lora_name, force)
            return web.json_response(
                {
                    "tags": combined,
                    "civitai_count": civ_count,
                    "meta_count": meta_count,
                    "ok": True,
                }
            )
        except Exception as e:
            print(f"[LoRAStackAutoTriggers] route error: {e}")
            return web.json_response(
                {
                    "tags": [],
                    "civitai_count": 0,
                    "meta_count": 0,
                    "ok": False,
                    "error": str(e),
                }
            )

    print("[LoRAStackAutoTriggers] route registered: /lorastack/trigger_words")
    return True