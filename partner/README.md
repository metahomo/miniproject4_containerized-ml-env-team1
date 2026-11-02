# 영상 혼잡도 측정 — 외부 서비스 시연

혼잡도 진단 API(영상 프레임 → 사람 수 → 밀집도)를 **외부 웹서비스가 연계해 쓰는 모습**을 보여 주는 시연 페이지다. 본 웹(`frontend/`)과 코드가 분리돼 있다.

- 주소: **https://p4.sumzip.com/partner/** (PC·휴대폰, https 라서 카메라 권한을 받을 수 있다)
- 입력 두 가지
  - **영상 파일** — 브라우저 안에서만 재생. 측정 간격(1·2·5초)마다 그 시점 프레임을 떠 보낸다. 파일 전체는 올라가지 않는다. 끝나면 평균·최대 인원·등급 분포 요약.
  - **실시간 카메라** — 기기 카메라(웹캠·휴대폰 카메라)를 연결해 간격마다 한 장씩 보낸다. 영상은 저장되지 않는다. 휴대폰은 **후면 카메라**로 켜지고 «전면/후면 전환» 버튼으로 바꾼다(측정 중에도 가능, 전면은 미리보기만 거울). 장치 목록에서 직접 고를 수도 있다.
- 결과: 사람 수 · 밀집도(인원 ÷ 정원 %) · 잔여 탑승 가능(% · 명) · 등급(여유·보통·혼잡·판단보류) · 평균 신뢰도 · 경고 · 추이 그래프 · 측정 기록(응답 시간). 판단보류는 화질·신뢰도가 기준 미달이라 «참고용»이라는 뜻.
- 프레임 규격: 긴 변 ≤ 1280 px(짧은 변 ≥ 240 px) JPEG 품질 0.85 — API 규격(JPEG/PNG · 240~4096 px · ≤ 10 MB) 안.

## 구조

```
브라우저 ── /partner/ (이 폴더의 index.html)
       └── /partner-api/v1/diagnose (프레임 1장, multipart) ──▶ 9504 vite 의 partnerSite 중계 (외부 서비스의 백엔드 역할)
                                                               · camera_id 가 CAM-PARTNER-01 인지 확인 · 6 MB 한도
                                                               · 브라우저 자격 헤더는 버리고 X-API-Key 부착
                                                               └──▶ https://p4.sumzip.com/model-api/v1/diagnose ──▶ 9544 API
```

- 설정: `frontend/vite.config.ts` 의 `partnerSite()` 플러그인(중계 코드 포함). 중계하는 것: `GET /v1/readiness` · `GET /v1/reference/cameras/CAM-PARTNER-01` · `POST /v1/diagnose`(CAM-PARTNER-01 만). 그 밖은 403, 6 MB 초과 413, 점 파일(`.secrets`) 404.
- **키는 브라우저에 가지 않는다** — 서버→서버 연계. 응답의 `X-Request-ID` 는 브라우저까지 전달돼 화면 아래에 보인다(문의 시 이 번호로 서버 로그 한 줄을 찾는다).

## API 로 직접 쓰기 (화면 없이 — 외부 서비스의 서버에서)

키는 환경변수로만 넘긴다(`export CV_API_KEY=…` — 명령행에 값을 직접 쓰지 않는다). 게이트웨이 `https://p4.sumzip.com/model-api`, 명세 `…/model-api/docs`.

```bash
# ① 프레임 한 장 → 사람 수·밀집도 (이 페이지가 쓰는 것, 한 장 0.1~0.4초)
curl -s -H "X-API-Key: $CV_API_KEY" -F camera_id=CAM-PARTNER-01 -F frame=@frame.jpg \
     https://p4.sumzip.com/model-api/v1/diagnose
#   → {"person_count":7,"capacity":80,"occupied_area_ratio":8.75,"vacant_capacity_ratio":91.25,
#      "crowding_level":"free|normal|crowded|uncertain","mean_confidence":…,"warnings":[…],"versions":{…}}

# ② 영상 파일 통째 → 간격마다 진단한 추이 + 요약 (10초 영상 2초 간격 약 2.4초)
curl -s -H "X-API-Key: $CV_API_KEY" -F camera_id=CAM-PARTNER-01 -F interval_s=2 -F file=@video.mp4 \
     https://p4.sumzip.com/model-api/v1/web/diagnose-video
#   → {"video":{…},"items":[{"t":0.0,"status":"accepted","assessment":{…},"smoothed_vacant_ratio":…},…],
#      "summary":{"frames":5,"accepted":5,"uncertain":1,"vacant_min":87.5,"vacant_max":92.5,"vacant_median":91.25}}
#   한 장만: interval_s 대신 at_s=3 (3초 지점)
```

- 응답 헤더 `X-Request-ID` 를 남겨 두면 문의 때 서버 로그 한 줄을 바로 찾는다.
- 실패: 키 없음 401 · 승인 대기 403 `KEY_PENDING` · 카메라 꺼짐 409 · 규격 밖(형식·해상도·용량·미정의 필드) 422 — 본문에 `gate`·`reason_code`·`reason`.
- 지난 결과를 다시 조회하는 연계용 API 는 없다(결과는 호출할 때 받은 응답뿐). 이력은 운영 관리자 화면에서만 본다.

## 이 서비스용으로 만든 것 (2026-09-30)

| 무엇 | 값 |
|---|---|
| 연계 계정 | `partner-demo` (일반 사용자) — 실제 온보딩 절차: 가입 201 → 키 신청 201 `pending`(이때 호출 403 `KEY_PENDING`) → 운영 관리자 승인 200 → 호출 200. 관리 기능(배치) 401 |
| API 키 | 4번 `정류장 안내 앱`(active). 원문은 `partner/.secrets` 에만(권한 600, git 추적 제외 — `LOGIN_ID`·`PASSWORD`·`API_KEY_ID`·`API_KEY`) |
| 전용 카메라 | `CAM-PARTNER-01` — `bus_in`, 차량 유형 `VT_LOW`(정원 80), 관심영역 화면 전체(0,0–4096,4096), 전원 켬, 자동 진단 소스 없음. 시연 카메라(CAM-DEMO-*)의 기록과 섞이지 않게 따로 둠 |

키를 바꾸면(재발급·폐기) `.secrets` 를 고친 뒤 vite 를 다시 띄운다 — 키는 vite 가 뜰 때 한 번 읽는다(`vite.config.ts` 를 저장해도 다시 읽힌다).
진단마다 운영 DB 에 요청·결과 행이 남는다(호출 주체 `partner-demo:정류장 안내 앱`, 원본 프레임은 저장 안 함).

## 끄는 법 · 되돌리는 법

- 시연만 끄기: 운영 관리자가 키 4번 폐기(`DELETE /v1/admin/api-keys/4`) → 중계가 403. 또는 S2b 에서 `CAM-PARTNER-01` 전원 끄기 → 409.
- 설정 되돌리기: `frontend/vite.config.ts.bak-20260930-1319`(partner 추가 전) 로 복사, `frontend/src/vite-config-node.d.ts` 삭제, 이 폴더 삭제.
- 버스 조회판(첫 판) 페이지는 `partner/index.html.bak-20260930-1352`, 그때의 설정은 `frontend/vite.config.ts.bak-20260930-1352`.
