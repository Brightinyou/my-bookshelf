# My Bookshelf

**책·논문·원고를 넣으면, 번역하고 요약해서 읽기 좋은 노트와 전자책으로 만들어 주는 프로그램입니다.**

PDF·Word(.docx)·한글(.hwp/.hwpx)·텍스트(.txt) 파일을 넣으면 → **요약 노트(Obsidian 위키) · Word 문서 · 한글 문서 · 전자책(EPUB)** 으로 받아 볼 수 있습니다.

[![Windows 내려받기](https://img.shields.io/badge/Windows-Setup.exe-0078D4?style=for-the-badge&logo=data%3Aimage%2Fsvg%2Bxml%3Bbase64%2CPHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHZpZXdCb3g9IjAgMCAyNCAyNCI%2BPHBhdGggZmlsbD0iI2ZmZiIgZD0iTTMgM2g4LjJ2OC4ySDNWM3ptOS44IDBIMjF2OC4yaC04LjJWM3pNMyAxMi44aDguMlYyMUgzdi04LjJ6bTkuOCAwSDIxVjIxaC04LjJ2LTguMnoiLz48L3N2Zz4K)](https://github.com/Brightinyou/my-bookshelf/releases/latest/download/Setup.exe)
[![macOS 내려받기](https://img.shields.io/badge/macOS-.pkg-000000?style=for-the-badge&logo=apple&logoColor=white)](https://github.com/Brightinyou/my-bookshelf/releases/latest/download/MyBookshelf.pkg)

> 🇬🇧 English: [README.en.md](README.en.md) · 📘 화면별 자세한 설명: [사용 설명서](docs/MANUAL.md)

---

## 이렇게 씁니다 (한눈에 보기)

```
① 설치  →  ② AI 연결  →  ③ 파일 넣기  →  ④ 결과 받기
```

1. 위 버튼으로 **설치 파일을 받아 설치**합니다. (아래 [설치하기](#설치하기))
2. 앱을 처음 열면 나오는 **«AI 연결»** 안내를 따라 AI를 연결합니다. (아래 [AI 연결하기](#ai-연결하기))
3. **텍스트 변환** 화면에 파일을 끌어다 놓고 **[▶ 시작]** 을 누릅니다.
4. 한 단계가 끝날 때마다 **다음 단계로 갈지 물어봅니다.** [예]를 누르며 따라가면 마지막에 결과 파일이 만들어집니다.

---

## 목차

1. [설치하기](#설치하기) — [Windows](#windows) · [macOS](#macos)
2. [AI 연결하기](#ai-연결하기)
3. [사용하기](#사용하기)
4. [결과 파일은 어디에?](#결과-파일은-어디에)
5. [자주 묻는 질문 · 문제 해결](#자주-묻는-질문--문제-해결)
6. [꼭 알아 두실 점 (저작권·개인정보)](#꼭-알아-두실-점-저작권개인정보)
7. [고급 · 개발자용](#고급--개발자용)

---

## 설치하기

<a id="windows"></a>

### <img src="docs/img/windows.svg" width="15" align="top" alt="Windows"> Windows

**1. 내려받기**
[**Setup.exe 내려받기 ⬇️**](https://github.com/Brightinyou/my-bookshelf/releases/latest/download/Setup.exe) (약 100MB)

> 브라우저가 내려받기를 막으면 [릴리스 페이지](https://github.com/Brightinyou/my-bookshelf/releases/latest) 아래쪽 **Assets** 에서 `MyBookshelf-Setup-v….zip` 을 받아 압축을 푸세요. 같은 `Setup.exe` 가 들어 있습니다.

**2. 실행 — 처음 한 번은 보안 경고가 뜹니다 ⚠️**
`Setup.exe` 를 더블클릭하면 파란 창(*"Windows의 PC 보호"*)이 뜰 수 있습니다. 개인이 만든 프로그램이라 뜨는 안내이니 걱정하지 않으셔도 됩니다.

- **[추가 정보]** → **[실행]** 을 누르세요.

**3. 설치**
- 언어(한국어/English)를 고르고 **[다음]** 을 누르다 보면 설치가 끝납니다. 보통 **1~2분** 걸립니다.
- 파이썬 같은 프로그램을 따로 설치하실 필요가 없습니다. 모두 설치 파일에 들어 있습니다.
- 컴퓨터에 앱 화면을 그리는 **Microsoft WebView2** 가 없으면 설치 중에 자동으로 받아 설치합니다(1분 안팎, 인터넷 필요). 이때 진행 막대가 좌우로 흐르면 정상입니다.

**4. 앱 열기**
설치 마지막 화면에서 **[마침]** 을 누르면 앱이 열립니다. 다음부터는 **바탕화면이나 시작 메뉴의 «My Bookshelf»** 를 누르세요.

이제 [AI 연결하기](#ai-연결하기)로 넘어가세요.

---

<a id="macos"></a>

### <img src="docs/img/apple.svg" width="14" align="top" alt="macOS"> macOS

**1. 내려받기**
[**MyBookshelf.pkg 내려받기 ⬇️**](https://github.com/Brightinyou/my-bookshelf/releases/latest/download/MyBookshelf.pkg)

> 파일이 수백 KB로 작은 것이 정상입니다. 필요한 것은 설치하면서 받아 옵니다.

**2. 실행 — 처음 한 번은 보안 경고가 뜹니다 ⚠️**
- 다운로드 폴더의 `MyBookshelf.pkg` 를 **control-클릭(또는 오른쪽 클릭) → 열기 → 열기** 로 실행하세요.
- 그래도 막히면: **Apple 메뉴 → 시스템 설정 → 개인정보 보호 및 보안** 에서 **[그래도 열기]** 를 누르세요.

**3. 설치**
**[계속] → [설치] → 맥 암호 입력**. 파이썬이 없으면 python.org에서 받아 자동으로 설치하므로, 인터넷 상태에 따라 **몇 분** 걸릴 수 있습니다. 설치 창을 닫지 마세요.

**4. 앱 열기**
설치가 끝나면 앱이 자동으로 열립니다. 다음부터는 **Launchpad** 나 **응용 프로그램** 폴더의 **My Bookshelf** 를 누르세요.

이제 [AI 연결하기](#ai-연결하기)로 넘어가세요.

---

## AI 연결하기

번역과 요약은 AI가 합니다. 앱을 처음 열면 **«AI 연결»** 안내가 나옵니다. 둘 중 **편한 쪽 하나**를 고르세요.

| | 구독 계정 | API 키 |
|---|---|---|
| **이런 분께** | ChatGPT Plus/Pro 나 Claude Pro/Max 를 **이미 구독 중**인 분 | 구독은 없고 **쓴 만큼만** 내고 싶은 분 |
| **요금** | 추가 요금 없음 (구독에 포함) | 쓴 만큼 나옴 |
| **준비** | 앱이 도구 설치와 로그인을 안내 | 키를 받아 붙여 넣기 |

### 구독 계정으로 연결 (추천)

1. «AI 연결» 안내에서 **구독 계정** 이 선택된 상태로 **[설정 창 열기]** 를 누릅니다.
2. 새 창이 뜨면 번호를 고릅니다: **1** Claude · **2** Codex(ChatGPT) · **3** 둘 다 · **4** 나중에
3. 필요한 도구를 자동으로 설치한 뒤 **브라우저 로그인 화면**이 열립니다. 평소 쓰는 계정으로 로그인하세요.
4. 앱으로 돌아와 **[다시 확인]** 을 누르면 연결이 끝납니다.

> **설정 창이 안 열리면** 안내 아래의 **«Claude 직접 설치 (명령 복사)»** 를 펼쳐 보세요. 복사 버튼으로 명령을 복사해 PowerShell(맥은 터미널)에 한 줄씩 붙여 넣으면 됩니다.

> **옵시디언(Obsidian)은?** 설정 창이 옵시디언도 설치할지 묻습니다. 옵시디언은 요약 노트를 서로 링크로 이어 보여 주는 **무료 메모 앱**입니다. 없어도 괜찮습니다 — 결과는 Word 문서로 받으실 수 있고, 나중에 설정에서 언제든 켤 수 있습니다.

### API 키로 연결

1. «AI 연결» 안내에서 **API 키** 를 고릅니다.
2. AI 서비스(Gemini·OpenAI·Anthropic)를 고르면 **키 발급 주소**가 나옵니다. 거기서 키를 받으세요.
3. 키를 붙여 넣고 **[저장]** 을 누르면 끝입니다. 키는 이 컴퓨터에만 저장됩니다.

### 나중에 바꾸려면

**⚙️ 설정 → AI 설정 → «AI 연결»** 한 칸에서 AI와 모델을 함께 고릅니다. **고르면 바로 적용**됩니다.

> 💡 **구독이 둘 다 있다면** «사용량 한도에 걸리면 다른 구독 AI로 이어받기» 를 켜 두세요. 한쪽이 한도에 걸려도 다른 쪽이 이어서 처리합니다. 화면 위쪽에 `1순위 › 2순위` 로 표시됩니다.

---

## 사용하기

화면 위쪽 메뉴에서 차례대로 진행합니다. 파일은 **끌어다 놓거나 [파일 선택]** 으로 넣습니다.

| 순서 | 메뉴 | 하는 일 |
|:---:|---|---|
| 1 | 📄 **텍스트 변환** | 파일에서 글자를 뽑아냅니다. 스캔한 PDF도 됩니다. |
| 2 | ✂️ **챕터 분할** | 책을 장(챕터)별로 나눕니다. |
| 3 | 🌐 **번역** | 외국어 문서를 한국어(또는 설정한 언어)로 옮깁니다. 한국어 문서는 건너뜁니다. |
| 4 | 📝 **문서요약** | 장마다 요약 노트를 만듭니다. |
| 5 | 📖 **문서출력** | Word · 한글 · 전자책(EPUB) · Obsidian 위키 중 원하는 형식으로 내보냅니다. |

- 각 단계는 **[▶ 시작]** 으로 시작하고, **[■ 중단]** 을 누르면 지금 하던 것까지만 하고 멈춥니다.
- 멈춘 작업은 **[▶ 시작]** 을 다시 누르면 **이어서** 합니다. 처음부터 다시 하지 않습니다.
- 한 단계가 끝나면 다음 단계로 갈지 묻습니다. **[예, 바로 진행]** 을 누르면 됩니다.

📘 버튼 하나하나의 설명은 [사용 설명서](docs/MANUAL.md)에 있습니다.

---

## 결과 파일은 어디에?

**문서** 폴더 안의 **My Bookshelf** 폴더에 저장됩니다.

| 폴더 | 들어 있는 것 |
|---|---|
| `3_챕터/책이름/` | 장별 원문 · 번역본 · 요약 |
| `5_위키문서(DOCX)/` | Word 문서 |
| `5_위키문서(HWPX)/` | 한글 문서 |
| `5_전자책(EPUB)/` | 전자책 |

Obsidian 위키 노트는 설정에서 고른 **옵시디언 보관함(Vault)** 폴더에 저장됩니다. 문서출력 화면의 **[폴더 열기]** 버튼으로 바로 열 수 있습니다.

---

## 자주 묻는 질문 · 문제 해결

**Q. «사용 가능한 AI가 없습니다» 라고 나와요.**
[AI 연결하기](#ai-연결하기)를 다시 따라 해 주세요. 구독 계정이라면 **[다시 확인]** 을 눌러 보세요.

**Q. 앱 창이 하얗게 비어 있어요. (Windows)**
앱 화면을 그리는 Microsoft WebView2 가 없는 경우입니다. 새 판(v1.5.0 이후)은 설치할 때 자동으로 넣어 주고, 그래도 없으면 **기본 브라우저로 앱을 엽니다.** 안내 창에 나온 주소로 [WebView2](https://go.microsoft.com/fwlink/p/?LinkId=2124703)를 설치하면 다음부터 앱 창으로 열립니다.

**Q. 새 판으로 올리고 싶어요.**
**⚙️ 설정 → 업데이트 확인** 을 누르면 됩니다. (아주 옛 판 v1.2.33 이전이라면 위 버튼으로 새 설치 파일을 받아 설치하세요.)

**Q. 업데이트했는데 예전 화면이 보여요.**
앱을 완전히 닫았다가 다시 여세요. 그래도 그대로면 시작 메뉴의 **«Stop My Bookshelf»** 를 누른 뒤 다시 여세요.

**Q. 스캔한 PDF도 되나요?**
됩니다. 글자가 이상하게 나오면 텍스트 변환 화면의 **«🔬 본문 품질 검사»** 를 눌러 AI로 다시 읽게 하세요(쪽수에 따라 몇 분~수십 분).

**Q. (맥) 앱 안에서 «업데이트 확인» 을 눌러도 판이 안 올라가요.**
v1.2.74 이전 `.pkg` 로 설치한 경우입니다. 터미널에서 아래를 한 번만 실행하거나, 최신 `.pkg` 로 다시 설치하세요.
```
sudo chown -R "$(whoami):staff" /Applications/MyBookshelf.app
```

**Q. 문제가 생겼을 때 어디를 보면 되나요?**
- Windows: `C:\Users\<사용자>\AppData\Local\My Bookshelf` 폴더의 `install.log`(설치), `launch-error.log`(실행)
- macOS: `~/Library/Application Support/MyBookshelf/` 폴더의 `install.log`, `app.log`

---

## 꼭 알아 두실 점 (저작권·개인정보)

- 이 프로그램은 **내가 이용할 권리가 있는 문서**를 **개인적으로** 읽기 쉽게 바꾸는 도구입니다. 만든 번역본·요약·전자책을 **다른 사람에게 나누거나 배포할 권리가 생기지는 않습니다.**
- **전자책(EPUB)에는 요약이 아니라 원문 전체**가 들어갑니다. 개인적인 용도로만 쓰세요.
- AI를 쓰면 문서 내용이 **외부 AI 서비스로 전송**됩니다. 민감한 개인정보나 공개되지 않은 원고는 넣지 마세요.
- AI가 만든 번역과 요약은 **틀릴 수 있습니다.** 인용하거나 제출하기 전에는 반드시 원문과 대조해 확인하세요.

<details>
<summary><b>저작권 및 면책 전문</b></summary>

**My Bookshelf** — © 2026 Brightinyou. 개인·비상업 연구 보조 용도로 제공됩니다.

**프로그램에 대하여**
- 이 프로그램의 저작권은 Brightinyou에게 있습니다. 개인적·학술적 용도로 사용·복제할 수 있으나, Brightinyou의 서면 동의 없이 재판매하거나 상업적으로 배포할 수 없습니다.
- 프로그램은 "있는 그대로(as-is)" 제공되며, 특정 목적 적합성이나 무결성을 보증하지 않습니다. 사용으로 인한 데이터 손실·손해에 대해 Brightinyou는 책임지지 않습니다.

**이용자 문서·생성 결과에 대하여**
- 이 프로그램은 **이용자가 이미 적법하게 이용할 권한을 가진 문서**를 변환·번역·요약하기 위한 개인용 도구입니다. 이 프로그램을 사용한다고 해서 원래 없던 권한이 생기지는 않으며, 생성된 EPUB·번역본·요약본을 제3자에게 배포·공유할 권한도 부여되지 않습니다. 어디까지 허용되는지는 나라와 그 문서를 얻은 경위에 따라 다릅니다.
- 원문 문서의 저작권·번역권·요약·재배포 가능 여부는 이용자 본인의 책임으로 확인해야 합니다. 이 프로그램은 법률·출판·학술 제출 요건을 자동 판정하지 않습니다.
- AI API 또는 CLI 도구를 활성화하면 문서의 일부 또는 전체가 외부 AI 서비스로 전송됩니다. 민감정보, 비공개 원고, 배포 권한이 불명확한 자료는 넣지 마세요.
- 생성된 번역·요약·위키 노트의 정확성·완전성은 보장되지 않습니다. 출판·제출·인용·대외 배포 전에는 반드시 원문과 결과물을 직접 대조해 검토하세요.

</details>

---

## 고급 · 개발자용

아래는 몰라도 앱을 쓰는 데 지장이 없습니다.

<details>
<summary><b>⚡ 명령 한 줄로 설치하기 (PowerShell·터미널이 익숙한 분)</b></summary>

**Windows (PowerShell)**
```powershell
irm https://github.com/Brightinyou/my-bookshelf/releases/latest/download/install-mybookshelf.ps1 -OutFile install-mybookshelf.ps1
powershell -ExecutionPolicy Bypass -File .\install-mybookshelf.ps1 -AI codex -Launch
```
`-AI codex`(기본) · `-AI claude` · `-AI both` · `-AI none` · `-NoLogin` · `-Obsidian` · `-TargetLang en` 을 쓸 수 있습니다.

**macOS (터미널)**
```bash
curl -fsSL https://github.com/Brightinyou/my-bookshelf/releases/latest/download/install-mybookshelf.sh -o install-mybookshelf.sh
bash install-mybookshelf.sh --ai codex --launch
```
`--ai codex`(기본) · `--ai claude` · `--ai both` · `--ai none` · `--obsidian` · `--target-lang en` 은 `bash install-mybookshelf.sh --help` 에서 볼 수 있습니다. 이 방법은 macOS 보안 경고를 만나지 않습니다.

</details>

<details>
<summary><b>🌐 화면 언어와 번역 언어</b></summary>

- `⚙️ 설정 → 언어` 는 **화면에 보이는 글자**의 언어(한국어/English)만 바꿉니다.
- 번역 결과의 언어는 `⚙️ 설정 → 🎯 번역 도착언어` 에서 따로 고릅니다. 번역본·요약·위키 노트에 함께 적용됩니다.
- 이미 만든 번역·요약은 도착언어를 바꿔도 자동으로 바뀌지 않습니다. 결과 파일을 지운 뒤 다시 실행하세요.

</details>

<details>
<summary><b>📂 데이터 폴더 전체 구조</b></summary>

설치 언어에 따라 폴더 이름이 한글/영문입니다.

```
0_업로드대기/            업로드·다운로드 대기 (처리 전)
1_원본PDF/               원본 PDF 보관
2_변환TXT/               변환된 TXT (완료/ = 분할 끝난 원본 보관)
3_챕터/<책>/              챕터·번역(_ko 등)·대역(_bilingual)·요약(_wiki.md)·전체요약
5_전자책(EPUB)/          EPUB (본문 전체)
5_위키문서(DOCX)/        Word 문서
5_위키문서(HWPX)/        한글 문서
실패/, 로그/              실패 파일·로그
```

설정은 `~/.config/mybookshelf/` 에 저장됩니다.

</details>

<details>
<summary><b>📖 용어집 — 요약 노트의 «한글(원어)» 표기 통일</b></summary>

용어집은 보관함의 `_glossary.json` 에 저장되어, 보관함을 여러 기기에서 공유하면 함께 따라갑니다.

```
Windows   glossary.bat            현황  /  --apply 수정  /  --check 사전 대조
macOS     cd core && python3 -m services.glossary          (--apply 로 수정)
          cd core && python3 -m services.termcheck         (사전 대조)
```

- `--apply` 는 보관함을 통째로 백업한 뒤 고칩니다. 손대는 범위는 **«## 핵심 키워드» 구획의 대소문자·공백 차이뿐**입니다.
- 원어 자체가 다른 것(`책임` → responsibility / responsabilité / Verantwortung)은 자동으로 손대지 않고 검토 목록으로만 보여 줍니다.
- `termcheck` 가 못 찾은 용어는 «미확인»이지 «오류»가 아닙니다.

</details>

<details>
<summary><b>🛠 개발자용 — 코드 구조와 빌드</b></summary>

```
core/                앱 핵심 코드
  pipeline_app.py    Streamlit UI (전 단계)
  desktop.py         앱 창(PyWebView) 실행기
  services/          처리 로직 (convert/translate/chapters/wiki/i18n …)
  chapter_wiki.py    챕터 분할 + 요약 생성
  llm_providers.py   AI 공급자 (Gemini/OpenAI/Anthropic/Claude CLI/Codex CLI) · 구독 CLI 이어받기
dev/                 빌드 스크립트 (build_mac_app.sh, bump_version.py …)
dev/installer/       Windows 설치 스크립트(MyBookshelf.iss) · 런타임/WebView2 준비 스크립트
```

- Windows 배포본: `.github/workflows/build-windows.yml` — 파이썬 런타임(`fetch-runtime.ps1`)과 WebView2 부트스트래퍼(`fetch-webview2.ps1`)를 받아 `Setup.exe` 로 묶습니다. 태그 푸시 때 릴리스에 첨부됩니다.
- macOS 빌드: `dev/build_mac_app.sh` → `.app`, `dev/build_mac_pkg.sh` → `MyBookshelf.pkg`
- macOS 설치 자동화: `dev/installer/mac_postinstall.sh` (파이썬·venv)
- 무인 설치 스크립트: `install-mybookshelf.sh` (macOS) · `install-mybookshelf.ps1` (Windows)
- 개발 실행: `streamlit run core/pipeline_app.py`
- 테스트: `PYTHONPATH=core python -m unittest discover -s core/tests`

</details>
