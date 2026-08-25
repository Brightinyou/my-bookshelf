# 저장소 하나로 합치기 — 실행 순서 (2026-08-25 준비)

## 왜

지금 GitHub에 둘이 있다.

| | 저장소 | 상태 |
|---|---|---|
| `origin` | `Brightinyou/my-bookshelf-for-mac` | **30커밋 앞섬**(오늘까지 최신) |
| `pc` | `Brightinyou/my-bookshelf-for-pc` | 1커밋 — **그 내용은 mac에도 있음** |

**갈라진 게 아니라 한쪽이 뒤처진 것뿐이다.** 확인한 사실:

- pc에만 있는 파일 **0개**. mac 저장소가 `setup.bat`·`start.bat`·`start-app.vbs`·
  `stop-app.bat`·`install-obsidian.bat`·`MyBookshelf.exe`를 **이미 갖고 있다**
- pc에만 있는 커밋은 「LICENSE 저작자 표기 변경」 하나인데, **LICENSE 파일 내용이
  두 저장소에서 완전히 같다**(차이 0)
- 플랫폼 차이는 파일이 아니라 **실행 시점 분기**로 처리된다 — `sys.platform`이
  6개 파일 17군데

### 나눠 둔 대가

- **"origin 정본 · pc/main 직접 merge 금지"** 라는 규칙 자체가 나눔이 만든 마찰이다
- 사흘 만에 30커밋이 벌어졌다
- ★**같은 수정이 두 경로로 들어갔다** — 저작권 문구를 두 번 고쳤고, 그래서 한쪽을
  "안 합쳐진 작업"으로 잘못 읽었다(2026-08-25 `copyright-hardening` 정리 과정)

---

## 맥에서 이미 해 둔 것 ✅

- `main` = `origin/main` = `8b5a24a` (밀지 않은 커밋 0)
- 유령 브랜치 정리: `copyright-hardening`·`feat/text-quality-reocr` 삭제
- **pc 저장소 이력 보존용 태그**: `archive/pc-main` → `132e3ba`
  (pc 저장소를 아카이브해도 이력이 이 맥에 남는다)

---

## ① PC에서 — 먼저 확인 (⚠️ 이것부터)

**PC 로컬에 안 올린 작업이 있는지는 맥에서 볼 수 없다.** PC에서:

```bash
git status                     # 수정 중인 파일이 있는가
git log --oneline origin/main..HEAD   # 안 올린 커밋이 있는가
git stash list                 # 치워 둔 작업이 있는가
```

**셋 다 비어 있어야** 아래로 넘어간다. 뭔가 있으면 먼저 push하거나 백업한다.

---

## ② GitHub 웹에서 (사람이 해야 함)

1. `my-bookshelf-for-mac` → **Settings → Rename** → `my-bookshelf`
   - GitHub이 옛 주소를 새 주소로 넘겨주므로 당장 깨지지는 않는다
2. `my-bookshelf-for-pc` → **Settings → Archive this repository**
   - ★**지우지 말고 아카이브**한다. 읽기 전용이 될 뿐 되돌릴 수 있다

---

## ③ 맥에서 (이름 변경 뒤)

```bash
cd ~/Projects/my-bookshelf
git remote set-url origin https://github.com/Brightinyou/my-bookshelf.git
git remote remove pc                    # 아카이브했으므로 더는 필요 없다
git push origin archive/pc-main         # pc 이력을 정본에 남긴다(선택)
git remote -v && git fetch origin && git status -sb
```

---

## ④ PC에서 (마무리)

```bash
git remote set-url origin https://github.com/Brightinyou/my-bookshelf.git
git remote remove pc 2>/dev/null
git fetch origin
git checkout main
git reset --hard origin/main      # ⚠️ PC 로컬 변경이 없다는 것을 ①에서 확인한 뒤에만
```

이후로는 양쪽 다 `git pull` / `git push` 하나로 끝난다. **정본은 하나다.**

---

## 되돌리려면

- 저장소 이름: GitHub에서 다시 바꾸면 된다
- pc 저장소: 아카이브 해제
- pc 이력: 맥의 태그 `archive/pc-main`
