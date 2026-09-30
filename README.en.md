# My Bookshelf

**Put in a book, paper or manuscript — it translates and summarizes it into easy-to-read notes and e-books.**

Feed it PDF, Word (.docx), Hangul (.hwp/.hwpx) or text (.txt) files → get **summary notes (Obsidian wiki) · Word documents · Hangul documents · e-books (EPUB)**.

[![Download for Windows](https://img.shields.io/badge/Windows-Setup.exe-0078D4?style=for-the-badge&logo=data%3Aimage%2Fsvg%2Bxml%3Bbase64%2CPHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHZpZXdCb3g9IjAgMCAyNCAyNCI%2BPHBhdGggZmlsbD0iI2ZmZiIgZD0iTTMgM2g4LjJ2OC4ySDNWM3ptOS44IDBIMjF2OC4yaC04LjJWM3pNMyAxMi44aDguMlYyMUgzdi04LjJ6bTkuOCAwSDIxVjIxaC04LjJ2LTguMnoiLz48L3N2Zz4K)](https://github.com/Brightinyou/my-bookshelf/releases/latest/download/Setup.exe)
[![Download for macOS](https://img.shields.io/badge/macOS-.pkg-000000?style=for-the-badge&logo=apple&logoColor=white)](https://github.com/Brightinyou/my-bookshelf/releases/latest/download/MyBookshelf.pkg)

> 🇰🇷 한국어: [README.md](README.md) · 📘 Every screen in detail: [User manual](docs/MANUAL.en.md)

---

## How it works (at a glance)

```
① Install  →  ② Connect an AI  →  ③ Add files  →  ④ Get the results
```

1. Use the buttons above to **download and install**. (See [Install](#install))
2. The first time you open the app, follow the **«AI connection»** guide. (See [Connect an AI](#connect-an-ai))
3. On the **Text** screen, drag your files in and press **[▶ Start]**.
4. After each step the app **asks whether to go on to the next one.** Keep pressing **[Yes, proceed now]** and your result files are made at the end.

---

## Contents

1. [Install](#install) — [Windows](#windows) · [macOS](#macos)
2. [Connect an AI](#connect-an-ai)
3. [Use the app](#use-the-app)
4. [Where are my results?](#where-are-my-results)
5. [FAQ and troubleshooting](#faq-and-troubleshooting)
6. [Please note (copyright and privacy)](#please-note-copyright-and-privacy)
7. [Advanced and developers](#advanced-and-developers)

---

## Install

<a id="windows"></a>

### <img src="docs/img/windows.svg" width="15" align="top" alt="Windows"> Windows

**1. Download**
[**Download Setup.exe ⬇️**](https://github.com/Brightinyou/my-bookshelf/releases/latest/download/Setup.exe) (about 100 MB)

> If your browser blocks the download, open the [release page](https://github.com/Brightinyou/my-bookshelf/releases/latest), get `MyBookshelf-Setup-v….zip` under **Assets**, and unzip it. It contains the same `Setup.exe`.

**2. Run it — a security warning appears the first time ⚠️**
When you double-click `Setup.exe`, a blue *"Windows protected your PC"* box may appear. It shows up because this is a program made by an individual; there is nothing to worry about.

- Click **[More info]** → **[Run anyway]**.

**3. Install**
- Choose a language (한국어/English) and keep clicking **[Next]**. It usually takes **1–2 minutes**.
- You do not need to install Python or anything else — everything is inside the installer.
- If your PC lacks **Microsoft WebView2**, which draws the app window, the installer downloads and installs it (about a minute, internet needed). A progress bar sliding back and forth during this step is normal.

**4. Open the app**
Click **[Finish]** on the last screen and the app opens. Next time, click **«My Bookshelf»** on the desktop or in the Start menu.

Now go to [Connect an AI](#connect-an-ai).

---

<a id="macos"></a>

### <img src="docs/img/apple.svg" width="14" align="top" alt="macOS"> macOS

**1. Download**
[**Download MyBookshelf.pkg ⬇️**](https://github.com/Brightinyou/my-bookshelf/releases/latest/download/MyBookshelf.pkg)

> The file is only a few hundred KB — that is normal. What it needs is downloaded during installation.

**2. Run it — a security warning appears the first time ⚠️**
- In your Downloads folder, **control-click (or right-click) `MyBookshelf.pkg` → Open → Open**.
- If it is still blocked: **Apple menu → System Settings → Privacy & Security** → **[Open Anyway]**.

**3. Install**
**[Continue] → [Install] → enter your Mac password**. If Python is missing it is downloaded from python.org and installed automatically, so this can take **a few minutes** depending on your connection. Do not close the installer.

**4. Open the app**
The app opens by itself when installation finishes. Next time, open **My Bookshelf** from **Launchpad** or the **Applications** folder.

Now go to [Connect an AI](#connect-an-ai).

---

## Connect an AI

Translation and summaries are done by an AI. The first time you open the app you see the **«AI connection»** guide. Pick **whichever suits you**:

| | Subscription | API key |
|---|---|---|
| **For you if** | you **already subscribe** to ChatGPT Plus/Pro or Claude Pro/Max | you have no subscription and want to **pay only for what you use** |
| **Cost** | no extra charge (included in your plan) | billed by usage |
| **Setup** | the app guides the tool install and sign-in | get a key and paste it |

### Connect with a subscription (recommended)

1. In the «AI connection» guide, keep **Subscription (Claude·ChatGPT)** selected and click **[Open setup window]**.
2. In the new window, pick a number: **1** Claude · **2** Codex (ChatGPT) · **3** Both · **4** Later
3. The needed tools are installed, then a **browser sign-in page** opens. Sign in with the account you already use.
4. Back in the app, click **[Check again]** and you are connected.

> **If the setup window does not open**, expand **«Install Claude yourself (copy commands)»** below the guide. Copy each command with the copy button and paste them one by one into PowerShell (Terminal on a Mac).

> **What about Obsidian?** The setup window asks whether to install Obsidian too. Obsidian is a **free note-taking app** that shows your summary notes linked to one another. You do not need it — you can get your results as Word documents instead, and you can turn Obsidian on in Settings any time.

### Connect with an API key

1. In the «AI connection» guide, choose **API keys**.
2. Pick an AI service (Gemini · OpenAI · Anthropic) and the app shows **where to get a key**. Get one there.
3. Paste the key and click **[Save]**. The key is stored only on this computer.

### To change it later

Go to **⚙️ Settings → AI settings → «AI connection»** and pick the AI and model together in one box. **It applies as soon as you pick it.**

> 💡 **Subscribed to both?** Turn on «When one subscription AI hits its usage limit, continue with the other». If one reaches its limit, the other carries on. The top of the screen then shows `first › second`.

---

## Use the app

Work through the menu at the top from left to right. Add files by **dragging them in or with the file picker**.

| Step | Menu | What it does |
|:---:|---|---|
| 1 | 📄 **Text** | Pulls the text out of your files. Scanned PDFs work too. |
| 2 | ✂️ **Chapter split** | Splits a book into chapters. |
| 3 | 🌐 **Translation** | Translates foreign-language documents into your target language. Documents already in that language are skipped. |
| 4 | 📝 **Summaries** | Writes a summary note for each chapter. |
| 5 | 📖 **Export** | Exports to Word · Hangul · e-book (EPUB) · Obsidian wiki — whichever you turn on. |

- Each step starts with **[▶ Start]**. **[■ Stop]** finishes the item in progress and then stops.
- Press **[▶ Start]** again to **pick up where you left off** — it does not start over.
- When a step finishes, the app asks about the next one. Just click **[Yes, proceed now]**.

📘 Every button is explained in the [user manual](docs/MANUAL.en.md).

---

## Where are my results?

In the **My Bookshelf** folder inside your **Documents** folder.

| Folder | Contents |
|---|---|
| `3_Chapters/<book>/` | chapters, translations and summaries |
| `5_위키문서(DOCX)/` | Word documents |
| `5_위키문서(HWPX)/` | Hangul documents |
| `5_전자책(EPUB)/` | e-books |

> The Word, Hangul and EPUB folders keep their Korean names even when the app is in English.

Obsidian wiki notes go to the **Obsidian vault** folder chosen in Settings. The **[Open folder]** buttons on the Export screen open these folders directly.

---

## FAQ and troubleshooting

**Q. It says «No AI available».**
Go through [Connect an AI](#connect-an-ai) again. If you use a subscription, try **[Check again]**.

**Q. The app window is completely blank. (Windows)**
Microsoft WebView2, which draws the app window, is missing. Recent versions (v1.5.0 and later) install it during setup, and if it is still missing the app **opens in your default browser** instead. Install [WebView2](https://go.microsoft.com/fwlink/p/?LinkId=2124703) from the address in the notice and the app window works from the next start.

**Q. How do I update?**
Click **⚙️ Settings → Check for updates**. (On a very old version, before v1.2.33, download the new installer with the button above instead.)

**Q. I updated but still see the old screen.**
Close the app completely and open it again. If nothing changes, click **«Stop My Bookshelf»** in the Start menu and open the app again.

**Q. Do scanned PDFs work?**
Yes. If the text comes out garbled, use **«🔬 Text quality check»** on the Text screen to have the AI re-read it (a few minutes to tens of minutes, depending on the page count).

**Q. (Mac) «Check for updates» does not update the app.**
This happens if you installed with a `.pkg` older than v1.2.74. Run this once in Terminal, or reinstall with the latest `.pkg`:
```
sudo chown -R "$(whoami):staff" /Applications/MyBookshelf.app
```

**Q. Where can I look when something goes wrong?**
- Windows: `install.log` (install) and `launch-error.log` (startup) in `C:\Users\<you>\AppData\Local\My Bookshelf`
- macOS: `install.log` and `app.log` in `~/Library/Application Support/MyBookshelf/`

---

## Please note (copyright and privacy)

- This program turns documents **you have the right to use** into easier reading **for your own use**. It gives you **no right to share or distribute** the translations, summaries or e-books it makes.
- **An EPUB contains the full original text**, not a summary. Keep it for personal use.
- When you use an AI, the document's content is **sent to an external AI service**. Do not put in sensitive personal data or unpublished manuscripts.
- AI translations and summaries **can be wrong.** Check them against the original before quoting or submitting them.

<details>
<summary><b>Full copyright and disclaimer</b></summary>

**My Bookshelf** — © 2026 Brightinyou. Provided for personal, non-commercial research use.

**About the program**
- Copyright in this program belongs to Brightinyou. You may use and copy it for personal and academic purposes, but you may not resell or commercially distribute it without Brightinyou's written consent.
- The program is provided "as-is", with no warranty of fitness for a particular purpose or integrity. Brightinyou is not liable for any data loss or damage from its use.

**About your documents and generated output**
- This is a personal tool for converting, translating, and summarizing documents **you already have the right to use**. Using it does not grant you any right you did not already have, and it does not authorize you to distribute or share the resulting EPUB, translation, or summary with third parties. What is permitted varies by country and by how you obtained the document. In particular, there is no general "personal copying" exemption in every jurisdiction — do not assume that private use is automatically lawful where you live.
- You are responsible for confirming the source document's copyright, translation, summary and redistribution rights. This program does not automatically judge legal, publishing or academic-submission requirements.
- Enabling an AI API or CLI tool sends part or all of your document to an external AI service. Do not input sensitive data, unpublished manuscripts, or material whose distribution rights are unclear.
- Accuracy and completeness of generated translations, summaries and Wiki notes are not guaranteed. Always compare against the source before publishing, submitting, citing or distributing.

</details>

---

## Advanced and developers

You do not need anything below to use the app.

<details>
<summary><b>⚡ Install with one command (for PowerShell / Terminal users)</b></summary>

**Windows (PowerShell)**
```powershell
irm https://github.com/Brightinyou/my-bookshelf/releases/latest/download/install-mybookshelf.ps1 -OutFile install-mybookshelf.ps1
powershell -ExecutionPolicy Bypass -File .\install-mybookshelf.ps1 -AI codex -Launch
```
Options: `-AI codex` (default) · `-AI claude` · `-AI both` · `-AI none` · `-NoLogin` · `-Obsidian` · `-TargetLang en`.

**macOS (Terminal)**
```bash
curl -fsSL https://github.com/Brightinyou/my-bookshelf/releases/latest/download/install-mybookshelf.sh -o install-mybookshelf.sh
bash install-mybookshelf.sh --ai codex --launch
```
`--ai codex` (default) · `--ai claude` · `--ai both` · `--ai none` · `--obsidian` · `--target-lang en` — see `bash install-mybookshelf.sh --help`. This way skips the macOS security warning.

</details>

<details>
<summary><b>🌐 Screen language and translation language</b></summary>

- The language setting in `⚙️ Settings` changes only the **text on screen** (한국어/English).
- The language translations are written in is chosen separately in `⚙️ Settings → 🎯 Target language`. It applies to translations, summaries and wiki notes.
- Existing translations and summaries are not converted when you change the target language. Delete the result files and run again.

</details>

<details>
<summary><b>📂 Full data folder layout</b></summary>

Folder names are Korean or English depending on the install language (English shown).

```
0_Inbox/                 uploads and downloads waiting to be processed
1_PDF_Originals/         original PDFs
2_Converted_TXT/         converted TXT (Done/ = originals already split)
3_Chapters/<book>/        chapters · translations (_ko etc.) · bilingual (_bilingual) · summaries (_wiki.md) · overview
5_전자책(EPUB)/          EPUB (full text)
5_위키문서(DOCX)/        Word documents
5_위키문서(HWPX)/        Hangul documents
Failed/, Logs/           failed files and logs
```

Settings are stored in `~/.config/mybookshelf/`.

</details>

<details>
<summary><b>📖 Glossary — unify «Korean (original)» terms in summary notes</b></summary>

The glossary is stored as `_glossary.json` in the vault, so it follows the vault if you share it across devices.

```
Windows   glossary.bat            status  /  --apply to fix  /  --check dictionary lookup
macOS     cd core && python3 -m services.glossary          (--apply to fix)
          cd core && python3 -m services.termcheck         (dictionary lookup)
```

- `--apply` backs up the whole vault first. It only touches **case and spacing differences in the «## 핵심 키워드» (key terms) section**.
- Terms whose original differs (`책임` → responsibility / responsabilité / Verantwortung) are never changed automatically; they are only listed for review.
- A term `termcheck` cannot find is «unconfirmed», not «wrong».

</details>

<details>
<summary><b>🛠 For developers — code layout and builds</b></summary>

```
core/                app core
  pipeline_app.py    Streamlit UI (all stages)
  desktop.py         app window (PyWebView) launcher
  services/          processing logic (convert/translate/chapters/wiki/i18n …)
  chapter_wiki.py    chapter split + summary generation
  llm_providers.py   AI providers (Gemini/OpenAI/Anthropic/Claude CLI/Codex CLI) · subscription CLI takeover
dev/                 build scripts (build_mac_app.sh, bump_version.py …)
dev/installer/       Windows installer (MyBookshelf.iss) · runtime / WebView2 fetch scripts
```

- Windows build: `.github/workflows/build-windows.yml` — fetches the Python runtime (`fetch-runtime.ps1`) and the WebView2 bootstrapper (`fetch-webview2.ps1`) and packs them into `Setup.exe`, attached to the release on tag push.
- macOS build: `dev/build_mac_app.sh` → `.app`, `dev/build_mac_pkg.sh` → `MyBookshelf.pkg`
- macOS install automation: `dev/installer/mac_postinstall.sh` (Python · venv)
- Unattended install scripts: `install-mybookshelf.sh` (macOS) · `install-mybookshelf.ps1` (Windows)
- Run from source: `streamlit run core/pipeline_app.py`
- Tests: `PYTHONPATH=core python -m unittest discover -s core/tests`

</details>
