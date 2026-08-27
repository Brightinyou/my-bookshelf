# My Bookshelf

**A personal research tool that turns PDF/DOCX/HWP/HWPX/TXT documents into EPUB e-books, Word documents, Hangul (HWPX) documents, and Obsidian Wiki notes** — Text conversion → Chapter split → Translation → Summaries → **EPUB · Word (.docx) · Hangul (.hwpx) · Obsidian Wiki**, in one flow.

[![Download for Windows](https://img.shields.io/badge/%F0%9F%AA%9F%20Windows-Setup.exe-0078D4?style=for-the-badge)](https://github.com/Brightinyou/my-bookshelf/releases/latest)
[![Download for macOS](https://img.shields.io/badge/%F0%9F%8D%8E%20macOS-.dmg-000000?style=for-the-badge)](https://github.com/Brightinyou/my-bookshelf/releases/latest)

> 🇰🇷 한국어 설명서: [README.md](README.md)

Runs on both Windows and macOS. The same core (`core/`) is shared and **only the installation differs** — in [2. Installation](#2-installation), read the part for your operating system.

---

## 1. What it does

Feed a book or paper as PDF/DOCX/HWP/HWPX/TXT, and it produces **readable summary Wiki notes** saved into your Obsidian vault through these stages:

```
PDF/DOCX/HWP/HWPX/TXT  →  Text conversion  →  Chapter split  →  Translation (when source differs from target)  →  Summaries  →  EPUB · Word (.docx) · Hangul (.hwpx) · Obsidian Wiki
```

- **PDF** must be text-based (has a text layer), not a raw scan (scanned PDFs need OCR first). **DOCX, HWP, HWPX and TXT** are processed as-is.
- Translation, summarization and Wiki generation use **AI**: enter an API key, or enable a Claude/ChatGPT subscription CLI.
- Notes include the **author, a key summary, per-chapter overview, key quotes and key keywords** (with explanations); dense source texts are made readable by glossing terms in the original language and paraphrasing in plain language.

---

## 2. Installation

<div align="center">

### ⬇️ Download

| | File |
|---|---|
| 🪟 **Windows** | [**Setup.exe**](https://github.com/Brightinyou/my-bookshelf/releases/latest) |
| 🍎 **macOS** | [**MyBookshelf.dmg**](https://github.com/Brightinyou/my-bookshelf/releases/latest) |

Both are on the [**latest release**](https://github.com/Brightinyou/my-bookshelf/releases/latest) page, under **Assets**.

</div>

---

### 🪟 Windows

#### Step 1 — Download

From the [**latest release**](https://github.com/Brightinyou/my-bookshelf/releases/latest) page, under **Assets**:

- **`Setup.exe`** — recommended. Just run it.
- `MyBookshelf-Setup-vX.Y.Z.zip` — use this if your browser blocks `.exe` downloads. Unzipping gives the same `Setup.exe`.

#### Step 2 — Run it (one-time security prompt ⚠️)

Double-clicking `Setup.exe` brings up a blue *"Windows protected your PC"* screen. **This is not a virus** — the app simply is not code-signed (a certificate costs a few hundred dollars a year).

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

### 🍎 macOS

#### Step 1 — Download

On the [**latest release**](https://github.com/Brightinyou/my-bookshelf/releases/latest) page, under **Assets**, grab one of:

- **`MyBookshelf-vX.Y.Z.dmg`** — recommended. Opens the familiar "drag to install" window.
- `MyBookshelf-vX.Y.Z-mac.zip` — unzipping gives just the app file. (Having no separate installer is normal — the app installs itself.)

> The file is only a few hundred KB — **that is expected.** The Python environment is fetched on first launch.

#### Step 2 — Put it in Applications

- **DMG**: double-click the `.dmg`, then **drag `MyBookshelf.app` onto the `Applications` folder** in the window.
- **zip**: unzip and move the resulting `MyBookshelf.app` into your **Applications** folder.

#### Step 3 — First time only: pass the security warning ⚠️

This app is a **personal build without Apple signing/notarization**, so the first launch shows an *"unidentified developer"* warning. **It is not malware** — it just skips the (US$99/yr) signing cost. Allow it once as follows. (The DMG does **not** remove this step — it's a signing matter, independent of packaging.)

- **Try first**: **right-click (or control-click)** the `MyBookshelf` icon in Applications → **Open** → **Open** in the dialog.
- **If that doesn't open it** (recent macOS blocks the right-click bypass):
  1. Double-click once so the warning appears (you can dismiss it).
  2. Go to ** menu → System Settings → Privacy & Security**.
  3. Scroll down to *"'MyBookshelf' was blocked"* and click **[Open Anyway]**, then **Open** in the dialog.

> Once allowed, just **double-click** the icon from then on.

#### Step 4 — First-run setup (automatic)

The first launch **auto-installs** the Python environment and packages (**5–20 min** depending on your network; the window may show "preparing"). When done, the native app window appears. Later launches open in seconds.

> Requires Python 3.10+. If missing, install from [python.org](https://www.python.org/downloads/).
> If setup seems stuck, check the log: `~/Library/Application Support/MyBookshelf/app.log`

> 🪟 **On Windows?** → Grab `Setup.exe` from the same [**latest release**](https://github.com/Brightinyou/my-bookshelf/releases/latest) page and run it. macOS and Windows share a single repository.

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

## 4. The workflow in detail

Switch stages from the top menu. Every upload area accepts **file picker or drag & drop**. The "open folder" buttons are tucked into a small expander so the actual work area stands out.

> **When a stage finishes, a popup asks about the next step.** For example, after text conversion it asks *"Split into chapters next?"* — press **[Yes, proceed now]** and **only the book you just processed** advances and runs automatically (other queued books are left untouched). To process several at once or pick manually, use **[Choose on the screen]** to open the regular queue view. The popup closes while processing so the progress bar and Stop button stay visible.

### ① 📄 Text conversion
- Uploaded PDF/DOCX/HWP/HWPX/TXT files stack up in the **processing queue**.
- Select items and press **[Convert to text]** — extracts the text and saves TXT. The original document is kept.
- **[Delete]** removes mistakenly added files.
- **Fetch from a paper source**: pull a paper by URL, DOI or arXiv number (for login/paywalled pages, download the PDF yourself and upload it).

### ② ✂️ Chapter split
- Splits a book TXT into **per-chapter files** under a per-book folder.
- **[Split]** — split into chapters. **[Move to next step]** — if no split is needed, send the whole document onward (when source differs from the target language → Translation; otherwise → Summaries).
- Short documents are handled separately under "Short documents".

### ③ 🌐 Translation (multiple languages → chosen target)
- Detects the source language automatically, including English, German, Dutch, French, Spanish, Italian, Portuguese, Latin, Japanese, Chinese, Russian, Greek, Hebrew, and Arabic.
- Choose the output language in `⚙️ Settings → 🎯 Target language`: Korean, English, Japanese, Chinese, German, French, Spanish, Italian, Portuguese, Dutch, or Russian. Korean is the default.
- The target language applies consistently to translations, chapter summaries, and Wiki notes. It is separate from the interface language.
- Translation text remains named `_ko.txt` for compatibility. Enable the **Bilingual** toggle to also create `_bilingual.txt`, which pairs source and translation by paragraph.
- Existing translations and summaries remain in their previous language. Delete them and run the stage again after changing the target.

### ④ 📝 Summaries
- Creates per-chapter summary notes (`_wiki.md`) — author, key summary, overview, key quotes, key keywords (with explanations).
- Summaries are written as **direct statements of the content**, not "the author says …".
- **Length control**: in the Settings tab or the collapsible **"Adjust summary length"** here, set the summary body to **5–40 % of the source** (15 % default). Higher values make longer notes and increase **output tokens / API cost** (input tokens for the source stay the same). Short chapters keep a minimum length.
- Select queued items and press **[▶ Start]**.

### ⑤ 📖 Output (Create EPUB · Create DOCX · Create HWPX · Wiki)
- This stage has **four independent toggles**. Enable any combination to generate every selected format.
  - **EPUB e-book** *(full text, not a summary)*: packages the complete source/translated chapters into an `.epub` in `5_전자책(EPUB)`. It is instant once optional Korean line-break repair has finished. ⚠️ This reproduces the entire copyrighted work. Use it only on documents **you already have the right to use**, and only within your own personal use. What copying, translation, or format conversion is permitted varies by country and by how you obtained the document — this feature grants you no right to distribute or share the result.
  - **Line-break repair** *(optional, Korean source books)*: restores printed line breaks into readable paragraphs before EPUB export. AI decides whitespace only; it does not alter the body text.
  - **Word document (DOCX)** *(summary-based)*: saves editable summaries in `5_위키문서(DOCX)`.
  - **Hangul document (HWPX)** *(summary-based)*: saves editable summaries in `5_위키문서(HWPX)`.
  - **Obsidian Wiki** *(summary-based)*: saves a hub note and per-chapter notes in the selected vault.
  - Select at least one output.
- The note/document frontmatter is auto-filled with **author, publication date, and publisher (`Place: Publisher`)**, extracted from the source's title/colophon page (left blank if not confidently found).
- If a book is already reflected, the popup asks **"Replace?"** to update it in place.
- Use **[Select all]/[Clear]** in the queue, then **[▶ Start]**.

---

## 5. Start · Stop · Resume

For the AI stages (Chapter split, Translation, Summaries, Wiki), pressing **[▶ Start]** switches to a processing view and **locks** other actions and tab navigation (so you can't accidentally leave a running job).

- The processing view shows progress and per-item results.
- **[■ Stop]** halts **after the current item finishes** and restores the full page.
- Remaining work stays in the queue — press **[▶ Start]** again to resume.
- Use **[🗑 Delete]** in the queue to drop wrongly added work.

---

## 6. Language and the translation stage

`⚙️ Settings → Language` changes the interface language only.

- Choose the language of translations, summaries, and Wiki notes separately in `⚙️ Settings → 🎯 Target language`.
- The Translation stage is currently hidden while the interface is set to English. Set the interface to Korean to run translation work.
- Changing the target language does not rewrite existing translations or summaries; delete the relevant output and run the stage again.

---

## 7. Data locations

Default data folders (folder names are Korean or English depending on the install language):

```
0_Inbox/            uploads/downloads waiting (pre-processing)
1_PDF_Originals/    original PDFs
2_Converted_TXT/    converted TXT (done/ = archived sources after split)
3_Chapters/<book>/  workspace holding chapters, translations (_ko), bilingual output (_bilingual), summaries (_wiki.md), overview
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
- **Scanned PDFs** — OCR scans into a text PDF/TXT first, then feed them in.
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
