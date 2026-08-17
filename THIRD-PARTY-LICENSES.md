# Third-party licenses

My Bookshelf's own source code is licensed under PolyForm Noncommercial 1.0.0
(see `LICENSE`) — free for personal/noncommercial use, commercial use
prohibited. It depends on
the open-source packages below, either as Python libraries or as a bundled
binary tool.

## Bundled binary — requires attention

### Poppler (`vendor/poppler/`) — GPL v2 or later

**Scope.** The Poppler binary is bundled **only in the Windows distribution**
(`vendor/poppler/Library/bin/pdftotext.exe`, used as the PDF text-extraction
fallback). The macOS build does **not** redistribute Poppler: it calls a
`pdftotext` that the user installs themselves (e.g. `brew install poppler`),
so the obligations below apply to the Windows release.

- Version bundled: Poppler 26.02.0
- Upstream project: https://poppler.freedesktop.org/
- **Corresponding source (direct download):**
  https://poppler.freedesktop.org/poppler-26.02.0.tar.xz

**No effect on the rest of the project.** My Bookshelf invokes `pdftotext` as a
separate subprocess and does not link against Poppler, so the two are merely
aggregated on the same medium. This does not place My Bookshelf's own code
under the GPL. The GPL license text ships alongside the binary at
`vendor/poppler/share/poppler/COPYING` and `COPYING.gpl2`.

**How we satisfy the source-code requirement.** Poppler is offered under "GPL
v2 or later", and for this redistribution we elect **GPL v3**. Under GPL v3
section 6(d), we offer access to the Corresponding Source from the third-party
server named above, and these directions sit next to the object code we
distribute. A link to a project homepage would not be enough on its own, so we
link the exact source archive for the exact version we ship.

**Written offer (also valid under GPL v2 section 3(b)).** In addition, for at
least three years from the date you received this distribution, we will give
any third party a complete machine-readable copy of the Corresponding Source
for the Poppler binary we shipped — including the source of the specific build,
if it differs in any way from the upstream archive above — for no more than our
cost of physically performing the distribution. To request it, open an issue at
https://github.com/Brightinyou/my-bookshelf-for-pc/issues .

## Python libraries — permissive (MIT / BSD / Apache-2.0 / MPL-2.0)

| Package | License |
|---|---|
| rhwp-python | MIT |
| python-docx | MIT |
| python-hwpx | Apache-2.0 |
| pythonnet | MIT |
| anthropic | MIT |
| pypdfium2 | BSD-3-Clause, Apache-2.0 (bundles Google's PDFium; see the package's own `LICENSE` for PDFium's third-party dependency licenses) |
| pandas | BSD-3-Clause |
| psutil | BSD-3-Clause |
| pywebview | BSD-3-Clause |
| streamlit | Apache-2.0 |
| google-genai | Apache-2.0 |
| openai | Apache-2.0 |
| Pillow | MIT-CMU |
| certifi | MPL-2.0 (used unmodified — bundled CA certificate data) |

These are all permissive (or, for certifi, effectively so when used
unmodified): they require preserving the copyright notice and license text,
but do not require releasing this project's own source code. Each package's
full license text ships with its installed distribution
(`*.dist-info/licenses/` or `*.dist-info/METADATA` under `.venv/`) and is also
available from the project's own repository/PyPI page.
