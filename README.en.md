# My Bookshelf

**A personal research tool that turns books, papers and manuscripts into readable summary notes and e-books.**
Feed it PDF/DOCX/HWP/HWPX/TXT and it translates, summarises, and exports to **EPUB · Word (.docx) · Hangul (.hwpx) · Obsidian Wiki**.

[![Download for Windows](https://img.shields.io/badge/Windows-Setup.exe-0078D4?style=for-the-badge&logo=data%3Aimage%2Fsvg%2Bxml%3Bbase64%2CPHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHZpZXdCb3g9IjAgMCAyNCAyNCI%2BPHBhdGggZmlsbD0iI2ZmZiIgZD0iTTMgM2g4LjJ2OC4ySDNWM3ptOS44IDBIMjF2OC4yaC04LjJWM3pNMyAxMi44aDguMlYyMUgzdi04LjJ6bTkuOCAwSDIxVjIxaC04LjJ2LTguMnoiLz48L3N2Zz4K)](https://github.com/Brightinyou/my-bookshelf/releases/latest/download/Setup.exe)
[![Download for macOS](https://img.shields.io/badge/macOS-.pkg-000000?style=for-the-badge&logo=apple&logoColor=white)](https://github.com/Brightinyou/my-bookshelf/releases/latest/download/MyBookshelf.pkg)

> 🇰🇷 한국어 설명서: [README.md](README.md) · 📘 Every tab in detail: [User manual](docs/MANUAL.en.md)

Runs on both Windows and macOS. The same core (`core/`) is shared and **only the installation differs** — in [2. Installation](#2-installation), read the part for your operating system.

---

## ⚡ Quick start

| | What to do |
|---|---|
| **1. Install** | Grab <img src="docs/img/windows.svg" width="15" align="top" alt="Windows"> `Setup.exe` or <img src="docs/img/apple.svg" width="14" align="top" alt="macOS"> `MyBookshelf.pkg` from the badges above and run it. You clear a **security warning once**, and the first launch takes **5–20 minutes** to prepare. → [details](#2-installation) |
| **2. Connect an AI** | In the app's `⚙️ Settings` tab, switch on an **AI subscription (CLI)** or paste an **API key**. A ChatGPT or Claude subscription works at no extra cost. → [details](#3-first-time-setup--connect-an-ai) |
| **3. Add documents** | Drop files onto the `📄 Text conversion` tab and press **[▶ Start]**. From there, **the popups walk you through** each following stage. |
| **4. Collect results** | In the `📖 Output` tab, switch on EPUB, Word, Hangul, or Obsidian and press **[▶ Start]**. |

---

## Contents

1. [What it does](#1-what-it-does)
2. [Installation](#2-installation) — [<img src="docs/img/windows.svg" width="15" align="top" alt="Windows"> Windows](#windows) · [<img src="docs/img/apple.svg" width="14" align="top" alt="macOS"> macOS](#macos)
3. [First-time setup — connect an AI](#3-first-time-setup--connect-an-ai)
4. [The workflow](#4-the-workflow)
5. [Start · Stop · Resume](#5-start--stop--resume)
6. [Language and translation](#6-language-and-translation)
7. [Data locations](#7-data-locations)
8. [Troubleshooting](#8-troubleshooting)
9. [Copyright and disclaimer](#9-copyright-and-disclaimer)

---

## 1. What it does

Feed in a book, paper, or manuscript as PDF/DOCX/HWP/HWPX/TXT, and it produces **readable summary Wiki notes** through these stages. (They can be saved into your Obsidian vault.)

```
PDF/DOCX/HWP/HWPX/TXT  →  Text conversion  →  Chapter split  →  Translation (when source differs from target)  →  Summaries  →  EPUB · Word (.docx) · Hangul (.hwpx) · Obsidian Wiki
```

- **PDF** works directly when it has a text layer. **Scanned PDFs, and PDFs with poor OCR, also work** — the «🔬 Text quality check» in the Text conversion tab flags them and **re-reads them with AI** (a few minutes to tens of minutes, depending on page count). **DOCX, HWP, HWPX and TXT** are processed as-is.
- Translation, summarization and Wiki generation use **AI**: enter an API key, or enable a Claude/ChatGPT subscription CLI.
- Notes include the **author, a key summary, per-chapter overview, key quotes and key keywords** (with explanations); dense source texts are made readable by glossing terms in the original language and paraphrasing in plain language.

---

## 2. Installation

<div align="center">

### ⬇️ Download

| | File |
|---|---|
| <img src="docs/img/windows.svg" width="15" align="top" alt="Windows"> **Windows** | [**Setup.exe** ⬇️](https://github.com/Brightinyou/my-bookshelf/releases/latest/download/Setup.exe) |
| <img src="docs/img/apple.svg" width="14" align="top" alt="macOS"> **macOS** | [**MyBookshelf.pkg** ⬇️](https://github.com/Brightinyou/my-bookshelf/releases/latest/download/MyBookshelf.pkg) |

The links above **download the latest build directly.** Older builds and other files live on the [release page](https://github.com/Brightinyou/my-bookshelf/releases/latest).

</div>

---

<a id="windows"></a>

<a id="windows"></a>

### <img src="docs/img/windows.svg" width="15" align="top" alt="Windows"> Windows

#### Step 1 — Download

- **[Download `Setup.exe` ⬇️](https://github.com/Brightinyou/my-bookshelf/releases/latest/download/Setup.exe)** — recommended. Just run it.
- If your browser blocks `.exe` downloads, grab `MyBookshelf-Setup-vX.Y.Z.zip` from the [release page](https://github.com/Brightinyou/my-bookshelf/releases/latest) under **Assets**. Unzipping gives the same `Setup.exe`.

#### Step 2 — Run it (one-time security prompt ⚠️)

Double-clicking `Setup.exe` brings up a blue *"Windows protected your PC"* screen. This is the notice Windows shows for software that **has not been signed with a commercial code-signing certificate** — common for programs shared by an individual.

1. Click **[More info]**.
2. Click the **[Run anyway]** button that appears.

#### Step 3 — Choose the interface language

Korean or English. You can change it any time later in the **Settings** tab.

#### Step 4 — Python (automatic)

If Python 3.14 is missing, the installer offers to download and install it for you — click **[Yes]**. If you already have 3.10 or newer, this step is skipped.

#### Step 5 — First-run preparation (automatic)

At the end of the install you'll see *"Preparing Python environment"*, and it will appear to hang for a few minutes — **that is normal.** It is fetching packages (**5–20 min** depending on your network).

- Install location: `C:\Users\<you>\AppData\Local\My Bookshelf`
- Progress log: `install.log` in that folder
- If it will not start: `launch-error.log` in the same folder

#### Step 6 — Launch

Use the **My Bookshelf** icon on your desktop or Start menu. Later launches open in seconds.

> **Updates**: use **Settings → Check for updates** in the app.
> If you were running a version older than v1.2.33, download this one manually just once — older builds point at the pre-merge repository.

---

<a id="macos"></a>

<a id="macos"></a>

### <img src="docs/img/apple.svg" width="14" align="top" alt="macOS"> macOS

#### Step 1 — Download

- **[Download `MyBookshelf.pkg` ⬇️](https://github.com/Brightinyou/my-bookshelf/releases/latest/download/MyBookshelf.pkg)** — this is the only one you need. Double-click it and the installer places the app in **Applications** for you.
- If you cannot use a Mac administrator password, grab `MyBookshelf-vX.Y.Z-mac.zip` from the [release page](https://github.com/Brightinyou/my-bookshelf/releases/latest) under **Assets**. Unzipping gives just the app file.

> The file is only a few hundred KB — **that is expected.** The Python environment is fetched on first launch.

#### Step 2 — Put it in Applications

- **`.pkg`**: double-click → [Continue] → [Install] → your Mac password. That's it; nothing else to do in this step.
- **zip**: unzip and move the resulting `MyBookshelf.app` into your **Applications** folder.

> ⚠️ **If you took the zip, move the app into Applications before running it.** Double-clicking it straight from your Downloads folder makes macOS run it from a locked temporary folder, and it **hangs with no visible response**. The `.pkg` does not have this problem.

#### Step 3 — First time only: pass the security warning ⚠️

Opening `MyBookshelf` for the first time shows an *"unidentified developer"* warning. This is the notice macOS shows for software that **has not gone through Apple signing/notarization** — common for programs shared by an individual. Allow it once as follows.

> Neither the `.pkg` nor the zip removes this step — it's about signing, not packaging. With the `.pkg` the warning appears when you first open the installer.

- **Try first**: **right-click (or control-click)** the `MyBookshelf` icon in Applications → **Open** → **Open** in the dialog.
- **If that doesn't open it** (recent macOS blocks the right-click bypass):
  1. Double-click once so the warning appears (you can dismiss it).
  2. Go to the **Apple menu (top-left of the screen) → System Settings → Privacy & Security**.
  3. Scroll down to *"'MyBookshelf' was blocked"* and click **[Open Anyway]**, then **Open** in the dialog.

> Once allowed, just **double-click** the icon from then on.

#### Step 4 — First-run setup (automatic)

The first launch **auto-installs** the Python environment and packages (**5–20 min** depending on your network; the window may show "preparing"). When done, the native app window appears. Later launches open in seconds.

> Requires Python 3.10+. If missing, install from [python.org](https://www.python.org/downloads/).
> If setup seems stuck, check the log: `~/Library/Application Support/MyBookshelf/app.log`

> <img src="docs/img/windows.svg" width="15" align="top" alt="Windows"> **On Windows?** → [Download `Setup.exe` ⬇️](https://github.com/Brightinyou/my-bookshelf/releases/latest/download/Setup.exe) and run it. macOS and Windows share a single repository.

---

## 3. First-time setup — connect an AI

In the app's `⚙️ Settings` tab, set up **one of these two**. **Pick the AI model once in Settings** and every stage uses it.

- **AI subscription (CLI)** — use your existing subscription, no API key (**recommended**). Takes priority over API keys.
- **AI API key** — paste a Gemini / OpenAI / Anthropic key. Billed per use.

---

### New here? — Installing a CLI

If you already pay for **ChatGPT Plus/Pro** or **Claude Pro/Max**, you can run this app on that subscription at **no extra cost**. You only need one of them.

#### Prerequisite — Node.js

Both CLIs need Node.js. You only install it once.

- [**Download Node.js**](https://nodejs.org/) — take the one marked **LTS**.
- Check it: open a terminal (**PowerShell** on Windows, **Terminal** on macOS) and run
  ```
  node --version
  ```
  Something like `v20.x` means you're set.

#### ① If you use ChatGPT — Codex CLI

```
npm install -g @openai/codex
codex
```

The first run of `codex` opens a browser and asks you to sign in to ChatGPT. Once is enough.

- Docs: [Codex CLI](https://developers.openai.com/codex/cli/)

#### ② If you use Claude — Claude Code CLI

```
npm install -g @anthropic-ai/claude-code
claude
```

The first run of `claude` opens a browser and asks you to sign in to Claude. Once is enough.

- Docs: [Claude Code setup](https://docs.claude.com/en/docs/claude-code/setup)

#### Last step — turn it on in the app

Once installed and signed in, **restart My Bookshelf** and flip the matching toggle in `⚙️ Settings`. The app finds it on its own.

> Not working? First check that typing `codex` or `claude` in a terminal actually runs.
> If the command doesn't run there, the app won't find it either.

---

### Prefer an API key?

Paste it into the `⚙️ Settings` tab.

- [Google AI Studio (Gemini)](https://aistudio.google.com/apikey)
- [OpenAI Platform](https://platform.openai.com/api-keys)
- [Anthropic Console](https://console.anthropic.com/settings/keys)

> If you have both a subscription (CLI) and an API key, **the subscription wins**.

---

Also open `⚙️ Settings → Obsidian vault` to check or change the folder where wiki notes are saved.

---

## 4. The workflow

Switch stages from the top menu. Every upload area accepts **the file picker or drag & drop**.

| Stage | What it does |
|---|---|
| **① 📄 Text conversion** | Extracts the body text from PDF/DOCX/HWP/HWPX/TXT and saves it as TXT. You can also pull a paper straight in by URL, DOI, or arXiv number. |
| **② ✂️ Chapter split** | Splits a book TXT into per-chapter files. If no split is needed, the whole document moves on as it is. |
| **③ 🌐 Translation** | Detects the source language automatically and renders it into your chosen **target language**. A paragraph-by-paragraph bilingual file is optional. |
| **④ 📝 Summaries** | Builds per-chapter notes — author, key summary, overview, key quotes, key keywords. Length is adjustable from 5–40 % of the source. |
| **⑤ 📖 Output** | Exports to **EPUB · Word (.docx) · Hangul (.hwpx) · Obsidian Wiki** — any combination at once. |

> **When a stage finishes, a popup asks about the next step.** **[Yes, proceed now]** advances only the book you just processed; use **[Choose on the screen]** to pick several at once from the queue.

> ⚠️ **EPUB carries the full text, not a summary.** Use it only on documents you already have the right to use, and only within your own personal use. ([9. Copyright and disclaimer](#9-copyright-and-disclaimer))

📘 Every button and option is documented in the **[User manual](docs/MANUAL.en.md)**.

---

## 5. Start · Stop · Resume

For the AI stages (Chapter split, Translation, Summaries, Wiki), pressing **[▶ Start]** switches to a processing view and **locks** other actions and tab navigation (so you can't accidentally leave a running job).

- The processing view shows progress and per-item results.
- **[■ Stop]** halts **after the current item finishes** and restores the full page.
- Remaining work stays in the queue — press **[▶ Start]** again to resume.
- Use **[🗑 Delete]** in the queue to drop wrongly added work.

---

## 6. Language and translation

`⚙️ Settings → Language` changes the interface language only.

- Choose the language of translations, summaries, and Wiki notes separately in `⚙️ Settings → 🎯 Target language`.
- The Translation stage works with the interface set to English too — the two settings are independent.
- Changing the target language does not rewrite existing translations or summaries; delete the relevant output and run the stage again.

---

## 7. Data locations

Default data folders (folder names are Korean or English depending on the install language):

```
0_Inbox/            uploads/downloads waiting (pre-processing)
1_PDF_Originals/    original PDFs
2_Converted_TXT/    converted TXT (done/ = archived sources after split)
3_Chapters/<book>/  workspace holding chapters, translations (_ko etc., by target language), bilingual output (_bilingual), summaries (_wiki.md), overview
5_전자책(EPUB)/      exported full-text EPUB e-books
5_위키문서(DOCX)/    exported DOCX documents (when "Create DOCX document" is on — this folder name stays in Korean regardless of the UI language)
5_위키문서(HWPX)/    exported HWPX documents (when "Create HWPX document" is on — this folder name stays in Korean regardless of the UI language)
Failed/, Logs/      failed files, logs
```

Wiki notes are saved to a separate Obsidian vault (chosen in `⚙️ Settings`). EPUB, Word (.docx), and Hangul (.hwpx) files are saved to the folders above. Settings live in `~/.config/mybookshelf/config.json` on macOS/Linux.

---

## 8. Troubleshooting

- **"No AI available"** — enter an API key or enable a CLI subscription (Claude/Codex) in `⚙️ Settings`.
- **Old screen after an update** — fully quit the app and reopen it (a server may still be running).
- **Scanned PDFs** — feed them in as they are. If the text comes out badly, use «🔬 Text quality check» in the Text conversion tab to re-read them with AI.
- (Windows) For install/launch errors, check `install.log` / `launch-error.log` in the install folder.

---

## 9. Copyright and disclaimer

**My Bookshelf** — © 2026 Brightinyou. Provided for personal, non-commercial research use.

**About the program**
- Copyright in this program belongs to Brightinyou. You may use and copy it for personal and academic purposes, but you may not resell or commercially distribute it without Brightinyou's written consent.
- The program is provided "as-is", with no warranty of fitness for a particular purpose or integrity. Brightinyou is not liable for any data loss or damage from its use.

**About your documents and generated output**
- This is a personal tool for converting, translating, and summarizing documents **you already have the right to use**. Using it does not grant you any right you did not already have, and it does not authorize you to distribute or share the resulting EPUB, translation, or summary with third parties. What is permitted varies by country and by how you obtained the document. In particular, there is no general "personal copying" exemption in every jurisdiction — do not assume that private use is automatically lawful where you live.
- You are responsible for confirming the source document's copyright, translation, summary and redistribution rights. This program does not automatically judge legal, publishing or academic-submission requirements.
- Enabling an AI API or CLI tool sends part or all of your document to an external AI service. Do not input sensitive data, unpublished manuscripts, or material whose distribution rights are unclear.
- Accuracy and completeness of generated translations, summaries and Wiki notes are not guaranteed. Always compare against the source before publishing, submitting, citing or distributing.

---

## For developers

```
core/                app core
  pipeline_app.py    Streamlit UI (all stages)
  services/          processing logic (convert/translate/chapters/wiki/i18n …)
  chapter_wiki.py    chapter split + summary generation (multi-provider AI)
  llm_providers.py   AI provider abstraction (Gemini/OpenAI/Anthropic/Claude CLI/Codex CLI)
  .streamlit/        config.toml (light theme, developer toolbar disabled)
dev/                 build scripts (build_mac_app.sh, bump_version.py …)
```

- macOS build: `dev/build_mac_app.sh` → `dist/.mac-build.noindex/MyBookshelf.app` (excluded from Spotlight)
- Run from source: each platform's `start` script, or `streamlit run core/pipeline_app.py`
