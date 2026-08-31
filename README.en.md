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
| **1. Install** | Grab <img src="docs/img/windows.svg" width="15" align="top" alt="Windows"> `Setup.exe` or <img src="docs/img/apple.svg" width="14" align="top" alt="macOS"> `MyBookshelf.pkg` from the badges above and run it. You clear a **security warning once**, and the installer spends a few minutes preparing the Python environment. → [details](#2-installation) |
| **2. Connect an AI** | After a macOS PKG install, Terminal asks you to choose **Claude, Codex (ChatGPT), both, or later**. If you skip it, enable a CLI or enter an API key in `⚙️ Settings`. → [details](#3-first-time-setup--connect-an-ai) |
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

⚡ Comfortable with a terminal or PowerShell? There is a **one-line install** too — Python, the app, and the AI connection in one go. [<img src="docs/img/windows.svg" width="15" align="top" alt="Windows"> Windows](#oneline-win) · [<img src="docs/img/apple.svg" width="14" align="top" alt="macOS"> macOS](#oneline-mac)

</div>

---

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

#### Step 6 — Connect an AI

After installation, a **My Bookshelf - Additional setup** PowerShell window opens. Choose **Claude, Codex (ChatGPT), both, or later**, then choose whether to install Obsidian. Setup installs the selected tools and immediately opens browser sign-in. Selecting **both** signs in to Claude first and then Codex, and enables the prepared CLIs and Obsidian in the app settings.

To use an API instead, choose **later** and enter a Gemini, OpenAI, or Anthropic API key in `⚙️ Settings`.

#### Step 7 — Launch

Use the **My Bookshelf** icon on your desktop or Start menu. Later launches open in seconds.

> **Updates**: use **Settings → Check for updates** in the app.
> If you were running a version older than v1.2.33, download this one manually just once — older builds point at the pre-merge repository.

<a id="oneline-win"></a>

> [!TIP]
> ### <img src="docs/img/windows.svg" width="15" align="top" alt="Windows"> Windows — ⚡ One-line install
>
> *Skips steps 1–7.*
>
> If you're comfortable with PowerShell, **one script does Python, the app, an AI CLI, and default settings.**
>
> ```powershell
> irm https://github.com/Brightinyou/my-bookshelf/releases/latest/download/install-mybookshelf.ps1 -OutFile install-mybookshelf.ps1
> powershell -ExecutionPolicy Bypass -File .\install-mybookshelf.ps1 -AI claude -Launch
> ```
>
> Options: `-AI codex` (ChatGPT, default) · `-AI claude` · `-AI both` · `-AI none` · `-NoLogin` · `-Obsidian` · `-TargetLang en`. Installing Node.js may pop up a **UAC admin-confirmation window** once, and on a very old Windows 10 without winget the Node.js (→ Codex CLI) install may not happen automatically — it will show up in the on-screen "do this manually" list instead.
>
> The selected subscription CLI opens browser sign-in immediately — `-AI both` attempts both Claude and Codex sign-in, so you need an actual Claude Pro/Max and ChatGPT Plus/Pro subscription for that. If you don't, pick a single `-AI codex`/`-AI claude`, or use `-AI none` and enter an API key in the app instead. The install itself takes 5–20 minutes, so leave the window open.

---

<a id="macos"></a>

### <img src="docs/img/apple.svg" width="14" align="top" alt="macOS"> macOS

#### Step 1 — Download

- **[Download `MyBookshelf.pkg` ⬇️](https://github.com/Brightinyou/my-bookshelf/releases/latest/download/MyBookshelf.pkg)** — this is the only one you need. Double-click it and the installer places the app in **Applications** for you.
- If you cannot use a Mac administrator password, grab `MyBookshelf-vX.Y.Z-mac.zip` from the [release page](https://github.com/Brightinyou/my-bookshelf/releases/latest) under **Assets**. Unzipping gives just the app file.

> The file is only a few hundred KB — **that is expected.** The `.pkg` fetches and prepares the Python environment during installation.

#### Step 2 — Pass the one-time security warning ⚠️

Because this independently distributed app has not gone through Apple signing and notarization, macOS may show an *"unidentified developer"* warning.

- **`.pkg`**: in Downloads, **control-click (or right-click) `MyBookshelf.pkg` → Open → Open**.
- **zip**: first move `MyBookshelf.app` into **Applications**, then **control-click its icon → Open → Open**. Running it directly from Downloads can place it in a temporary translocation path and make it appear to hang.
- If it is still blocked, double-click once to trigger the warning, then use **Apple menu → System Settings → Privacy & Security → Open Anyway**.

#### Step 3 — Install the app and Python environment

In the `.pkg` installer, click **[Continue] → [Install]** and enter your Mac password. It automatically:

1. Finds Python 3.10 or newer, preferring an installation that matches the Mac's architecture.
2. If none is available, downloads Python 3.14.6 from python.org, verifies its SHA256, and installs it.
3. Creates an app-specific virtual environment and installs the required Python packages.

This can take a few minutes depending on the network; leave the installer open.

> **The zip is different.** Python 3.10 or newer must already be installed. If it is missing, the first launch directs you to python.org; after installing Python, reopen the app to prepare its virtual environment and packages.

#### Step 4 — Choose an AI in Terminal

After Python preparation, a **My Bookshelf — Additional setup** Terminal window opens.

| Choice | What it installs | Approx. additional space |
|---|---|---:|
| **1. Claude** | Claude Code CLI · Claude Pro/Max subscription | 293MB |
| **2. Codex** | Codex CLI · ChatGPT Plus/Pro subscription | 363MB, including Node.js |
| **3. Both** | Claude and Codex · Codex (ChatGPT) is the default working AI | 656MB |
| **4. Later** | No CLI; enter an API key in the app later | 0MB |

Enter a number and press Return. Pressing Enter without a number selects the default, **4. Later**. An existing CLI is not downloaded again and is shown as 0MB additional space.

> If Homebrew is already installed, it is used for Node.js. The setup does not install Homebrew; without it, the official Node.js LTS build is installed directly in the user account.

#### Step 5 — Choose whether to install Obsidian

After the AI choice, setup asks whether to install Obsidian (about 515MB). The default is **No**.

- **Yes**: uses Homebrew if available; otherwise downloads the latest official macOS DMG and installs it under `~/Applications`.
- **No**: sets the default outputs to **EPUB + Word**. Installing Obsidian sets them to **EPUB + Obsidian Wiki**.
- If Obsidian already exists in `/Applications` or `~/Applications`, the download is skipped.

You can change output formats and the Obsidian vault later in `⚙️ Settings`.

#### Step 6 — Sign in to the CLI and launch the app

When you select a CLI, setup opens its browser sign-in immediately. Selecting **Both** signs in to Claude first, then Codex. It also registers the command paths, so `claude` and `codex` work from newly opened Terminal windows.

You can cancel either sign-in and later enable it in `⚙️ Settings` or use an API key instead. The final Enter ends additional setup.

Then launch **My Bookshelf** from Launchpad or Applications. The `.pkg` build opens immediately because its Python environment is already prepared.

> Installer log: `~/Library/Application Support/MyBookshelf/install.log`<br>
> App log: `~/Library/Application Support/MyBookshelf/app.log`

<a id="oneline-mac"></a>

> [!TIP]
> ### <img src="docs/img/apple.svg" width="14" align="top" alt="macOS"> macOS — ⚡ One-line install
>
> *Skips steps 1–6.*
>
> If you're comfortable with a terminal, one script handles the download plus **Python, the app, the selected AI CLIs, and default settings**. The `.pkg` also installs Python and your selected AI CLIs, plus Obsidian when requested; this route simply supplies the choices up front for an unattended install.
>
> ```bash
> curl -fsSL https://github.com/Brightinyou/my-bookshelf/releases/latest/download/install-mybookshelf.sh -o install-mybookshelf.sh
> bash install-mybookshelf.sh --ai codex --launch
> ```
>
> Options: `--ai codex` (ChatGPT, default) · `--ai claude` · `--ai both` · `--ai none`. Repeating `--ai claude --ai codex` also installs both. See `bash install-mybookshelf.sh --help` for `--obsidian`, `--target-lang en`, and the full list.
>
> **This route never hits the security warning** — it installs with the `installer` command.
> The selected CLI's browser sign-in opens during installation. Only API-key entry remains manual in the app settings.

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
- (macOS) **"Check for updates" does nothing** — if you installed with a `.pkg` older than v1.2.74, the app is owned by root and cannot replace itself. Run this once and updates work from then on:
  ```
  sudo chown -R "$(whoami):staff" /Applications/MyBookshelf.app
  ```
  Reinstalling from the latest `.pkg` does the same thing automatically. See `~/Library/Application Support/MyBookshelf/update.log`.
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
- macOS distributable: `dev/build_mac_pkg.sh` → `MyBookshelf-vX.Y.Z.pkg` plus the fixed name `MyBookshelf.pkg`
- macOS install automation: `dev/installer/mac_postinstall.sh` (Python and venv) + `mac_setup_extras.sh` (sequential AI CLI and Obsidian choices)
- Windows distributable: `.github/workflows/build-windows.yml` builds `Setup.exe` and a versioned ZIP on tag pushes and attaches both to the release
- Unattended installers: `install-mybookshelf.sh` (macOS) · `install-mybookshelf.ps1` (Windows)
- Run from source: each platform's `start` script, or `streamlit run core/pipeline_app.py`

### Glossary

Unifies how each term's original-language form is written across your vault's notes. The glossary lives in the vault as `_glossary.json`, so sharing the vault across machines shares the canonical spellings too.

```
Windows   glossary.bat            report  /  --apply to fix  /  --check against authorities
macOS     cd core && python3 -m services.glossary          (--apply to fix)
          cd core && python3 -m services.termcheck         (authority check)
```

- `--apply` backs up the whole vault first. It only touches **case and spacing differences inside the `## 핵심 키워드` block**.
- When the original term itself differs (`책임` → responsibility / responsabilité / Verantwortung) that is usually a source-language difference, so it is listed for review rather than changed.
- Terms `termcheck` cannot find are reported as **unverified, not wrong** — a term a book coined will not be in any dictionary.
