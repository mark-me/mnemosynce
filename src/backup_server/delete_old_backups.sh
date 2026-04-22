set -euo pipefail

NAME_SNAPSHOT=$1
DIR_BACKUP=$2
DIR_SNAPSHOT="${DIR_BACKUP%/}/${NAME_SNAPSHOT}"
FILE_LOG="${DIR_SNAPSHOT}/remove_old.log"

mkdir -p "$DIR_SNAPSHOT"
echo "===== Retention $NAME_SNAPSHOT $(date) =====" > "$FILE_LOG"

list_all_dirs() {
    find "$DIR_SNAPSHOT" -mindepth 1 -maxdepth 1 -type d -printf '%f\n' | sed 's/[[:space:]]*$//'
}

ALL_DIRS=$(list_all_dirs)

if [[ -z "$ALL_DIRS" ]]; then
    echo "No backups found, nothing to clean" >> "$FILE_LOG"
    exit 0
fi

listYearlyBackups() {
    for i in 0 1 2 3 4 5; do
        (echo "$ALL_DIRS" | grep -E "$(date +%Y -d "${i} year ago")-[0-9]{2}-[0-9]{2}" || true) | sort | head -n 1
    done
}

listMonthlyBackups() {
    for i in {0..12}; do
        (echo "$ALL_DIRS" | grep -E "$(date +%Y-%m -d "${i} month ago")-[0-9]{2}" || true) | sort | head -n 1
    done
}

listWeeklyBackups() {
    for i in 0 1 2 3 4; do
        (echo "$ALL_DIRS" | grep "$(date +%Y-%m-%d -d "last monday -${i} weeks")" || true)
    done
}

listDailyBackups() {
    for i in 0 1 2 3 4 5 6; do
        (echo "$ALL_DIRS" | grep "$(date +%Y-%m-%d -d "-${i} day")" || true)
    done
}

listUniqueBackups() {
    {
        listYearlyBackups
        listMonthlyBackups
        listWeeklyBackups
        listDailyBackups
    } | sort -u
}

KEEP_FILE=$(mktemp)
trap 'rm -f "$KEEP_FILE"' EXIT

listUniqueBackups > "$KEEP_FILE"

if [[ ! -s "$KEEP_FILE" ]]; then
    echo "WARNING: keep list is empty, skipping deletion" >> "$FILE_LOG"
    exit 1
fi

echo "Determining backups to delete..." >> "$FILE_LOG"

echo "$ALL_DIRS" | grep -vxFf "$KEEP_FILE" | while read -r file_to_delete; do
    echo "Removing $file_to_delete" >> "$FILE_LOG"
    if [[ -n "$file_to_delete" && -d "$DIR_SNAPSHOT/$file_to_delete" ]]; then
        rm -rf -- "$DIR_SNAPSHOT/$file_to_delete" >> "$FILE_LOG" 2>&1
    fi
done