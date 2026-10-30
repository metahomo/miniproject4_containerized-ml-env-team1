"""cv_api — 대전 대중교통 비식별 군중 밀집도·잔여 공간 진단 API.

계층 (specs/001-crowd-vacancy-api/plan.md Project Structure):
- app.py         FastAPI 앱 팩토리. 진단 API(9544, lifespan: DDL → 검출기 적재 → 웜업 → 계약 확인 → 준비 완료)
- web.py         웹 백엔드(9524) 진입점 — 운영 관리 /v1/admin/* (DB 만)
- settings.py    규격·판독 기준값·키·외부 공급자·검출기·Ollama 설정
- schemas.py     Pydantic 계약 (contracts/openapi.yaml 과 1:1, 요청은 extra="forbid")
- predict.py     검출기 어댑터(Detector: yolov8 프로세스 내 / ollama_vl 공유 서버 gemma4:e4b / stub) + 인원 ÷ 정원 혼잡도 계산 (R22)
- ollama_client  공유 Ollama 서버 규칙(num_ctx 8192, keep_alive 5m, 동시 1건, 타임아웃 300s)을 강제하는 클라이언트
- quality.py     선명도·조도·역광·겹침 검사 → warnings
- gates.py       게이트 G0~G17 판정 → HTTP 상태 + gate_event 기록
- db.py          SQLAlchemy Core, design/cv_ddl.sql 멱등 적용
- repo/          영역별 DB 접근 (A 기준 정보 ~ G 안내)
- services/      프로세스 P0~P9
- external/      BIS·배차·기준 정보 공급자 (+ Fixture)
- routers/       엔드포인트
"""

__version__ = "0.1.0"
