# 작업 방법

## 1. 브랜치 생성과 파일 이동
```bash
cd ~/miniproject4_containerized-ml-env-team1
git switch develop
git pull
git switch -c feature/02-repo-init
mkdir -p docs steps
git mv README.md docs/PROMPT.md
touch steps/.gitkeep
```
- git mv: 파일 이동을 git이 이름 변경(rename)으로 기록, 이력 유지
- touch steps/.gitkeep: git은 빈 폴더를 추적하지 않으므로 빈 파일을 넣어 폴더 유지

## 2. 파일 작성
changes/ 의 README.md, .gitignore, .gitattributes, docs/CONTRIBUTING.md를 같은 경로에 만든다.

## 3. 커밋과 push
```bash
git add .
git status
git commit -m "chore(repo): 저장소 골격과 협업 규칙 추가" -m "Refs: #3"
git push -u origin feature/02-repo-init
```
- git status에서 renamed: README.md -> docs/PROMPT.md 가 보여야 한다

## 4. PR과 머지 (웹)
- base: develop ← compare: feature/02-repo-init
- 본문에 Closes #3
- 승인 후 Merge status → Squash and merge → Delete branch

## 5. 로컬 정리
```bash
git switch develop
git pull
git branch -D feature/02-repo-init
```
- 브랜치 이름은 develop (development 아님)
- 로컬 브랜치를 지워도 GitHub의 PR은 그대로 열려 있으므로 웹에서 머지 여부를 반드시 확인

## WSL 주의
- .gitattributes의 eol=lf로 Windows 편집기에서 CRLF가 들어와도 저장소에는 LF로 저장
- git config --global core.autocrlf input 설정과 함께 사용
