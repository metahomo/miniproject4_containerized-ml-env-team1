# 02-repo-init

## 목표
프롬프트로 쓰던 README를 docs/로 옮기고, 프로젝트 소개 README, 협업 규칙, 줄바꿈·무시 파일 설정을 추가해 저장소 골격을 만든다.

- 담당: A (Git/협업 리드)
- 대응 학습 모듈: 3-1 Git/GitHub 기반 협업과 코드 관리
- 이슈: #3 / PR: #4

## 선행 조건
- 01-issue-template 머지 완료
- 도구: git

## 직접 진행할 순서
1. 웹에서 이슈 #3 등록 (ISSUE.md)
2. develop 최신화 후 feature/02-repo-init 브랜치 생성
3. README.md를 docs/PROMPT.md로 이동(git mv)
4. README.md, .gitignore, .gitattributes, docs/CONTRIBUTING.md 작성, steps/ 생성
5. 커밋 후 push
6. 웹에서 PR 생성, base: develop
7. 리뷰 승인 후 Squash and merge, 브랜치 삭제
8. 확인 (VERIFY.md)
