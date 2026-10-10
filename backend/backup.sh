#!/usr/bin/env bash
# SQLite backup for the Gumroad Automation backend.
# Usage: bash backup.sh [backup_dir]
# Keeps the 7 most recent backups. Safe to run while the backend is live
# (uses sqlite3's online backup API, not a raw file copy).
set -euo pipefail
cd "$(dirname "$0")"
BACKUP_DIR="${1:-$HOME/workspace/gumroad-automation/backups}"
mkdir -p "$BACKUP_DIR"
STAMP="$(date +%Y%m%d-%H%M%S)"
OUT="$BACKUP_DIR/gumroad_app-$STAMP.db"
sqlite3 gumroad_app.db ".backup '$OUT'"
chmod 600 "$OUT"
# Prune to the 7 newest.
ls -t "$BACKUP_DIR"/gumroad_app-*.db | tail -n +8 | xargs -r rm -f
echo "Backup written: $OUT"
echo "To restore: stop the backend, then: cp '$OUT' gumroad_app.db"
