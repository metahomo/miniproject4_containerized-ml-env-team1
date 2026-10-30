"""서비스 설정 — research.md R4(요청 규격)·R5(판독 기준)·R6(인증)·R12(외부)·R17(보존)·R20(발자국) 기본값.

원천에 값이 있는 것: 신뢰도 0.6, 기본 유효 시간 10분, 합산 시각 창 1분, 시연 2시간, SC 85%.
그 외는 Clarifications 3차 Q5 로 확정한 기본값이며 운영 설정(.env)으로 조정한다. 파일럿 결과로 재조정.
Ollama 관련 값은 `Ollama 유저 가이드.md` 1.1·1.3·1.7 규칙을 따른다.
"""
from __future__ import annotations

import hashlib
from functools import lru_cache
from pathlib import Path
from typing import Dict, Literal, Optional, Tuple

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parent.parent
REPO_ROOT = BACKEND_DIR.parent
PUBLIC_DEFAULT_KEYS = ("changeme-web", "changeme-admin")   # 코드 기본값·quickstart·테스트에 적힌 키


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=BACKEND_DIR / ".env", env_file_encoding="utf-8", extra="ignore",
                                      env_ignore_empty=True)   # 빈 값(KEY=)은 «없음» → 코드 기본값. .env.example 을 그대로 복사해도 뜬다 (API 점검 D9)

    # ---- 저장소 ----
    DATABASE_URL: str = f"sqlite:///{BACKEND_DIR / 'cv.db'}"
    DDL_PATH: Path = REPO_ROOT / "design" / "cv_ddl.sql"
    DDL_POSTGRES_PATH: Path = REPO_ROOT / "design" / "cv_ddl.postgres.sql"

    # ---- 인증 (R6) — "caller_id:key,caller_id:key". 키는 평문 또는 sha256:<hex> ----
    API_KEYS: str = "web:changeme-web"
    ADMIN_KEYS: str = "op1:changeme-admin"
    # 위 기본 키(저장소·문서에 공개된 값)로는 운영 실행(cv_api.serve)이 뜨지 않는다. 로컬 개발에서만 1 (BE-1)
    ALLOW_INSECURE_KEYS: bool = False

    # ---- 요청 규격 (R4, G2, BR-CV-11) ----
    IMAGE_FORMATS: Tuple[str, ...] = ("jpeg", "png")
    IMAGE_MIN_SIDE: int = 240
    IMAGE_MAX_SIDE: int = 4096
    IMAGE_MAX_BYTES: int = 10 * 1024 * 1024
    BATCH_MAX_FRAMES: int = 20

    # ---- 규격 변환 (/v1/web/* — /v1/diagnose 등은 위 규격 그대로 반려) ----
    DIAGNOSIS_API_URL: str = ""   # /v1/web/* 가 변환한 프레임을 넘길 진단 API — 지정 모델 게이트웨이를 .env 로 (API 점검 A9, 이전: 원본 포트 주소가 코드 기본값). 비면 G0 503
    NORMALIZE_MAX_SIDE: int = 1920          # 긴 변 상한 (FHD). 모델 입력이 640 이라 더 커도 이득 없음. 확대는 하지 않는다
    NORMALIZE_JPEG_QUALITY: int = 90
    MEDIA_MAX_BYTES: int = 50 * 1024 * 1024       # 웹 화면 사진 업로드 한도 (변환 전)
    VIDEO_MAX_BYTES: int = 500 * 1024 * 1024      # 영상 업로드 한도
    VIDEO_MAX_FRAMES: int = 60              # 영상 1건당 진단 프레임 수 상한 (넘으면 간격을 넓힘)
    VIDEO_DEFAULT_INTERVAL_S: float = 2.0
    VIDEO_MIN_INTERVAL_S: float = 0.5
    VIDEO_SMOOTH_WINDOW: int = 5            # 추이 그래프 평활화: 직전 N 장 중앙값
    SAMPLES_DIR: Path = BACKEND_DIR / "samples"   # S5 샘플 사진·영상 — catalog.json 에 적힌 파일만 내준다 (자유 이용 허가 자료, 이용자 원본 아님)

    # ---- 판독 기준 (R5, G6, BR-CV-06·07·21) ----
    BLUR_LAPLACIAN_MIN: float = 100.0
    LOW_LIGHT_MEAN_MAX: float = 40.0
    BACKLIGHT_HIGH_VALUE: int = 250
    BACKLIGHT_HIGH_RATIO: float = 0.05
    BACKLIGHT_LOW_VALUE: int = 30
    BACKLIGHT_LOW_RATIO: float = 0.30
    CONFIDENCE_MIN: float = 0.6
    OCCLUSION_IOU: float = 0.5
    OCCLUSION_RATIO: float = 0.30
    INFER_TIMEOUT_S: float = 5.0

    # ---- 검출기 (Clarifications Q12: MaxTheTechy/yolo — YOLOv8n person 검출) ----
    # yolov8   : 프로세스(uvicorn) 안에 가중치 적재
    # ollama_vl: 공유 Ollama 서버의 비전 모델(qwen3-vl)로 사람 박스를 JSON 으로 받음
    # stub     : 테스트용 고정 박스
    DETECTOR: str = "yolov8"
    MODEL_REPO: str = "https://github.com/MaxTheTechy/yolo"
    MODEL_WEIGHTS: Path = BACKEND_DIR / "models" / "yolov8n.pt"
    MODEL_PERSON_CLASS_ID: int = 0          # MODEL_TARGET=auto 에서 클래스 이름을 못 찾을 때만 쓴다
    MODEL_TARGET: Literal["auto", "person", "head"] = "auto"   # auto: 가중치에 head 클래스가 있으면 머리 검출(기준점 = 박스 중심), 없으면 person(발 위치)
    MODEL_DEVICE: str = "cpu"
    MODEL_CONF_MIN: float = 0.25
    MODEL_IMGSZ: int = 1280                 # YOLO 입력 긴 변(px). 640 → 1280: 밀집·작은 사람 검출 증가(대합실 샘플 평균 5.4 → 12.8명), 한 장 32 → 65ms (T090)

    # ---- Ollama 공유 서버 (가이드 1.1·1.3·1.7) ----
    OLLAMA_URL: str = "http://127.0.0.1:11434"
    OLLAMA_VISION_MODEL: str = "gemma4:e4b"   # A등급 이미지 이해 모델. qwen3-vl 은 사고 모드가 꺼지지 않아 출력이 비어 온다(가이드 1.4, 2026-09-28 실측)
    OLLAMA_NUM_CTX: int = 8192                       # 고정값. 바꾸지 않는다
    OLLAMA_NUM_PREDICT: int = 1024
    OLLAMA_KEEP_ALIVE: str = "5m"                    # A등급 상한
    OLLAMA_TIMEOUT_S: float = 300.0                  # 앞 요청 대기 포함
    OLLAMA_INFER_TIMEOUT_S: float = 120.0            # 비전 추론 1건 상한 (G5 판정용, 300s 안)

    # ---- 인원 세기 (R22) ----
    COUNT_CONF_MIN: float = 0.4             # 인원 세기 기준 기본값 — 등급 기준(threshold_policy.count_conf_min)이 비어 있을 때
    FOOTPRINT_M2: float = 0.30              # R20 발자국 면적 — R22 이후 산출에 쓰지 않음 (.env 호환용으로만 남김)

    # ---- 외부 연계 (R12) ----
    EXTERNAL_PROVIDER: str = "fixture"  # fixture | bis
    BIS_API_KEY: str = ""
    BIS_TIMEOUT_S: float = 3.0
    BIS_BASE_URL: str = "https://apis.data.go.kr/6300000"
    BIS_POS_CACHE_S: float = 60.0          # 버스 위치 — 일일 호출 한도 보호. 15 → 60초(T102): 몇 명이 보든 노선당 1분에 최대 1회
    BIS_STATIC_CACHE_S: float = 6 * 3600.0  # 노선 기본정보·경유 정류소
    BIS_DEFAULT_SPEED_KMH: float = 18.0    # RUN_DIST_HALF/RUN_TM 이 없을 때 도착 추정 속도
    HEADWAY_STALE_HOURS: int = 24
    FIXTURES_DIR: Path = BACKEND_DIR / "data" / "fixtures"

    # ---- 응답 고지 (FR-10) ----
    NOTICE_TEXT: str = "이 수치는 영상 프레임을 바탕으로 한 통계적 추정치이며 실제 탑승 가능 여부를 보장하지 않습니다."

    # ---- 운영 (R15·R17, P0) ----
    RETENTION_DAYS: Optional[int] = None
    OPS_LOOP_SECONDS: int = 60
    DEMO_DEFAULT_HOURS: int = 2

    # ---- 서버 ----
    SERVER_PUBLIC_URL: str = "http://localhost:9544"   # 외부 연계용 공개 API 포트 (D1)
    SERVE_PORTS: Tuple[int, ...] = (9544, 9524)          # cv_api.serve 가 한 프로세스로 여는 포트. 첫 포트가 모델 적재. 둘 다 같은 앱(D1)
    CORS_ORIGINS: Tuple[str, ...] = ("*",)   # 웹은 vite 프록시로 호출하지만, 직접 호출(다른 PC)도 허용

    @field_validator("RETENTION_DAYS", mode="before")
    @classmethod
    def _empty_to_none(cls, v):
        return None if v in ("", None) else v

    @field_validator("MODEL_WEIGHTS", "FIXTURES_DIR", "SAMPLES_DIR", mode="before")
    @classmethod
    def _relative_to_backend(cls, v):
        p = Path(v)
        return p if p.is_absolute() else (BACKEND_DIR / p)

    def _parse_keys(self, raw: str) -> Dict[str, str]:
        out: Dict[str, str] = {}
        for item in filter(None, (p.strip() for p in raw.split(","))):
            if ":" not in item:
                continue
            cid, key = item.split(":", 1)
            out[cid.strip()] = key[7:].lower() if key.startswith("sha256:") else hashlib.sha256(key.encode()).hexdigest()
        return out

    @property
    def api_key_hashes(self) -> Dict[str, str]:
        return self._parse_keys(self.API_KEYS)

    @property
    def admin_key_hashes(self) -> Dict[str, str]:
        return self._parse_keys(self.ADMIN_KEYS)

    def insecure_key_fields(self) -> Tuple[str, ...]:
        """공개된 기본 키(changeme-…)가 들어 있는 설정 이름. 값이 비면 기본값이 쓰이므로 이것으로 함께 걸린다 (BE-1)."""
        weak = {hashlib.sha256(k.encode()).hexdigest() for k in PUBLIC_DEFAULT_KEYS}
        return tuple(name for name, table in (("API_KEYS", self.api_key_hashes), ("ADMIN_KEYS", self.admin_key_hashes))
                     if weak & set(table.values()))

    @property
    def is_sqlite(self) -> bool:
        return self.DATABASE_URL.startswith("sqlite")


@lru_cache
def get_settings() -> Settings:
    return Settings()
