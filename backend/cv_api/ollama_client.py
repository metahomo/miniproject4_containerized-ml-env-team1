"""공유 Ollama 서버 클라이언트 — `Ollama 유저 가이드.md` 2.2 템플릿을 이 서비스용으로 옮긴 것.

가이드 규칙을 코드로 강제한다:
  - num_ctx 8192 고정, num_predict 1024 기본          (1.3, 1.7-1·2)
  - 서버 호출은 프로세스당 동시 1건 (세마포어)         (1.7-5, 2.1-5)
  - 연결 오류·시간 초과만 재시도(3s·6s), 4xx/5xx 즉시 실패 (2.3)
  - keep_alive 5분 이하, 내리기는 내 접두사 모델만      (1.6)
  - 헬스체크는 /api/version 만, 1분 1회 이하 (호출 측 책임) (1.7-6)
  - think:false, </think> 제거                           (1.4)
비전 모델(qwen3-vl)에는 /api/chat 의 messages[].images (base64) 로 프레임을 넘긴다.
"""
from __future__ import annotations

import base64
import getpass
import json
import threading
import time
import urllib.error
import urllib.request
from typing import Any, Dict, List, Optional

from .settings import get_settings

NUM_CTX = 8192
NUM_PREDICT = 1024
KEEP_ALIVE = "5m"
_lock = threading.Semaphore(1)


class OllamaError(RuntimeError):
    pass


def _url() -> str:
    return get_settings().OLLAMA_URL.rstrip("/")


def _request(path: str, payload: Optional[Dict[str, Any]] = None, timeout: Optional[float] = None, retries: int = 3):
    data = json.dumps(payload).encode() if payload is not None else None
    t = timeout or get_settings().OLLAMA_TIMEOUT_S
    for attempt in range(retries):
        try:
            req = urllib.request.Request(_url() + path, data=data, headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=t) as resp:
                return json.load(resp)
        except urllib.error.HTTPError as e:
            raise OllamaError(f"Ollama {e.code}: {e.read().decode(errors='replace')[:300]}") from e
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            if attempt == retries - 1:
                raise OllamaError(f"Ollama 요청 실패: {e}") from e
            time.sleep(2 ** attempt * 3)


def _strip_think(text: str) -> str:
    return text.split("</think>", 1)[1].lstrip() if "</think>" in text else text


def health(timeout: float = 5.0) -> str:
    return _request("/api/version", timeout=timeout, retries=1)["version"]


def installed_models() -> List[str]:
    return [m["name"] for m in _request("/api/tags", retries=1)["models"] if not m["name"].endswith("cloud")]


def loaded_models() -> List[Dict[str, Any]]:
    return [
        {"name": m["name"], "context_length": m.get("context_length"), "expires_at": m.get("expires_at")}
        for m in _request("/api/ps", retries=1)["models"]
    ]


def preload(model: str, keep_alive: str = KEEP_ALIVE) -> Optional[str]:
    """서비스 시작 시 1회 미리 올린다 (첫 응답 지연 제거). 반환 'load'."""
    with _lock:
        return _request("/api/generate", {"model": model, "keep_alive": keep_alive, "options": {"num_ctx": NUM_CTX}}).get(
            "done_reason"
        )


def unload(model: str) -> Optional[str]:
    """내 접두사(<계정명>-) 모델만 내린다. 공용 모델이면 PermissionError."""
    prefix = getpass.getuser() + "-"
    if not model.startswith(prefix):
        raise PermissionError(f"공용 모델은 내리지 않는다: {model} (허용: {prefix}*)")
    with _lock:
        return _request("/api/generate", {"model": model, "keep_alive": 0}).get("done_reason")


def chat(
    messages: List[Dict[str, Any]],
    model: str,
    json_mode: bool = False,
    num_predict: int = NUM_PREDICT,
    keep_alive: str = KEEP_ALIVE,
    timeout: Optional[float] = None,
) -> str:
    body: Dict[str, Any] = {
        "model": model, "messages": messages, "stream": False, "think": False, "keep_alive": keep_alive,
        "options": {"num_ctx": NUM_CTX, "num_predict": num_predict},
    }
    if json_mode:
        body["format"] = "json"
    with _lock:
        return _strip_think(_request("/api/chat", body, timeout=timeout)["message"]["content"])


def chat_vision(prompt: str, image_bytes: bytes, model: str, json_mode: bool = True, timeout: Optional[float] = None) -> str:
    """비전 모델에 프레임 1장을 넘긴다. 이미지는 요청 본문에만 실리고 서버·클라이언트 어디에도 저장하지 않는다."""
    b64 = base64.b64encode(image_bytes).decode("ascii")
    return chat([{"role": "user", "content": prompt, "images": [b64]}], model=model, json_mode=json_mode, timeout=timeout)
