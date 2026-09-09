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

- Version bundled: Poppler 25.07.0, as built and packaged by
  poppler-windows release `v25.07.0-0`
- Upstream project: https://poppler.freedesktop.org/
- **Corresponding source (direct download):**
  https://poppler.freedesktop.org/poppler-25.07.0.tar.xz
- **Corresponding source for the Windows build we actually ship** (this build
  is configured and compiled differently from the upstream archive, and carries
  its own dependency set): https://github.com/oschwartz10612/poppler-windows
  at tag `v25.07.0-0`

**No effect on the rest of the project.** My Bookshelf invokes `pdftotext` as a
separate subprocess and does not link against Poppler, so the two are merely
aggregated on the same medium. This does not place My Bookshelf's own code
under the GPL. The full text of the GPL version 2 ships alongside the binary,
installed as `poppler/share/poppler/COPYING.gpl2` in the application folder
(`COPYING` and `COPYING.adobe` next to it are poppler-data's own notices, not
the GPL text). The Windows build fails if that text is missing or truncated, so
a package cannot go out without it.

**How we satisfy the source-code requirement.** Poppler is offered under "GPL
v2 or later", and for this redistribution we elect **GPL v2**. We elect v2
because v2 is the license whose full text we actually convey with the binary,
as GPL v2 section 1 requires.

Under GPL v2, a distributor of object code must pick one of the three options in
section 3. Version 2 has no equivalent of the GPL v3 section 6(d) "offer access
from a network server" option, so a download link cannot by itself discharge the
obligation. **We rely on section 3(b): the written offer below.** That offer is
what satisfies the requirement, and it is conveyed with the object code —
`THIRD-PARTY-LICENSES.md` is installed into the application folder by the
Windows installer.

The source links above are provided as a convenience so that most people never
need to invoke the offer. They do not replace it.

**Written offer (GPL v2 section 3(b)).** For at
least three years from the date you received this distribution, we will give
any third party a complete machine-readable copy of the Corresponding Source
for the Poppler binary we shipped — including the source of the specific build,
if it differs in any way from the upstream archive above — for no more than our
cost of physically performing the distribution. To request it, open an issue at
https://github.com/Brightinyou/my-bookshelf/issues .

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
