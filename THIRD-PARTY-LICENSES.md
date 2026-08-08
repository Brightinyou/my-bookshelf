# Third-party licenses

My Bookshelf's own source code is MIT-licensed (see `LICENSE`). It depends on
the open-source packages below, either as Python libraries or as a bundled
binary tool.

## Bundled binary — requires attention

### Poppler (`vendor/poppler/`) — GPL v2 or later
- Version bundled: 26.02.0 (`pdftotext.exe`, used for PDF text extraction fallback)
- Source: https://poppler.freedesktop.org/
- My Bookshelf invokes `pdftotext` as a separate subprocess (not linked into
  the Python code), so this is "mere aggregation" — it does not place the
  rest of the codebase under the GPL. The GPL license text is bundled
  alongside the binary at `vendor/poppler/share/poppler/COPYING` and
  `COPYING.gpl2`. The corresponding source for this exact version is publicly
  available at the URL above.

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
