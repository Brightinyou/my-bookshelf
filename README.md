# My Bookshelf

**책·논문·원고를 읽기 좋은 요약 노트와 전자책으로 바꾸는 개인 연구 도구.**
PDF·DOCX·HWP·HWPX·TXT를 넣으면 번역과 요약을 거쳐 **EPUB·Word(.docx)·한글(.hwpx)·Obsidian 위키**로 내보냅니다.

[![Windows 내려받기](https://img.shields.io/badge/Windows-Setup.exe-0078D4?style=for-the-badge&logo=data%3Aimage%2Fsvg%2Bxml%3Bbase64%2CPHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHZpZXdCb3g9IjAgMCAyNCAyNCI%2BPHBhdGggZmlsbD0iI2ZmZiIgZD0iTTMgM2g4LjJ2OC4ySDNWM3ptOS44IDBIMjF2OC4yaC04LjJWM3pNMyAxMi44aDguMlYyMUgzdi04LjJ6bTkuOCAwSDIxVjIxaC04LjJ2LTguMnoiLz48L3N2Zz4K)](https://github.com/Brightinyou/my-bookshelf/releases/latest/download/Setup.exe)
[![macOS 내려받기](https://img.shields.io/badge/macOS-.pkg-000000?style=for-the-badge&logo=apple&logoColor=white)](https://github.com/Brightinyou/my-bookshelf/releases/latest/download/MyBookshelf.pkg)

> 🇬🇧 English manual: [README.en.md](README.en.md) · 📘 각 탭 상세: [사용 설명서](docs/MANUAL.md)

Windows와 macOS 모두 지원합니다. 같은 코어(`core/`)를 쓰고 **설치 방법만 다릅니다** — 아래 [2. 설치](#2-설치)에서 쓰시는 운영체제 부분만 보시면 됩니다.

---

## ⚡ 3분 빠른 시작

| | 할 일 |
|---|---|
| **1. 설치** | 위 배지에서 <img src="docs/img/windows.svg" width="15" align="top" alt="Windows"> `Setup.exe` 또는 <img src="docs/img/apple.svg" width="14" align="top" alt="macOS"> `MyBookshelf.pkg`를 받아 실행합니다. 처음 한 번은 **보안 경고를 통과**해야 하고, 설치 중 파이썬 환경 준비에 몇 분 걸립니다. → [자세히](#2-설치) |
| **2. AI 연결** | macOS PKG는 설치 직후 터미널에서 **Claude·Codex·둘 다·나중에** 중 하나를 묻습니다. 건너뛰었다면 앱의 `⚙️ 설정` 탭에서 CLI를 켜거나 API 키를 넣습니다. → [자세히](#3-첫-설정--ai-연결) |
| **3. 문서 넣기** | `📄 텍스트 변환` 탭에 파일을 끌어다 놓고 **[▶ 시작]**. 이후 단계는 **팝업이 물어보는 대로** 이어집니다. |
| **4. 결과 받기** | `📖 출력` 탭에서 EPUB·Word·한글·Obsidian 중 원하는 형식을 켜고 **[▶ 시작]**. |

---

## 목차

1. [이 프로그램은 무엇인가](#1-이-프로그램은-무엇인가)
2. [설치](#2-설치) — [<img src="docs/img/windows.svg" width="15" align="top" alt="Windows"> Windows](#windows) · [<img src="docs/img/apple.svg" width="14" align="top" alt="macOS"> macOS](#macos)
3. [첫 설정 — AI 연결](#3-첫-설정--ai-연결)
4. [작업 흐름](#4-작업-흐름)
5. [시작 · 중단 · 이어하기](#5-시작--중단--이어하기)
6. [언어 설정과 번역](#6-언어-설정과-번역)
7. [데이터 위치](#7-데이터-위치)
8. [문제 해결](#8-문제-해결)
9. [저작권 및 면책](#9-저작권-및-면책)

---

## 1. 이 프로그램은 무엇인가

책, 논문, 원고 등 PDF·DOCX·HWP·HWPX·TXT를 넣으면, 다음 단계를 거쳐 **읽기 좋은 요약 위키 노트**를 만듭니다. (Obsidian 보관함(Vault)에 저장 가능)

```
PDF/DOCX/HWP/HWPX/TXT  →  텍스트 변환  →  챕터 분할  →  번역(도착언어가 아닌 문서)  →  문서요약  →  EPUB · Word(.docx) · 한글(.hwpx) · Obsidian Wiki (모두 가능)
```

- **PDF**는 텍스트 레이어가 있으면 바로 처리됩니다. **스캔본이거나 OCR 품질이 나쁜 PDF**도 됩니다 — 텍스트 변환 탭의 «🔬 본문 품질 검사»가 불량을 짚어 주면 **AI로 다시 읽습니다**(쪽수에 따라 몇 분~수십 분). **DOCX·HWP·HWPX·TXT**는 그대로 바로 처리됩니다.
- 번역·요약·위키 생성에는 **AI**를 씁니다. API 키를 넣거나, Claude/ChatGPT 구독 CLI를 켜서 사용합니다.
- 결과 노트는 **저자·핵심 요약·장별 개요·핵심 인용·핵심 키워드**를 담고, 어려운 원전은 용어 원어 병기·풀어 쓰기로 읽기 쉽게 만듭니다.

---

## 2. 설치

<div align="center">

### ⬇️ 내려받기

| | 받을 파일 |
|---|---|
| <img src="docs/img/windows.svg" width="15" align="top" alt="Windows"> **Windows** | [**Setup.exe** ⬇️](https://github.com/Brightinyou/my-bookshelf/releases/latest/download/Setup.exe) |
| <img src="docs/img/apple.svg" width="14" align="top" alt="macOS"> **macOS** | [**MyBookshelf.pkg** ⬇️](https://github.com/Brightinyou/my-bookshelf/releases/latest/download/MyBookshelf.pkg) |

위 링크를 누르면 **최신 판이 바로 내려받아집니다.** 예전 판이나 다른 파일은 [릴리스 페이지](https://github.com/Brightinyou/my-bookshelf/releases/latest)에 있습니다.

⚡ 터미널·PowerShell 이 익숙하시면 **한 줄로 끝내는 방법**도 있습니다 — 파이썬·앱·AI 연결까지 한 번에. [<img src="docs/img/windows.svg" width="15" align="top" alt="Windows"> Windows](#oneline-win) · [<img src="docs/img/apple.svg" width="14" align="top" alt="macOS"> macOS](#oneline-mac)

</div>

---

<a id="windows"></a>

### <img src="docs/img/windows.svg" width="15" align="top" alt="Windows"> Windows

#### 1단계 — 내려받기

- **[`Setup.exe` 내려받기 ⬇️](https://github.com/Brightinyou/my-bookshelf/releases/latest/download/Setup.exe)** — 권장. 바로 실행하면 됩니다.
- 브라우저가 `.exe` 내려받기를 막으면, [릴리스 페이지](https://github.com/Brightinyou/my-bookshelf/releases/latest)의 **Assets**에서 `MyBookshelf-Setup-vX.Y.Z.zip` 을 받으세요. 압축을 풀면 같은 `Setup.exe`가 나옵니다.

#### 2단계 — 실행 (처음 한 번만: 보안 경고 통과 ⚠️)

`Setup.exe`를 더블클릭하면 Windows가 *"PC를 보호했습니다"* 라는 파란 창을 띄웁니다. 개인이 만들어 나누는 프로그램이라 **상용 코드 서명 인증서를 갖추지 않았을 때 뜨는 안내**입니다.

1. 파란 창에서 **[추가 정보]** 를 누릅니다.
2. 아래에 나타나는 **[실행]** 버튼을 누릅니다.

#### 3단계 — 설치 언어 고르기

한국어 / English 중 고릅니다. 앱 화면에 쓰이는 언어이며, 나중에 **설정 탭에서 언제든 바꿀 수 있습니다.**

#### 4단계 — 파이썬 (자동)

파이썬 3.14가 없으면 설치 프로그램이 *"자동으로 받아 설치할까요?"* 라고 묻습니다. **[예]** 를 누르면 알아서 내려받아 설치합니다. 이미 3.10 이상이 설치돼 있으면 이 단계는 건너뜁니다.

#### 5단계 — 첫 실행 준비 (자동)

설치 마지막에 *"Preparing Python environment"* 가 뜨고 **몇 분간 멈춘 듯 보입니다 — 정상입니다.** 필요한 패키지를 받는 중입니다(네트워크에 따라 **5~20분**).

- 설치 위치: `C:\Users\<사용자>\AppData\Local\My Bookshelf`
- 진행 기록: 그 폴더의 `install.log`
- 실행이 안 되면: 같은 폴더의 `launch-error.log`

#### 6단계 — AI 연결

설치가 끝나면 **My Bookshelf - Additional setup** PowerShell 창이 열립니다. **Claude·Codex·둘 다·나중에** 중 하나를 고르면 선택한 CLI를 설치하고, 이어서 옵시디언 설치 여부를 묻습니다. 그 뒤 브라우저 로그인 창을 바로 엽니다. **둘 다**를 고르면 Claude 로그인 뒤 Codex 로그인이 이어지며, 준비된 CLI와 옵시디언은 앱 설정에도 자동으로 등록됩니다.

CLI 대신 API를 쓰려면 **나중에**를 고른 뒤 앱의 `⚙️ 설정`에서 Gemini·OpenAI·Anthropic 중 하나의 API 키를 넣습니다.

#### 7단계 — 실행

바탕화면 또는 시작 메뉴의 **My Bookshelf** 아이콘을 누릅니다. 두 번째 실행부터는 몇 초면 창이 뜹니다.

> **업데이트**: 앱의 **설정 탭 → 업데이트 확인**으로 새 판을 받을 수 있습니다.
> 다만 **v1.2.33 이전 판을 쓰고 계셨다면 이번 한 번은 직접 받아 설치**해야 합니다(저장소가 통합되기 전 판이라 옛 주소를 보고 있습니다).

<a id="oneline-win"></a>

> [!TIP]
> ### <img src="docs/img/windows.svg" width="15" align="top" alt="Windows"> Windows — ⚡ 한 줄로 끝내기
>
> *위 1~7단계를 건너뜁니다.*
>
> PowerShell 이 익숙하시면, **파이썬·앱·AI CLI·기본 설정까지 스크립트 하나로** 끝납니다.
>
> ```powershell
> irm https://github.com/Brightinyou/my-bookshelf/releases/latest/download/install-mybookshelf.ps1 -OutFile install-mybookshelf.ps1
> powershell -ExecutionPolicy Bypass -File .\install-mybookshelf.ps1 -AI claude -Launch
> ```
>
> `-AI codex`(기본) · `-AI claude` · `-AI both` · `-AI none` · `-NoLogin` · `-Obsidian`(옵시디언도 설치) · `-TargetLang en` 등을 줄 수 있습니다.
>
> 기본적으로 선택한 구독 CLI의 브라우저 로그인도 바로 시작합니다. 자동화 환경에서는 `-NoLogin`으로 건너뛸 수 있으며, API 키는 앱에서 직접 입력합니다.

---

<a id="macos"></a>

### <img src="docs/img/apple.svg" width="14" align="top" alt="macOS"> macOS

#### 1단계 — 내려받기

- **[`MyBookshelf.pkg` 내려받기 ⬇️](https://github.com/Brightinyou/my-bookshelf/releases/latest/download/MyBookshelf.pkg)** — 이것만 받으면 됩니다. 더블클릭하면 설치 관리자가 **응용 프로그램** 폴더에 넣어 줍니다.
- 맥 관리자 암호를 쓸 수 없다면, [릴리스 페이지](https://github.com/Brightinyou/my-bookshelf/releases/latest)의 **Assets**에서 `MyBookshelf-vX.Y.Z-mac.zip` 을 받으세요. 압축을 풀면 앱 파일만 나옵니다.

> 파일 크기가 수백 KB로 작습니다 — **정상입니다.** `.pkg` 설치 중 파이썬 환경을 내려받아 준비합니다.

#### 2단계 — 처음 한 번만: 보안 경고 통과 ⚠️

개인이 만들어 나누는 프로그램이라 Apple 서명·공증을 거치지 않았을 때 *"확인되지 않은 개발자"* 경고가 뜰 수 있습니다.

- **`.pkg`**: 다운로드 폴더의 `MyBookshelf.pkg`를 **control-클릭(또는 우클릭) → 열기 → 열기**로 실행합니다.
- **zip**: 먼저 `MyBookshelf.app`을 **응용 프로그램** 폴더로 옮긴 다음, 그 아이콘을 **control-클릭 → 열기 → 열기**로 실행합니다. 다운로드 폴더에서 바로 실행하면 macOS의 임시 격리 경로 때문에 아무 반응 없이 멈출 수 있습니다.
- 그래도 차단되면 한 번 더블클릭해 경고를 띄운 뒤 **Apple 메뉴 → 시스템 설정 → 개인정보 보호 및 보안 → 그래도 열기(또는 확인 없이 열기)**를 누릅니다.

#### 3단계 — 앱과 파이썬 환경 설치

`.pkg` 설치 관리자에서 **[계속] → [설치] → 맥 암호**를 입력합니다. 설치 프로그램은 다음을 자동으로 처리합니다.

1. Python 3.10 이상을 찾되 현재 Mac과 아키텍처가 맞는 설치본을 우선 사용합니다.
2. 없으면 python.org의 Python 3.14.6을 받아 SHA256을 확인한 뒤 설치합니다.
3. 앱 전용 가상환경을 만들고 필요한 Python 패키지를 설치합니다.

네트워크에 따라 몇 분 걸릴 수 있으므로 설치 관리자를 닫지 마세요.

> **zip은 다릅니다.** Mac에 Python 3.10 이상이 이미 있어야 합니다. 없으면 첫 실행 때 python.org 설치 페이지를 안내하며, Python을 설치한 뒤 앱을 다시 열면 가상환경과 패키지를 준비합니다.

#### 4단계 — 터미널에서 AI 고르기

`.pkg`의 Python 준비가 끝나면 **My Bookshelf — 추가 설정** 터미널 창이 열립니다.

| 선택 | 설치 내용 | 예상 추가 용량 |
|---|---|---:|
| **1. Claude** | Claude Code CLI · Claude Pro/Max 구독 | 약 293MB |
| **2. Codex** | Codex CLI · ChatGPT Plus/Pro 구독 | 약 363MB(Node.js 포함) |
| **3. 둘 다** | Claude와 Codex 모두 설치 · 기본 작업 AI는 Codex | 약 656MB |
| **4. 나중에** | CLI를 설치하지 않고 앱에서 API 키 설정 | 0MB |

번호를 입력한 뒤 Enter를 누릅니다. 아무것도 입력하지 않고 Enter를 누르면 기본값인 **4. 나중에**가 선택됩니다. 이미 설치된 CLI는 다시 받지 않으며 추가 용량도 0MB로 표시됩니다.

> Homebrew가 이미 있으면 Node.js 설치에 사용합니다. Homebrew가 없다고 새로 설치하지는 않으며, 공식 Node.js LTS를 사용자 폴더에 직접 설치합니다.

#### 5단계 — 옵시디언 고르기

AI 선택이 끝나면 옵시디언을 설치할지 묻습니다(약 515MB). 기본값은 **아니요**입니다.

- **예**: Homebrew가 있으면 사용하고, 없으면 공식 최신 macOS DMG를 받아 `~/Applications`에 설치합니다.
- **아니요**: 기본 출력을 **EPUB + Word**로 둡니다. 옵시디언을 설치하면 **EPUB + 옵시디언 위키**로 맞춥니다.
- 이미 `/Applications` 또는 `~/Applications`에 설치돼 있으면 다운로드를 건너뜁니다.

출력 형식과 옵시디언 보관함은 나중에 앱의 `⚙️ 설정`에서 언제든 바꿀 수 있습니다.

#### 6단계 — CLI 로그인과 앱 실행

CLI를 골랐다면 설치 창이 곧바로 브라우저 로그인 창을 엽니다. **둘 다**를 골랐다면 Claude 로그인 뒤 Codex 로그인이 이어집니다. 로그인 뒤에는 새 터미널을 열어도 `claude`와 `codex`를 바로 쓸 수 있도록 경로를 자동 등록합니다.

로그인이나 설치를 취소했어도 앱의 `⚙️ 설정`에서 다시 켜거나 API 키를 넣을 수 있습니다. 마지막 Enter는 추가 설정을 끝냅니다.

그다음 Launchpad 또는 응용 프로그램 폴더에서 **My Bookshelf**를 실행합니다. `.pkg` 설치본은 Python 환경이 이미 준비돼 있어 바로 열립니다.

> 설치 기록: `~/Library/Application Support/MyBookshelf/install.log`<br>
> 앱 실행 기록: `~/Library/Application Support/MyBookshelf/app.log`

<a id="oneline-mac"></a>

> [!TIP]
> ### <img src="docs/img/apple.svg" width="14" align="top" alt="macOS"> macOS — ⚡ 한 줄로 끝내기
>
> *위 1~6단계를 건너뜁니다.*
>
> 터미널이 익숙하시면, 내려받기부터 **파이썬·앱·AI CLI·기본 설정까지 스크립트 하나로** 끝납니다. `.pkg`도 파이썬과 선택한 AI CLI·옵시디언을 설치하며, 이 방법은 옵션을 명령에 미리 적는 무인 설치입니다.
>
> ```bash
> curl -fsSL -O https://github.com/Brightinyou/my-bookshelf/releases/latest/download/install-mybookshelf.sh
> bash install-mybookshelf.sh --ai claude --launch
> ```
>
> `--ai codex`(기본) · `--ai none` · `--obsidian`(옵시디언도 설치) · `--target-lang en` 등을 줄 수 있습니다. `bash install-mybookshelf.sh --help` 로 전부 볼 수 있습니다.
>
> **이 방법은 보안 경고를 만나지 않습니다** — `installer` 명령으로 설치하기 때문입니다.
> 자동화되지 않는 것은 둘뿐입니다 — **구독 CLI 브라우저 로그인, API 키 입력.**

---

## 3. 첫 설정 — AI 연결

앱의 `⚙️ 설정` 탭에서 **둘 중 하나**를 준비합니다. **AI 모델은 설정에서 한 번만 고르면** 모든 단계가 그 모델을 씁니다.

- **AI 구독(CLI)** — API 키 없이 구독으로 사용 (**권장**). 우선순위가 API 키보다 높습니다.
- **AI API 키** — Gemini / OpenAI / Anthropic 키를 직접 입력. 쓴 만큼 과금됩니다.

---

### 처음이신가요? — CLI 설치하기

이미 **ChatGPT Plus/Pro** 나 **Claude Pro/Max** 를 쓰고 계시다면, **추가 요금 없이** 그 구독으로 이 앱을 돌릴 수 있습니다. 둘 중 하나만 있으면 됩니다.

#### 준비물 — Node.js

두 CLI 모두 Node.js가 필요합니다. 한 번만 설치하면 됩니다.

- [**Node.js 내려받기**](https://nodejs.org/) — **LTS** 라고 적힌 쪽을 받아 설치하세요.
- 설치 확인: 터미널(Windows는 **PowerShell**, macOS는 **터미널**)을 열고
  ```
  node --version
  ```
  `v20.x` 처럼 나오면 준비된 것입니다.

#### ① ChatGPT를 쓰신다면 — Codex CLI

```
npm install -g @openai/codex
codex
```

`codex` 를 처음 실행하면 브라우저가 열리며 ChatGPT 로그인을 묻습니다. 한 번만 하면 됩니다.

- 안내: [Codex CLI 문서](https://developers.openai.com/codex/cli/)

#### ② Claude를 쓰신다면 — Claude Code CLI

```
npm install -g @anthropic-ai/claude-code
claude
```

`claude` 를 처음 실행하면 브라우저가 열리며 Claude 로그인을 묻습니다. 한 번만 하면 됩니다.

- 안내: [Claude Code 설치 문서](https://docs.claude.com/en/docs/claude-code/setup)

#### 마지막 — 앱에서 켜기

설치·로그인을 마쳤으면 **My Bookshelf를 껐다 켜고**, `⚙️ 설정` 탭에서 해당 토글을 켜면 됩니다. 앱이 알아서 찾습니다.

> 잘 안 되면: 터미널에서 `codex` 또는 `claude` 를 쳤을 때 실행되는지 먼저 확인하세요.
> 그 명령이 실행되지 않으면 앱도 찾지 못합니다.

---

### API 키로 쓰시려면

`⚙️ 설정` 탭에 키를 붙여 넣으면 됩니다.

- [Google AI Studio (Gemini)](https://aistudio.google.com/apikey)
- [OpenAI Platform](https://platform.openai.com/api-keys)
- [Anthropic Console](https://console.anthropic.com/settings/keys)

> 구독(CLI)과 API 키가 둘 다 있으면 **구독이 우선**입니다.

---

또한 `⚙️ 설정 → 옵시디언(Obsidian) 보관함 설정`에서 위키 노트를 저장할 폴더(Vault)를 확인·변경합니다.

---

## 4. 작업 흐름

상단 메뉴에서 다섯 단계를 오갑니다. 각 탭의 업로드 영역은 **파일 선택·끌어다 놓기** 모두 됩니다.

| 단계 | 하는 일 |
|---|---|
| **① 📄 텍스트 변환** | PDF·DOCX·HWP·HWPX·TXT에서 본문을 뽑아 TXT로 저장합니다. URL·DOI·arXiv 번호로 논문을 바로 받아올 수도 있습니다. |
| **② ✂️ 챕터 분할** | 책 TXT를 장 단위 파일로 나눕니다. 나눌 필요가 없으면 통째로 다음 단계로 보냅니다. |
| **③ 🌐 번역** | 원문 언어를 자동으로 감지해 설정한 **도착언어**로 옮깁니다. 원문·번역을 나란히 둔 대역본도 만들 수 있습니다. |
| **④ 📝 문서요약** | 장별 요약 노트를 만듭니다 — 저자·핵심 요약·개요·핵심 인용·핵심 키워드. 분량은 원문 대비 5~40%로 조절합니다. |
| **⑤ 📖 출력** | **EPUB · Word(.docx) · 한글(.hwpx) · Obsidian 위키** 중 원하는 것을 켜서 내보냅니다(여러 개 동시 가능). |

> **단계가 끝나면 팝업이 다음 작업을 묻습니다.** **[예, 바로 진행]** 을 누르면 방금 처리한 책만 다음 단계로 넘어가고, 여러 권을 한꺼번에 고르려면 **[직접 화면에서 선택]** 으로 대기 목록 화면을 쓰면 됩니다.

> ⚠️ **EPUB은 요약이 아니라 원문 전체**를 담습니다 — 이용 권한이 있는 문서에 한해, 본인의 개인적 사용 범위에서만 쓰세요. ([9. 저작권 및 면책](#9-저작권-및-면책))

📘 각 탭의 버튼·옵션 하나하나는 **[사용 설명서](docs/MANUAL.md)** 에 정리해 두었습니다.

---

## 5. 시작 · 중단 · 이어하기

챕터 분할·번역·문서요약·위키반영의 AI 작업은 **[▶ 시작]** 을 누르면 처리 화면만 남고 다른 기능·탭 이동이 **잠깁니다**(실수로 작업을 벗어나는 것 방지).

- 처리 화면에는 진행률과 항목별 결과가 표시됩니다.
- **[■ 중단]** 을 누르면 **현재 항목까지 마친 뒤** 멈추고 전체 화면이 돌아옵니다.
- 남은 작업은 대기 목록에 그대로 남아 **[▶ 시작]** 을 다시 누르면 이어서 처리됩니다.
- 대기 목록에서 **[🗑 삭제]** 로 잘못 넣은 작업을 뺄 수 있습니다.

---

## 6. 언어 설정과 번역

`⚙️ 설정 → 언어`는 화면에 표시되는 언어(한국어/English)만 바꿉니다.

- 번역 결과의 언어는 바로 아래의 `⚙️ 설정 → 🎯 번역 도착언어`에서 따로 고릅니다. 이 선택은 번역본·챕터 요약·위키 노트에 함께 적용됩니다.
- 화면 언어를 English로 두어도 번역 단계는 그대로 쓸 수 있습니다. 두 설정은 서로 무관합니다.
- 이미 만든 번역본·요약은 도착언어를 바꿔도 변환되지 않습니다. 필요한 결과 파일을 지운 뒤 다시 실행하세요.

---

## 7. 데이터 위치

기본 데이터 폴더(설치 언어에 따라 폴더명이 한글/영문):

```
0_업로드대기/            업로드·다운로드 대기 (처리 전)
1_원본PDF/               원본 PDF 보관
2_변환TXT/               변환된 TXT (완료/ = 분할 끝난 원본 보관)
3_챕터/<책>/              챕터·번역(_ko 등 도착언어)·대역(_bilingual)·요약(_wiki.md)·전체요약이 함께 있는 작업장
5_전자책(EPUB)/          EPUB으로 내보낸 전자책 (본문 전체)
5_위키문서(DOCX)/        DOCX로 내보낸 문서 (‘DOCX 문서 생성’ 선택 시, 언어 설정과 무관하게 이 이름 고정)
5_위키문서(HWPX)/        HWPX로 내보낸 문서 (‘HWPX 문서 생성’ 선택 시, 언어 설정과 무관하게 이 이름 고정)
실패/, 로그/              실패 파일·로그
```

위키 노트는 별도 Obsidian 보관함(Vault)에 저장됩니다(`⚙️ 설정`에서 선택). EPUB·Word(.docx)·한글(.hwpx)은 각각 위 `5_전자책(EPUB)/`·`5_위키문서(DOCX)/`·`5_위키문서(HWPX)/`에 저장됩니다. 설정은 `~/.config/mybookshelf/config.json`(macOS/Linux)에 저장됩니다.

---

## 8. 문제 해결

- **"사용 가능한 AI가 없습니다"** — `⚙️ 설정`에서 API 키를 넣거나 CLI 구독(Claude/Codex)을 켜세요.
- **업데이트했는데 옛 화면이 보임** — 앱을 완전히 종료 후 다시 여세요(실행 중인 서버가 남아 있을 수 있습니다).
- **스캔 PDF** — 그대로 넣으시면 됩니다. 본문이 엉망으로 나오면 텍스트 변환 탭의 «🔬 본문 품질 검사»로 AI에 다시 읽히세요.
- (Windows) 설치·실행 오류는 설치 폴더의 `install.log` / `launch-error.log`를 확인하세요.

---

## 9. 저작권 및 면책

**My Bookshelf** — © 2026 Brightinyou. 개인·비상업 연구 보조 용도로 제공됩니다.

**프로그램에 대하여**
- 이 프로그램의 저작권은 Brightinyou에게 있습니다. 개인적·학술적 용도로 사용·복제할 수 있으나, Brightinyou의 서면 동의 없이 재판매하거나 상업적으로 배포할 수 없습니다.
- 프로그램은 "있는 그대로(as-is)" 제공되며, 특정 목적 적합성이나 무결성을 보증하지 않습니다. 사용으로 인한 데이터 손실·손해에 대해 Brightinyou는 책임지지 않습니다.

**이용자 문서·생성 결과에 대하여**
- 이 프로그램은 **이용자가 이미 적법하게 이용할 권한을 가진 문서**를 변환·번역·요약하기 위한 개인용 도구입니다. 이 프로그램을 사용한다고 해서 원래 없던 권한이 생기지는 않으며, 생성된 EPUB·번역본·요약본을 제3자에게 배포·공유할 권한도 부여되지 않습니다. 어디까지 허용되는지는 나라와 그 문서를 얻은 경위에 따라 다릅니다.
- 원문 문서의 저작권·번역권·요약·재배포 가능 여부는 이용자 본인의 책임으로 확인해야 합니다. 이 프로그램은 법률·출판·학술 제출 요건을 자동 판정하지 않습니다.
- AI API 또는 CLI 도구를 활성화하면 문서의 일부 또는 전체가 외부 AI 서비스로 전송됩니다. 민감정보, 비공개 원고, 배포 권한이 불명확한 자료는 넣지 마세요.
- 생성된 번역·요약·위키 노트의 정확성·완전성은 보장되지 않습니다. 출판·제출·인용·대외 배포 전에는 반드시 원문과 결과물을 직접 대조해 검토하세요.

---

## 개발자용

```
core/                앱 핵심 코드
  pipeline_app.py    Streamlit UI (전 단계)
  services/          처리 로직 (convert/translate/chapters/wiki/i18n …)
  chapter_wiki.py    챕터 분할 + 요약 생성 (멀티 공급자 AI)
  llm_providers.py   AI 공급자 추상화 (Gemini/OpenAI/Anthropic/Claude CLI/Codex CLI)
  .streamlit/        config.toml (라이트 테마·개발자 툴바 비활성)
dev/                 빌드 스크립트 (build_mac_app.sh, bump_version.py …)
```

- macOS 빌드: `dev/build_mac_app.sh` → `dist/.mac-build.noindex/MyBookshelf.app` (Spotlight 검색 제외)
- macOS 배포본: `dev/build_mac_pkg.sh` → `MyBookshelf-vX.Y.Z.pkg` + 고정 이름 `MyBookshelf.pkg` (.app이 없거나 버전이 다르면 알아서 먼저 빌드)
- macOS 설치 자동화: `dev/installer/mac_postinstall.sh` (파이썬·venv) + `mac_setup_extras.sh` (AI CLI·옵시디언 순차 선택)
- Windows 배포본: `.github/workflows/build-windows.yml` → 태그 푸시 때 `Setup.exe` + 버전명 ZIP을 빌드해 릴리스에 첨부
- 무인 설치 스크립트: `install-mybookshelf.sh` (macOS) · `install-mybookshelf.ps1` (Windows)
- 개발 실행(레포 코드): 각 플랫폼의 `start` 스크립트 또는 `streamlit run core/pipeline_app.py`

### 용어집

요약 노트의 «한글(원어)» 표기를 보관함 안에서 통일합니다. 용어집은 보관함의 `_glossary.json` 에 저장되어, 보관함을 여러 기기에서 공유하면 정본도 함께 따라갑니다.

```
Windows   glossary.bat            현황  /  --apply 수정  /  --check 사전 대조
macOS     cd core && python3 -m services.glossary          (--apply 로 수정)
          cd core && python3 -m services.termcheck         (사전 대조)
```

- `--apply` 는 보관함을 통째로 백업한 뒤 고칩니다. 손대는 범위는 **«## 핵심 키워드» 구획의 대소문자·공백 차이뿐**입니다.
- 원어 자체가 다른 것(`책임` → responsibility / responsabilité / Verantwortung)은 원서 언어 차이인 경우가 많아 자동으로 손대지 않고 검토 목록으로만 보여 줍니다.
- `termcheck` 가 못 찾은 용어는 «미확인»이지 «오류»가 아닙니다 — 책이 만든 조어는 사전에 없는 것이 정상입니다.
