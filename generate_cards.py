#!/usr/bin/env python3
"""Generate Obsidian card notes from oracle-cards.sql."""

import re
import os
import html as html_module
from collections import defaultdict

SQL_FILE = '/home/lilly/Documents/zap-vault/db/oracle-cards.sql'
OUT_DIR  = '/home/lilly/Documents/zap-vault/zap-oracle-vault/cards'


# ── SQL parser ───────────────────────────────────────────────────────────────

def fix_encoding(s):
    """Re-decode latin-1 string that actually contains UTF-8 bytes (up to 2 passes)."""
    for _ in range(2):
        try:
            decoded = s.encode('latin-1').decode('utf-8')
            s = decoded
        except (UnicodeDecodeError, UnicodeEncodeError):
            break
    return s


def parse_sql_values(data):
    rows = []
    i = 0; n = len(data)
    while i < n:
        if data[i] == '(':
            i += 1; fields = []
            while True:
                while i < n and data[i] == ' ':
                    i += 1
                if i >= n:
                    break
                if data[i] == "'":
                    i += 1; val = []
                    while i < n:
                        c = data[i]
                        if c == '\\':
                            nc = data[i + 1]
                            val.append({"'": "'", 'n': '\n', 'r': '\r', '\\': '\\'}.get(nc, nc))
                            i += 2
                        elif c == "'":
                            i += 1; break
                        else:
                            val.append(c); i += 1
                    fields.append(fix_encoding(''.join(val)))
                elif data[i:i+4] == 'NULL':
                    fields.append(None); i += 4
                else:
                    j = i
                    while i < n and data[i] not in (',', ')'):
                        i += 1
                    fields.append(data[j:i].strip())
                while i < n and data[i] == ' ':
                    i += 1
                if i < n and data[i] == ',':
                    i += 1
                elif i < n and data[i] == ')':
                    i += 1; break
            rows.append(fields)
        elif data[i] in (',', '\n', ' '):
            i += 1
        else:
            i += 1
    return rows


# ── HTML → Markdown ──────────────────────────────────────────────────────────

def html_to_md(html_str):
    if not html_str:
        return ''

    s = html_str

    s = re.sub(r'<br\s*/?>', '\n', s, flags=re.IGNORECASE)
    s = re.sub(r'</p>\s*<p[^>]*>', '\n\n', s, flags=re.IGNORECASE)
    s = re.sub(r'<p[^>]*>', '', s, flags=re.IGNORECASE)
    s = re.sub(r'</p>', '\n\n', s, flags=re.IGNORECASE)
    s = re.sub(r'</?(?:div|section|article|header|footer)[^>]*>', '\n\n', s, flags=re.IGNORECASE)

    s = re.sub(r'<ul[^>]*>', '\n', s, flags=re.IGNORECASE)
    s = re.sub(r'</ul>', '\n', s, flags=re.IGNORECASE)
    s = re.sub(r'<ol[^>]*>', '\n', s, flags=re.IGNORECASE)
    s = re.sub(r'</ol>', '\n', s, flags=re.IGNORECASE)
    s = re.sub(r'<li[^>]*>(.*?)</li>', lambda m: f'- {m.group(1).strip()}\n', s, flags=re.IGNORECASE | re.DOTALL)
    s = re.sub(r'<li[^>]*>', '- ', s, flags=re.IGNORECASE)

    for lvl in range(6, 0, -1):
        s = re.sub(rf'<h{lvl}[^>]*>(.*?)</h{lvl}>', lambda m, l=lvl: '\n' + '#' * l + ' ' + m.group(1).strip() + '\n', s, flags=re.IGNORECASE | re.DOTALL)

    s = re.sub(r'<a\s[^>]*href=["\']([^"\']*)["\'][^>]*>(.*?)</a>', lambda m: f'[{m.group(2).strip()}]({m.group(1)})', s, flags=re.IGNORECASE | re.DOTALL)

    s = re.sub(r'<(?:b|strong)[^>]*>(.*?)</(?:b|strong)>', lambda m: f'**{m.group(1).strip()}**', s, flags=re.IGNORECASE | re.DOTALL)
    s = re.sub(r'<(?:i|em)[^>]*>(.*?)</(?:i|em)>', lambda m: f'*{m.group(1).strip()}*', s, flags=re.IGNORECASE | re.DOTALL)

    s = re.sub(r'<blockquote[^>]*>(.*?)</blockquote>', lambda m: '\n> ' + m.group(1).strip().replace('\n', '\n> ') + '\n', s, flags=re.IGNORECASE | re.DOTALL)

    s = re.sub(r'<hr\s*/?>', '\n---\n', s, flags=re.IGNORECASE)
    s = re.sub(r'<[^>]+>', '', s)
    s = html_module.unescape(s)
    s = re.sub(r'\n{3,}', '\n\n', s)
    s = s.strip()

    return s


# ── Slug ─────────────────────────────────────────────────────────────────────

def slugify(title):
    s = title.lower()
    s = re.sub(r'[^\w\s-]', '', s)
    s = re.sub(r'[\s_]+', '-', s)
    s = re.sub(r'-+', '-', s)
    s = s.strip('-')
    return s


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    with open(SQL_FILE, encoding='latin-1') as f:
        content = f.read()

    insert_start = content.find("INSERT INTO `cards` VALUES ")
    insert_end   = content.find(";\n/*!40000 ALTER TABLE `cards` ENABLE KEYS", insert_start)
    insert_data  = content[insert_start + len("INSERT INTO `cards` VALUES "):insert_end]

    rows = parse_sql_values(insert_data)
    print(f"Parsed {len(rows)} rows")

    # 0=id, 1=title, 2=caption, 3=subcaption, 4=private_comment,
    # 5=filename, 6=footnote, 7=disabled, 8=copyright, 9=crt_date, 10=mod_date

    active = [r for r in rows if r[7] == '0']
    print(f"Active: {len(active)}")

    title_groups = defaultdict(list)
    for r in active:
        title = (r[1] or '').strip()
        if title:
            title_groups[title.lower()].append(r)

    chosen = {}
    for title_lower, group in title_groups.items():
        best = sorted(group, key=lambda r: (r[10] or '0000-00-00 00:00:00', r[0]), reverse=True)[0]
        chosen[title_lower] = best

    print(f"Unique cards after dedup: {len(chosen)}")

    os.makedirs(OUT_DIR, exist_ok=True)

    written = 0
    seen_slugs = {}

    for title_lower, r in sorted(chosen.items()):
        card_id  = r[0]
        title    = (r[1] or '').strip()
        caption  = html_to_md(r[2] or '')
        footnote = html_to_md(r[6] or '')
        filename = (r[5] or '').strip()
        mod_date = (r[10] or '').strip()
        crt_date = (r[9] or '').strip()

        slug = slugify(title)
        if slug in seen_slugs:
            seen_slugs[slug] += 1
            slug = f"{slug}-{seen_slugs[slug]}"
        else:
            seen_slugs[slug] = 0

        lines = []

        # ── Frontmatter ──
        lines.append('---')
        lines.append(f'title: "{title}"')
        lines.append(f'card_id: {card_id}')
        if mod_date and mod_date != '0000-00-00 00:00:00':
            lines.append(f'modified: {mod_date[:10]}')
        if crt_date and crt_date != '0000-00-00 00:00:00':
            lines.append(f'created: {crt_date[:10]}')
        lines.append('tags: [oracle-card]')
        lines.append('---')
        lines.append('')

        # ── Title ──
        lines.append(f'# {title}')
        lines.append('')

        # ── Image ──
        if filename:
            lines.append(f'![[{filename}]]')
            lines.append('')

        # ── Card text ──
        if caption:
            lines.append(caption)
            lines.append('')

        # ── Footnote (source references) ──
        if footnote:
            lines.append('---')
            lines.append('')
            lines.append(footnote)
            lines.append('')

        # ── Notes ──
        lines.append('---')
        lines.append('')
        lines.append('## Notes')
        lines.append('')
        lines.append('')

        # ── Back to Oracle ──
        lines.append('---')
        lines.append('')
        lines.append('[[Oracle]]')
        lines.append('')

        fpath = os.path.join(OUT_DIR, f"{slug}-card.md")
        with open(fpath, 'w', encoding='utf-8') as f:
            f.write('\n'.join(lines))
        written += 1

    print(f"Written {written} cards to {OUT_DIR}/")


if __name__ == '__main__':
    main()
