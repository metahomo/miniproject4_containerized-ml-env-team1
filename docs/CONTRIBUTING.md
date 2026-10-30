# 협업 규칙

## 브랜치
- main: 발표·릴리스용, 직접 push 금지
- develop: 통합 브랜치, 직접 push 금지
- feature/NN-slug: 단계별 작업 (예: feature/06-compose-db)

## 작업 순서
1. 이슈 확인 → 본인 assign
2. git switch develop && git pull
3. git switch -c feature/NN-slug
4. 작업 → 커밋 → git push -u origin feature/NN-slug
5. PR 생성 (base: develop) → 리뷰 1인 승인 → Squash and merge

## 커밋 메시지
type(scope): 요약

본문(무엇을, 왜)

Refs: #이슈번호

| type | 용도 |
|---|---|
| feat | 기능 |
| fix | 버그 수정 |
| docs | 문서 |
| chore | 설정·환경 |
| refactor | 동작 변화 없는 구조 개선 |

## 단계 폴더
- steps/NN-slug/ 에 단계 문서를 둔다.
- changes/ 의 파일은 저장소 루트의 같은 경로에 반영한다.
