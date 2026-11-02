# 01-issue-template

## 목표
팀원 모두가 같은 형식으로 이슈와 PR을 작성하도록 이슈·PR 템플릿을 추가한다.

- 담당: A (Git/협업 리드)
- 대응 학습 모듈: 3-1 Git/GitHub 기반 협업과 코드 관리
- 이슈: #1 / PR: #2

## 선행 조건
- 저장소 생성, develop 브랜치 생성과 기본 브랜치 지정
- 라벨(type:*, area:*, priority:*)과 마일스톤(Day 1~5) 생성
- 도구: git, GitHub CLI(gh) 로그인 완료

## 직접 진행할 순서
1. 웹에서 이슈 #1 등록 (ISSUE.md)
2. develop 최신화 후 feature/01-issue-template 브랜치 생성
3. .github/ 아래 템플릿 4개 작성 (changes/)
4. 커밋 (COMMIT_MESSAGE.txt) 후 push
5. 웹에서 PR 생성 (PR.md), base: develop
6. 리뷰 승인 후 Squash and merge, 브랜치 삭제
7. 확인 (VERIFY.md)
