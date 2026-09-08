"""Small, escaped and keyboard-accessible HTML building blocks."""
from html import escape

_ICONS = {
    "menu": '<path d="M3 3h7v7H3z M14 3h7v7h-7z M3 14h7v7H3z M14 14h7v7h-7z"/>',
    "1_txt": '<path d="M6 3h8l4 4v14H6z M14 3v5h4 M9 12h6 M9 16h6"/>',
    "2_split": '<circle cx="6" cy="6" r="3"/><circle cx="6" cy="18" r="3"/><path d="m8 8 12 12 M8 16 20 4"/>',
    "3_translate": '<path d="M3 5h12 M9 2v3 M5 5c0 6 5 9 9 10 M13 5c-1 6-5 9-10 11 M14 21l4-11 4 11 M16 17h4"/>',
    "4_summary": '<path d="M5 3h14v18H5z M8 7h8 M8 11h8 M8 15h5"/>',
    "5_wiki": '<path d="M12 5C8 2 4 3 2 4v16c3-2 7-2 10 0 3-2 7-2 10 0V4c-3-1-7-2-10 1z M12 5v15"/>',
    "settings": '<path d="M4 5h16 M4 12h16 M4 19h16 M8 2v6 M16 9v6 M10 16v6"/>',
}


def navigation_html(items, active: str, locked: bool, label: str) -> str:
    links = []
    for ident, name in items:
        text = escape(name, quote=True)
        current = ident == active
        attrs = f'class="stage-nav-link{" active" if current else ""}" title="{text}" aria-label="{text}"'
        if current:
            attrs += ' aria-current="page"'
        if locked:
            attrs += ' aria-disabled="true" tabindex="0" role="link"'
        else:
            attrs += f' href="?view={escape(ident, quote=True)}" target="_self"'
        icon = f'<svg viewBox="0 0 24 24" aria-hidden="true" focusable="false">{_ICONS.get(ident, _ICONS["menu"])}</svg>'
        body = icon + (f'<span class="nav-current-label">{escape(name)}</span>' if current else '')
        body += f'<span class="nav-tooltip" aria-hidden="true">{escape(name)}</span>'
        tag = 'span' if locked else 'a'
        links.append(f'<{tag} {attrs}>{body}</{tag}>')
    return f'<nav class="stage-nav" aria-label="{escape(label, quote=True)}">' + ''.join(links) + '</nav>'


def status_chip(text: str, details: str) -> str:
    return (f'<span class="status-chip" tabindex="0" title="{escape(details, quote=True)}" '
            f'aria-label="{escape(details, quote=True)}">{escape(text)}</span>')


# Keep all narrow-screen overrides together, after the desktop rules. No viewport
# bridge or rerun: resizing never resets selections or interrupts a background job.
COMPACT_CSS = """
.st-key-app_brand h1 { font-size:calc(34px * var(--mb-font-scale)) !important; }
.st-key-app_brand .mb-version { font-size:calc(13px * var(--mb-font-scale)) !important; white-space:nowrap; }
[class*="st-key-stage_folders_"] { margin-top:6px; }
[class*="st-key-chapter_children_"] {
    padding-left:20px; box-sizing:border-box; min-width:0;
    border-left:2px solid #e5e7eb; margin-bottom:10px;
}
[class*="st-key-list_group_"] [data-testid="stHorizontalBlock"] {
    display:grid !important; grid-template-columns:32px minmax(0,1fr); gap:4px;
}
[class*="st-key-list_group_"] [data-testid="stColumn"] { min-width:0 !important; width:100% !important; }
[class*="st-key-list_header_"] [data-testid="stHorizontalBlock"] { column-gap:14px !important; }
[class*="st-key-format_row_"] [data-testid="stHorizontalBlock"] {
    display:grid !important; grid-template-columns:minmax(0,1fr) 40px; gap:8px; align-items:center;
}
[class*="st-key-format_row_"] [data-testid="stHorizontalBlock"] > [data-testid="stColumn"] {
    width:100% !important; min-width:0 !important;
}
[class*="st-key-format_row_"] button { min-height:40px; padding:6px !important; }
[class*="st-key-document_row_"] [data-testid="stHorizontalBlock"] {
    display:grid !important; grid-template-columns:32px minmax(0,1fr) 44px; gap:4px;
}
[class*="st-key-document_row_"] [data-testid="stColumn"] { min-width:0 !important; width:100% !important; }
[class*="st-key-document_row_"] [data-testid="stHorizontalBlock"] > [data-testid="stColumn"]:nth-child(1) { grid-column:1; grid-row:1; }
[class*="st-key-document_row_"] [data-testid="stHorizontalBlock"] > [data-testid="stColumn"]:nth-child(2) { grid-column:2 / -1; grid-row:1; }
[class*="st-key-document_row_"] [data-testid="stHorizontalBlock"] > [data-testid="stColumn"]:nth-child(3):not(:last-child) { grid-column:3; grid-row:2; width:40px !important; }
[class*="st-key-document_row_"] [data-testid="stHorizontalBlock"] > [data-testid="stColumn"]:last-child:nth-child(n+3) { grid-column:2; grid-row:2; justify-self:start; width:40px !important; }
@media (max-width:560px) {
    .block-container { padding: .65rem .65rem 1.5rem !important; }
    [data-testid="stVerticalBlock"] { gap:.65rem; }
    [data-testid="stHorizontalBlock"] { flex-direction:column !important; gap:.5rem; }
    [data-testid="stHorizontalBlock"] > [data-testid="stColumn"] {
        width:100% !important; flex:1 1 auto !important; min-width:0 !important;
    }
    [data-testid="stMarkdownContainer"] p,
    [data-testid="stMarkdownContainer"] li, [data-testid="stText"],
    label, input, textarea, .stButton button, .stFormSubmitButton button,
    [data-testid="stSelectbox"] input,
    [data-testid="stSelectbox"] [data-baseweb="select"] {
        font-size:calc(13px * var(--mb-font-scale)) !important; line-height:1.45;
    }
    [data-testid="stCaptionContainer"], [data-testid="stCaptionContainer"] p,
    [data-testid="stMarkdownContainer"] small, .status-chip {
        font-size:calc(11.5px * var(--mb-font-scale)) !important;
    }
    [data-testid="stMarkdownContainer"] h2,
    [data-testid="stMarkdownContainer"] h3,
    [data-testid="stMarkdownContainer"] h4 {
        font-size:calc(13.5px * var(--mb-font-scale)) !important; padding:.2rem 0;
    }
    .st-key-app_brand h1 { font-size:calc(20px * var(--mb-font-scale)) !important; }
    .st-key-app_brand .mb-version { font-size:calc(10.5px * var(--mb-font-scale)) !important; }
    [data-testid="stExpander"] summary p,
    .st-key-tq_scan button p { font-size:calc(12px * var(--mb-font-scale)) !important; }
    [data-testid="stFileUploaderDropzone"] small,
    [data-testid="stFileUploaderDropzoneInstructions"] small,
    [data-testid="stFileUploaderDropzoneInstructions"] span { font-size:calc(10px * var(--mb-font-scale)) !important; }
    [data-testid="stMarkdownContainer"] hr { margin:.7rem 0 !important; }
    [data-testid="stMarkdownContainer"] h1 img { width:32px; height:32px; margin-right:6px !important; }
    .menu-card { box-sizing:border-box; padding:10px 12px !important; }
    .menu-title { font-size:calc(14px * var(--mb-font-scale)) !important; }
    [data-testid="stText"] { white-space:pre-wrap; overflow-wrap:anywhere; }
    .stButton button, .stFormSubmitButton button { min-height:40px; padding:.35rem .6rem; }
    [data-testid="stCheckbox"] label { min-height:40px; }
    [data-testid="stFileUploaderDropzone"] { flex-direction:column; align-items:stretch; padding:.65rem !important; }
    [data-testid="stFileUploaderDropzoneInstructions"] { width:100%; }
    [data-baseweb="tab-list"] { max-width:100%; overflow-x:auto; }
    [data-testid="stRadio"] > div { flex-wrap:wrap; }
    [data-testid="stCode"] pre { white-space:pre-wrap; overflow-wrap:anywhere; }
    [data-testid="stDataFrame"] { height:300px !important; min-height:220px !important; }
    .stage-nav { display:grid; grid-template-columns:repeat(7,minmax(0,1fr)); gap:4px; }
    .stage-nav-link { min-width:0; min-height:40px; padding:8px 4px; }
    .stage-nav-link svg { width:20px; height:20px; }
    .nav-current-label { display:none; }
    [class*="st-key-document_row_"] { border-bottom:1px solid #d1d5db; padding:4px 0 8px; }
    [class*="st-key-document_row_"] small { display:block; }
    [class*="st-key-list_group_"] [data-testid="stHorizontalBlock"] {
        display:grid !important; grid-template-columns:32px minmax(0,1fr);
    }
    [class*="st-key-list_header_"] [data-testid="stHorizontalBlock"] {
        display:grid !important; grid-template-columns:minmax(0,1.3fr) minmax(0,1fr) auto; align-items:center;
    }
}
"""


def font_scale(value) -> float:
    try:
        return min(1.35, max(0.85, float(value)))
    except (TypeError, ValueError):
        return 1.0


def window_geometry(screen_width, screen_height, saved=None):
    """Clamp restored logical pixels to the current display, including small screens."""
    max_w, max_h = max(320, int(screen_width * .95)), max(240, int(screen_height * .90))
    min_w, min_h = min(380, max_w), min(600, max_h)
    saved = saved if isinstance(saved, dict) else {}
    try:
        width, height = int(saved.get("width", 1100)), int(saved.get("height", 820))
    except (TypeError, ValueError, OverflowError):
        width, height = 1100, 820
    return max(min_w, min(width, max_w)), max(min_h, min(height, max_h)), min_w, min_h
