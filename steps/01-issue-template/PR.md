# PR

## 제목
[01] 이슈·PR 템플릿과 라벨 체계 구성

## 브랜치
feature/01-issue-template → develop

## 본문
### 관련 이슈
Closes #1

### 단계
01-issue-template

### 변경 요약
- .github/ISSUE_TEMPLATE/step.yml: 단계 작업용 이슈 양식
- .github/ISSUE_TEMPLATE/bug.yml: 문제 보고용 이슈 양식
- .github/ISSUE_TEMPLATE/config.yml: 빈 이슈 작성 막기
- .github/PULL_REQUEST_TEMPLATE.md: PR 기본 양식

### 검증 방법
머지 후 New issue에서 단계 작업, 문제 보고 양식이 보이는지 확인

### 리뷰어 체크리스트
- [ ] 파일 4개가 .github/ 아래 올바른 경로에 있다
- [ ] YAML 들여쓰기 오류가 없다
