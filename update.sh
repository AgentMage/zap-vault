#!/usr/bin/env bash
# Refreshes ~/zap-vault from the live oracle app.
# Run from anywhere: ~/zap-vault/update.sh
set -euo pipefail

VAULT="$(cd "$(dirname "$0")" && pwd)"
CARD_IMAGES_SRC="/home/lilly/php-oracle/html/oracle/card-images"
PATTERNS_SRC="/home/lilly/php-oracle/html/oracle/patterns"
SQL_SRC="/home/lilly/oracle-archive/zapoclea_oracle3.sql"
DB_OUT="$VAULT/db/oracle-cards.sql"

echo "=== ZapOracle vault update ==="

# --- DB export ---
echo "Extracting card tables from SQL dump..."
python3 - "$SQL_SRC" "$DB_OUT" << 'PYEOF'
import re, sys

include_tables = {'cards', 'cards_backup', 'link_cards_themes', 'positions', 'spreads', 'themes'}
src, dst = sys.argv[1], sys.argv[2]

with open(src, encoding='latin-1') as f:
    content = f.read()

preamble_match = re.search(r'--\n-- Table structure for table', content)
out_parts = [content[:preamble_match.start()]] if preamble_match else []

pattern = r'(--\n-- Table structure for table `(\w+)`.*?)(?=--\n-- Table structure for table `|\Z)'
matches = re.findall(pattern, content, re.DOTALL)

written = []
for block, table_name in matches:
    if table_name in include_tables:
        out_parts.append(block)
        written.append(table_name)

with open(dst, 'w', encoding='utf-8') as f:
    f.write(''.join(out_parts))

print(f"  Tables: {', '.join(written)}")
print(f"  Size:   {sum(len(p) for p in out_parts) / 1024 / 1024:.1f} MB -> {dst}")
PYEOF

# --- Images ---
echo "Syncing card images..."
rsync -a --delete --include='*.jpg' --include='*.jpeg' --include='*.JPG' \
    --include='*.png' --include='*.gif' --exclude='*' \
    --exclude='_large/' --exclude='thumbs/' \
    "$CARD_IMAGES_SRC/" "$VAULT/images/card-images/"
echo "  $(ls "$VAULT/images/card-images/" | wc -l) card images"

echo "Syncing patterns..."
rsync -a --delete --include='*.jpg' --include='*.jpeg' --include='*.png' \
    --exclude='*' \
    "$PATTERNS_SRC/" "$VAULT/images/patterns/"
echo "  $(ls "$VAULT/images/patterns/" | wc -l) patterns"

echo
echo "Done. Total size: $(du -sh "$VAULT" | cut -f1)"
