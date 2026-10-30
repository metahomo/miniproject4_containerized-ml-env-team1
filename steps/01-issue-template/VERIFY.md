# 확인 방법

| 확인 항목 | 확인 명령 | 예상 결과 | 실제 검증 여부 |
|---|---|---|---|
| PR 머지 | 웹 develop 최근 커밋 | chore(github): 이슈·PR 템플릿 추가 (#2) | 검증됨 |
| 이슈 자동 종료 | 웹 Issues → Closed | #1 Closed | 검증됨 |
| 이슈 양식 표시 | 웹 Issues → New issue | 단계 작업, 문제 보고 선택지 | 미검증 |
| 빈 이슈 차단 | 웹 Issues → New issue | Blank issue 선택지 없음 | 미검증 |
| PR 템플릿 | 웹 New pull request | 본문에 템플릿 자동 입력 | 미검증 |
| 파일 경로 | ls -R .github | 파일 4개 | 미검증 |

미검증 항목은 확인 후 검증됨 / 실패(사유)로 수정한다.
