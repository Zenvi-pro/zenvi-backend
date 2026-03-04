"""
TwelveLabs indexing helpers.
Ported from zenvi-core — standalone, no Qt or app dependencies.
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple

from logger import log


def _load_dotenv_if_available() -> None:
    try:
        from dotenv import load_dotenv
    except Exception:
        return
    try:
        root_env = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))), ".env")
        cwd_env = os.path.join(os.getcwd(), ".env")
        if os.path.exists(root_env):
            load_dotenv(dotenv_path=root_env, override=False)
        elif os.path.exists(cwd_env):
            load_dotenv(dotenv_path=cwd_env, override=False)
    except Exception:
        return


def _get_api_key() -> Optional[str]:
    _load_dotenv_if_available()
    key = os.getenv("TWELVELABS_API_KEY")
    if not key:
        try:
            from config import get_settings
            key = get_settings().twelvelabs_api_key
        except Exception:
            pass
    return key or None


def is_configured() -> bool:
    return bool(_get_api_key())


def _get_client():
    api_key = _get_api_key()
    if not api_key:
        return None
    try:
        from twelvelabs.client import TwelveLabs
        return TwelveLabs(api_key=api_key)
    except Exception:
        return None


def delete_video_from_index(*, index_id: str, video_id: str) -> bool:
    client = _get_client()
    if client is None:
        return False
    try:
        videos_api = getattr(getattr(client, "indexes", None), "videos", None)
        if videos_api is None:
            return False
        delete_fn = getattr(videos_api, "delete", None) or getattr(videos_api, "remove", None)
        if delete_fn is None:
            return False
        try:
            delete_fn(str(index_id), str(video_id))
            return True
        except TypeError:
            try:
                delete_fn(str(video_id))
                return True
            except Exception:
                return False
    except Exception:
        return False


def build_project_index_name(project_id: str) -> str:
    return f"zenvi-project-{str(project_id)[:12]}"


@dataclass(frozen=True)
class IndexingResult:
    status: str
    index_id: Optional[str] = None
    asset_id: Optional[str] = None
    indexed_asset_id: Optional[str] = None
    video_id: Optional[str] = None
    filename: Optional[str] = None
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "status": self.status,
            "index_id": self.index_id,
            "asset_id": self.asset_id,
            "indexed_asset_id": self.indexed_asset_id,
            "video_id": self.video_id,
            "filename": self.filename,
            "error": self.error,
            "updated_at": time.time(),
        }


def _safe_str(exc: BaseException) -> str:
    try:
        return str(exc)
    except Exception:
        return exc.__class__.__name__


def get_or_create_index_id(index_name: str) -> Tuple[Optional[str], Optional[str]]:
    client = _get_client()
    if client is None:
        return None, "TwelveLabs not configured"
    try:
        if hasattr(client, "indexes") and hasattr(client.indexes, "list"):
            for idx in client.indexes.list():
                name = getattr(idx, "index_name", None) or getattr(idx, "name", None)
                if isinstance(idx, dict):
                    name = name or idx.get("index_name") or idx.get("name")
                if str(name) == str(index_name):
                    existing_id = getattr(idx, "id", None)
                    if isinstance(idx, dict):
                        existing_id = existing_id or idx.get("id")
                    if existing_id:
                        return str(existing_id), None
    except Exception:
        pass
    try:
        from twelvelabs.indexes.types.indexes_create_request_models_item import IndexesCreateRequestModelsItem
        resp = client.indexes.create(
            index_name=index_name,
            models=[IndexesCreateRequestModelsItem(model_name="marengo3.0", model_options=["visual", "audio"])],
        )
        index_id = getattr(resp, "id", None) or (resp.get("id") if isinstance(resp, dict) else None)
        if not index_id:
            return None, "TwelveLabs index creation returned no id"
        return str(index_id), None
    except Exception as e:
        return None, _safe_str(e)


def upload_video_asset(file_path: str, filename: Optional[str] = None) -> Tuple[Optional[str], Optional[str]]:
    client = _get_client()
    if client is None:
        return None, "TwelveLabs not configured"
    try:
        result = client.multipart_upload.upload_file(file_path, filename=filename, file_type="video")
        asset_id = getattr(result, "asset_id", None)
        if not asset_id:
            return None, "TwelveLabs upload returned no asset_id"
        return str(asset_id), None
    except Exception as e:
        return None, _safe_str(e)


def create_indexed_asset(index_id: str, asset_id: str) -> Tuple[Optional[str], Optional[str]]:
    client = _get_client()
    if client is None:
        return None, "TwelveLabs not configured"
    try:
        resp = client.indexes.indexed_assets.create(index_id, asset_id=asset_id, enable_video_stream=True)
        indexed_asset_id = getattr(resp, "id", None) or (resp.get("id") if isinstance(resp, dict) else None)
        if not indexed_asset_id:
            return None, "TwelveLabs indexed asset creation returned no id"
        return str(indexed_asset_id), None
    except Exception as e:
        return None, _safe_str(e)


def poll_indexed_asset_ready(
    index_id: str,
    indexed_asset_id: str,
    *,
    filename: Optional[str] = None,
    max_wait_seconds: float = 60 * 30,
    sleep_seconds: float = 10.0,
) -> IndexingResult:
    client = _get_client()
    if client is None:
        return IndexingResult(status="not_configured", index_id=index_id, indexed_asset_id=indexed_asset_id, filename=filename)
    started = time.time()
    try:
        while True:
            detailed = client.indexes.indexed_assets.retrieve(index_id, indexed_asset_id)
            status = getattr(detailed, "status", None) or (detailed.get("status") if isinstance(detailed, dict) else None)
            status = str(status) if status is not None else "unknown"
            if status.lower() == "ready":
                video_id = None
                try:
                    if filename:
                        for v in client.indexes.videos.list(index_id):
                            sys = getattr(v, "system_metadata", None)
                            sys_filename = getattr(sys, "filename", None) if sys is not None else None
                            if sys_filename and os.path.basename(str(sys_filename)) == os.path.basename(filename):
                                video_id = getattr(v, "id", None)
                                break
                except Exception:
                    pass
                return IndexingResult(status="ready", index_id=index_id, indexed_asset_id=indexed_asset_id, video_id=str(video_id) if video_id else None, filename=filename)
            if status.lower() == "failed":
                return IndexingResult(status="failed", index_id=index_id, indexed_asset_id=indexed_asset_id, filename=filename, error="TwelveLabs indexing failed")
            if time.time() - started > max_wait_seconds:
                return IndexingResult(status="timeout", index_id=index_id, indexed_asset_id=indexed_asset_id, filename=filename, error="Timed out waiting for TwelveLabs indexing")
            time.sleep(sleep_seconds)
    except Exception as e:
        return IndexingResult(status="failed", index_id=index_id, indexed_asset_id=indexed_asset_id, filename=filename, error=_safe_str(e))


def index_video_blocking(*, file_path: str, index_name: str, filename: Optional[str] = None, existing_index_id: Optional[str] = None) -> Dict[str, Any]:
    if not is_configured():
        return IndexingResult(status="not_configured", filename=filename).to_dict()
    try:
        index_id = existing_index_id
        if not index_id:
            index_id, err = get_or_create_index_id(index_name)
            if err:
                return IndexingResult(status="failed", filename=filename, error=err).to_dict()
        if not index_id:
            return IndexingResult(status="failed", filename=filename, error="Missing index_id").to_dict()
        asset_id, err = upload_video_asset(file_path, filename=filename)
        if err:
            return IndexingResult(status="failed", index_id=index_id, filename=filename, error=err).to_dict()
        indexed_asset_id, err = create_indexed_asset(index_id, asset_id)
        if err:
            return IndexingResult(status="failed", index_id=index_id, asset_id=asset_id, filename=filename, error=err).to_dict()
        ready = poll_indexed_asset_ready(index_id, indexed_asset_id, filename=filename)
        d = ready.to_dict()
        d["asset_id"] = asset_id
        return d
    except Exception as e:
        return IndexingResult(status="failed", filename=filename, error=_safe_str(e)).to_dict()


def search_index(query: str, *, index_id: str = "", top_k: int = 5):
    """Search a TwelveLabs index for matching clips."""
    client = _get_client()
    if client is None:
        return []
    try:
        if not index_id:
            # Use first available index
            for idx in client.indexes.list():
                index_id = getattr(idx, "id", None) or (idx.get("id") if isinstance(idx, dict) else None)
                if index_id:
                    break
        if not index_id:
            return []
        results = client.search.query(index_id=index_id, query_text=query, search_options=["visual", "audio"])
        clips = []
        for r in list(results)[:top_k]:
            clips.append({
                "video_id": getattr(r, "video_id", None),
                "score": float(getattr(r, "score", None) or 0),
                "start": float(getattr(r, "start", None) or 0),
                "end": float(getattr(r, "end", None) or 0),
                "filename": getattr(r, "filename", None) or "",
            })
        return clips
    except Exception as e:
        log.error("TwelveLabs search failed: %s", e)
        return []
