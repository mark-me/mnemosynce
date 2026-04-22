set -euo pipefail

if [[ $# -ne 3 ]]; then
    echo "Usage: $0 <name> <backup_dir> <source_dir>"
    exit 1
fi

NAME_SNAPSHOT=$1
DIR_BACKUP=$2
DIR_SOURCE=$3

create_backup() {
    TODAY=$(date +%Y-%m-%d)

    DIR_SNAPSHOT="${DIR_BACKUP%/}/${NAME_SNAPSHOT}"
    DIR_TODAY="${DIR_SNAPSHOT}/${TODAY}"
    FILE_LOG="${DIR_SNAPSHOT}/backup.log"
    FILE_EXCLUDES="${DIR_SNAPSHOT}/excludes.lst"

    # Locking
    LOCK_FILE="/tmp/${NAME_SNAPSHOT}.lock"
    exec 200>"$LOCK_FILE"
    flock -n 200 || {
        echo "Another backup is already running for $NAME_SNAPSHOT"
        exit 1
    }
    trap 'rm -f "$LOCK_FILE"' EXIT

    mkdir -p "$DIR_SNAPSHOT"

    # Init log
    echo "===== Backup $NAME_SNAPSHOT $(date) =====" >> "$FILE_LOG"

    # Ensure excludes file exists
    [[ -f "$FILE_EXCLUDES" ]] || touch "$FILE_EXCLUDES"

    LAST_DAY=$(find "$DIR_SNAPSHOT" -mindepth 1 -maxdepth 1 -type d \
        -exec basename {} \; | grep -E '^[0-9]{4}-[0-9]{2}-[0-9]{2}$' | sort | tail -n 1 || true)

    if [[ "$LAST_DAY" == "$TODAY" ]]; then
        LAST_DAY=""
    fi

    DIR_LASTDAY=""
    if [[ -n "$LAST_DAY" ]]; then
        DIR_LASTDAY="${DIR_SNAPSHOT}/${LAST_DAY}"
    fi

    if [[ ! -d "$DIR_TODAY" ]]; then
        if [[ -n "$LAST_DAY" ]]; then
            echo "$TODAY $(date +%H:%M:%S) : Creating snapshot from $DIR_LASTDAY to $DIR_TODAY" >> "$FILE_LOG"
            cp -al "$DIR_LASTDAY" "$DIR_TODAY" >> "$FILE_LOG" 2>&1
        else
            echo "$TODAY $(date +%H:%M:%S) : Creating initial backup directory $DIR_TODAY" >> "$FILE_LOG"
            mkdir -p "$DIR_TODAY" >> "$FILE_LOG" 2>&1
        fi
    else
        echo "$TODAY $(date +%H:%M:%S) : Backup for $TODAY already exists, continuing (rsync will update)" >> "$FILE_LOG"
    fi

    echo "$TODAY $(date +%H:%M:%S) : Starting backup for $TODAY" >> "$FILE_LOG"
    echo "Running rsync from '$DIR_SOURCE' to '$DIR_TODAY'" >> "$FILE_LOG"

    if ! rsync \
        -az --delete --delete-excluded \
        --numeric-ids \
        --exclude-from="$FILE_EXCLUDES" \
        "$DIR_SOURCE"/ "$DIR_TODAY"/ >> "$FILE_LOG" 2>&1
    then
        echo "$TODAY $(date +%H:%M:%S) : ERROR during rsync, removing incomplete snapshot" >> "$FILE_LOG"
        if [[ -n "$DIR_TODAY" && "$DIR_TODAY" == "$DIR_SNAPSHOT/"* ]]; then
            rm -rf "$DIR_TODAY"
        fi
        exit 1
    fi
}

create_backup