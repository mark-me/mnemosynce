#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 2 || $# -gt 3 ]]; then
    echo "Usage: $0 <name> <backup_dir> [log_file]"
    exit 1
fi

NAME_SNAPSHOT=$1
DIR_BACKUP=$2
DIR_SNAPSHOT="${DIR_BACKUP%/}/${NAME_SNAPSHOT}"

# Accept an explicit log path from the caller (backup_task.py passes this so
# the file lands where the email reporter expects it).  Fall back to the old
# location inside the snapshot directory when called standalone.
FILE_LOG="${3:-${DIR_SNAPSHOT}/remove_old.log}"

mkdir -p "$DIR_SNAPSHOT"
echo "===== Retention $NAME_SNAPSHOT $(date) =====" > "$FILE_LOG"

# ---------------------------------------------------------------------------
# BusyBox-compatible date helpers
# 'date -d' on BusyBox uses a different syntax to GNU date:
#   GNU:     date -d "3 months ago" / date -d "last monday"
#   BusyBox: date -d "-3 months"    / no 'last X' support
# We compute offsets via Python (always present in the Alpine image).
# ---------------------------------------------------------------------------

date_offset() {
    python3 -c "
from datetime import date, timedelta
print((date.today() + timedelta(days=${1})).isoformat())
"
}

year_of_offset() {
    python3 -c "
from datetime import date
d = date.today()
print(d.year - ${1})
"
}

month_start_offset() {
    python3 -c "
from datetime import date
d = date.today()
month = d.month - ${1}
year  = d.year
while month <= 0:
    month += 12
    year  -= 1
print(f'{year:04d}-{month:02d}')
"
}

last_monday_offset() {
    python3 -c "
from datetime import date, timedelta
d = date.today()
last_monday = d - timedelta(days=d.weekday() + 7 * ${1})
print(last_monday.isoformat())
"
}

# ---------------------------------------------------------------------------

list_all_dirs() {
    find "$DIR_SNAPSHOT" -mindepth 1 -maxdepth 1 -type d \
        | xargs -I{} basename {}
}

ALL_DIRS=$(list_all_dirs)

if [[ -z "$ALL_DIRS" ]]; then
    echo "No backups found, nothing to clean" >> "$FILE_LOG"
    exit 0
fi

listYearlyBackups() {
    for i in 0 1 2 3 4 5; do
        local yr
        yr=$(year_of_offset "$i")
        echo "$ALL_DIRS" | { grep -E "^${yr}-[0-9]{2}-[0-9]{2}$" || true; } \
            | LC_ALL=C sort | head -n 1
    done
}

listMonthlyBackups() {
    for i in $(seq 0 12); do
        local ym
        ym=$(month_start_offset "$i")
        echo "$ALL_DIRS" | { grep -E "^${ym}-[0-9]{2}$" || true; } \
            | LC_ALL=C sort | head -n 1
    done
}

listWeeklyBackups() {
    for i in 0 1 2 3 4; do
        local d
        d=$(last_monday_offset "$i")
        echo "$ALL_DIRS" | { grep -Fx "$d" || true; }
    done
}

listDailyBackups() {
    for i in 0 1 2 3 4 5 6; do
        local d
        d=$(date_offset "-${i}")
        echo "$ALL_DIRS" | { grep -Fx "$d" || true; }
    done
}

listUniqueBackups() {
    {
        listYearlyBackups
        listMonthlyBackups
        listWeeklyBackups
        listDailyBackups
    } | LC_ALL=C sort -u
}

KEEP_FILE=$(mktemp)
trap 'rm -f "$KEEP_FILE"' EXIT

listUniqueBackups > "$KEEP_FILE"

if [[ ! -s "$KEEP_FILE" ]]; then
    echo "WARNING: keep list is empty, skipping deletion" >> "$FILE_LOG"
    exit 1
fi

echo "Keeping:" >> "$FILE_LOG"
cat "$KEEP_FILE" >> "$FILE_LOG"
echo "Determining backups to delete..." >> "$FILE_LOG"

echo "$ALL_DIRS" | grep -vxFf "$KEEP_FILE" | while read -r file_to_delete; do
    echo "Removing $file_to_delete" >> "$FILE_LOG"
    FULL_PATH="$DIR_SNAPSHOT/$file_to_delete"
    if [[ -n "$file_to_delete" && -d "$FULL_PATH" && "$FULL_PATH" == "$DIR_SNAPSHOT/"* ]]; then
        rm -rf -- "$FULL_PATH"
    fi
done

echo "Retention complete" >> "$FILE_LOG"
