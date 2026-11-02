# samples — 시연·테스트 프레임

시연 시나리오(`HG/시연웹/01-시연-시나리오.md` §3)의 자산. **인터넷에서 구한 자유 이용 허가 사진만** 둔다. 파일이 없으면 `scripts/demo_prepare.py` 가 합성 프레임을 만들어 쓴다.

| 파일 | 용도 | 조건 |
|---|---|---|
| `bus_full.jpg` | 앞차 — 혼잡 (CAM-DEMO-01 / 1234호) | 시내버스 차내, 선명, 사람 많음 |
| `bus_empty.jpg` | 다음 차 — 여유 (CAM-DEMO-02 / 5678호) | 같은 차량 유형, 사람 적음 |
| `bus_blur.jpg` | 판독 불확실 (CAM-DEMO-03 / 9012호) | `bus_full.jpg` 를 블러 처리해도 됨 (스크립트가 자동 처리) |

## 출처 기록 규칙 (필수)

파일을 넣을 때 아래 표에 한 줄씩 적는다. 뉴스·방송 캡처는 쓰지 않는다. 얼굴이 뚜렷한 사진은 피한다(서비스는 비식별이 원칙이고 발표 화면에 원본이 보인다).

| 파일 | 출처 URL | 라이선스 | 저작자 | 비고 |
|---|---|---|---|---|
| (예) bus_full.jpg | https://commons.wikimedia.org/... | CC BY-SA 4.0 | ... | 2026-09-30 내려받음 |
| bus_full.jpg | https://commons.wikimedia.org/wiki/File:2022.06.29_Inside_a_public_bus_in_Tomasz%C3%B3w_Mazowiecki,_Poland.ogg | Public domain | WrS.tm.pl | videos/bus_crowded_tomaszow.webm 7초 장면(854×480), 입석 승객. 서비스 검출기 9명. 2026-10-01 |
| bus_empty.jpg | https://commons.wikimedia.org/wiki/File:Przejazd_jednyn_z_nowych_autobus%C3%B3w_MZK_Solaris_Urbino_12_w_Tomaszowie_Mazowieckim_w_wojew%C3%B3dztwie_%C5%82%C3%B3dzkim._Inwestycja_z_roku_2017.ogv | Public domain | Mux8cont | videos/bus_seated_tomaszow.webm 46초 장면(854×480), 좌석 승객 뒷모습. 서비스 검출기 3명. 2026-10-01 |
| bus_blur.jpg | https://commons.wikimedia.org/wiki/File:2022.06.29_Inside_a_public_bus_in_Tomasz%C3%B3w_Mazowiecki,_Poland.ogg | Public domain | WrS.tm.pl | bus_full.jpg 에 가우시안 블러 9 — 라플라시안 분산 2.0(< 100) → 판독 불확실. 2026-10-01 |
| videos/bus_crowded_tomaszow.webm | https://commons.wikimedia.org/wiki/File:2022.06.29_Inside_a_public_bus_in_Tomasz%C3%B3w_Mazowiecki,_Poland.ogg | Public domain | WrS.tm.pl | 480p VP9 변환본, 음성 제거, 2026-09-29 |
| videos/bus_seated_tomaszow.webm | https://commons.wikimedia.org/wiki/File:Przejazd_jednyn_z_nowych_autobus%C3%B3w_MZK_Solaris_Urbino_12_w_Tomaszowie_Mazowieckim_w_wojew%C3%B3dztwie_%C5%82%C3%B3dzkim._Inwestycja_z_roku_2017.ogv | Public domain | Mux8cont | 480p VP9, 앞 47초만(뒤는 창밖), 음성 제거, 2026-09-29 |
| videos/subway_crowded_moscow.webm | https://commons.wikimedia.org/wiki/File:Metro_de_Mosc%C3%BA_1.webm | CC BY-SA 4.0 | ProtoplasmaKid | 480p VP9, 16초 이후 객차 내부만(앞은 승강장), 음성 제거, 2026-09-29 |
| videos/subway_seated_mexico.webm | https://commons.wikimedia.org/wiki/File:Trayecto_del_Metro_de_la_Ciudad_de_M%C3%A9xico_L%C3%ADnea_2.webm | CC BY 4.0 | ProtoplasmaKid | 480p VP9, 앞 41초만(뒤는 창밖 역), 음성 제거, 2026-09-29 |
| videos/concourse_crowded_saint_lazare.webm | https://commons.wikimedia.org/wiki/File:2025-11-06_17-33-16_-_Paris_-_Saint-Lazare_-_Time-lapse.webm | CC BY-SA 4.0 | Baidax | 480p VP9 변환본, 2026-09-29 |
| videos/crossing_timelapse_shibuya.webm | https://commons.wikimedia.org/wiki/File:Shibuya_crossing_time-lapse_2019-01-05.webm | CC0 | Asanagi | 480p VP9 변환본, 2026-09-29 |
| videos/platform_sparse_ragigudda.webm | https://commons.wikimedia.org/wiki/File:Interiors_of_Ragigudda_metro_station,_Bangalore_(2025).webm | CC BY-SA 4.0 | Gpkp | 480p VP9 변환본, 2026-09-29 |
| videos/train_interior_nyc.webm | https://commons.wikimedia.org/wiki/File:NYC_Subway_train_inside_vc.ogv | CC BY-SA 2.0 | otto-yamamoto (Flickr) | 480p VP9 변환본, 2026-09-29 |

## S5 샘플 선택 (`catalog.json`)

S5 현재 프레임 진단의 "샘플 선택" 목록은 `catalog.json` 에 적힌 파일만 보여 준다(`GET /v1/web/samples`, 파일은 `GET /v1/web/samples/{file}`).
샘플을 추가하려면 파일을 이 폴더(예: `videos/`)에 넣고 `catalog.json` 에 `file·title·description·source_url·license·author` 한 항목, 위 출처 표에 한 줄을 더한다.
서버 재시작은 필요 없다. 영상은 브라우저가 재생할 수 있는 형식(WebM VP9, MP4 H.264)으로 둔다 — 재생이 되어야 실시간 진단·장면 진단을 쓸 수 있다.

## 규격

JPEG 또는 PNG, 320×240 ~ 4096×4096, 10 MB 이하 (FR-02). 넘으면 `POST /v1/diagnose` 가 422 로 반려한다.

## ROI

`scripts/demo_prepare.py` 는 세 카메라에 같은 ROI(바닥 사각형, 실제 면적 6.5 ㎡)를 등록한다. 실제 사진을 쓰면 S2 화면의 다각형 편집기로 사진마다 ROI 를 다시 그리고 실제 면적을 넣는다.
