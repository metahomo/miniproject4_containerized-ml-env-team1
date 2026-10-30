# 작업 방법

## 1. 브랜치 생성
```bash
cd ~/miniproject4_containerized-ml-env-team1
git switch develop
git pull
git switch -c feature/01-issue-template
mkdir -p .github/ISSUE_TEMPLATE
```
- git switch develop: 통합 브랜치로 이동
- git pull: 원격의 최신 내용 받기
- git switch -c: 새 브랜치를 만들고 이동
- mkdir -p: 중간 폴더까지 한 번에 생성, 이미 있어도 오류 없음

## 2. 파일 작성
changes/ 의 파일 4개를 같은 경로에 만든다.
셸 리다이렉션으로 작성할 수 있다.
```bash
cat > .github/ISSUE_TEMPLATE/config.yml <<'END'
blank_issues_enabled: false
END
```
- cat > 파일: 표준 입력 내용을 파일로 저장
- <<'END' ... END: 사이의 내용을 그대로 입력으로 전달(변수 치환 없음)

## 3. 커밋과 push
```bash
git add .github
git status
git commit -m "chore(github): 이슈·PR 템플릿 추가" -m "Refs: #1"
git push -u origin feature/01-issue-template
```
- git add: 커밋 대상에 올림(출력 없음이 정상)
- git status: 올라간 파일 확인
- -m 두 번: 첫 번째는 제목, 두 번째는 본문
- push -u: 원격 브랜치를 만들고 추적 관계 설정

## 4. PR과 머지 (웹)
- Pull requests → New pull request
- base: develop ← compare: feature/01-issue-template
- 본문에 Closes #1 (머지 시 이슈 자동 종료)
- 승인 후 Squash and merge → Delete branch

## 5. 로컬 정리
```bash
git switch develop
git pull
git branch -D feature/01-issue-template
```
- branch -D: Squash 머지는 이력이 달라 -d가 거부하므로 -D로 삭제

## WSL 주의
- 저장소는 ~/ 아래에 클론한다(/mnt/c 아래는 권한·속도 문제)
- 원격 이름 오타 주의: origin
