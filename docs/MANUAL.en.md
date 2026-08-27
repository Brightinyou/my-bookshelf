# My Bookshelf — User manual

A detailed walkthrough of every tab's buttons and options. For installation and AI setup, see the [README](../README.en.md).

---

## The workflow in detail
Switch stages from the top menu. Every upload area accepts **file picker or drag & drop**. The "open folder" buttons are tucked into a small expander so the actual work area stands out.

> **When a stage finishes, a popup asks about the next step.** For example, after text conversion it asks *"Split into chapters next?"* — press **[Yes, proceed now]** and **only the book you just processed** advances and runs automatically (other queued books are left untouched). To process several at once or pick manually, use **[Choose on the screen]** to open the regular queue view. The popup closes while processing so the progress bar and Stop button stay visible.

## ① 📄 Text conversion
- Uploaded PDF/DOCX/HWP/HWPX/TXT files stack up in the **processing queue**.
- Select items and press **[Convert to text]** — extracts the text and saves TXT. The original document is kept.
- **[Delete]** removes mistakenly added files.
- **Fetch from a paper source**: pull a paper by URL, DOI or arXiv number (for login/paywalled pages, download the PDF yourself and upload it).
- **🔬 Text quality check**: for scanned PDFs or poor OCR, this flags the bad pages and **re-reads them with AI** (a few minutes to tens of minutes depending on page count).

## ② ✂️ Chapter split
- Splits a book TXT into **per-chapter files** under a per-book folder.
- **[Split]** — split into chapters. **[Move to next step]** — if no split is needed, send the whole document onward (when source differs from the target language → Translation; otherwise → Summaries).
- Short documents are handled separately under "Short documents".

## ③ 🌐 Translation

*Multiple source languages → your chosen target*
- Detects the source language automatically, including English, German, Dutch, French, Spanish, Italian, Portuguese, Latin, Japanese, Chinese, Russian, Greek, Hebrew, and Arabic.
- Choose the output language in `⚙️ Settings → 🎯 Target language`: Korean, English, Japanese, Chinese, German, French, Spanish, Italian, Portuguese, Dutch, or Russian. Korean is the default.
- The target language applies consistently to translations, chapter summaries, and Wiki notes. It is separate from the interface language.
- Output files are named after the **target language** — `_ko.txt` for Korean, `_en.txt` for English, `_ja.txt` for Japanese, and so on. Enable the **Bilingual** toggle to also create `_bilingual.txt`, which pairs source and translation by paragraph.
- Existing translations and summaries remain in their previous language. Delete them and run the stage again after changing the target.

## ④ 📝 Summaries
- Creates per-chapter summary notes (`_wiki.md`) — author, key summary, overview, key quotes, key keywords (with explanations).
- Summaries are written as **direct statements of the content**, not "the author says …".
- **Length control**: in the Settings tab or the collapsible **"Adjust summary length"** here, set the summary body to **5–40 % of the source** (15 % default). Higher values make longer notes and increase **output tokens / API cost** (input tokens for the source stay the same). Short chapters keep a minimum length.
- Select queued items and press **[▶ Start]**.

## ⑤ 📖 Output

*Create EPUB · Create DOCX · Create HWPX · Wiki*
- This stage has **four independent toggles**. Enable any combination to generate every selected format.
  - **EPUB e-book** *(full text, not a summary)*: packages the complete source/translated chapters into an `.epub` in `5_전자책(EPUB)`. It is instant once optional Korean line-break repair has finished. ⚠️ This reproduces the entire copyrighted work. Use it only on documents **you already have the right to use**, and only within your own personal use. What copying, translation, or format conversion is permitted varies by country and by how you obtained the document — this feature grants you no right to distribute or share the result.
  - **Line-break repair** *(optional, Korean source books)*: restores printed line breaks into readable paragraphs before EPUB export. AI decides whitespace only; it does not alter the body text.
  - **Word document (DOCX)** *(summary-based)*: saves editable summaries in `5_위키문서(DOCX)`.
  - **Hangul document (HWPX)** *(summary-based)*: saves editable summaries in `5_위키문서(HWPX)`.
  - **Obsidian Wiki** *(summary-based)*: saves a hub note and per-chapter notes in the selected vault.
  - Select at least one output.
- The note/document frontmatter is auto-filled with **author, publication date, and publisher (`Place: Publisher`)**, extracted from the source's title/colophon page (left blank if not confidently found).
- The EPUB opens with a **title page** carrying the title, subtitle, author and citation (title and subtitle centred, author right-aligned).
- If a book is already reflected, the popup asks **"Replace?"** to update it in place.
- Use **[Select all]/[Clear]** in the queue, then **[▶ Start]**.
