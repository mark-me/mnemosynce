#!/usr/bin/env bash
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

    # Find the most recent snapshot — must be an actual directory, not a file.
    # Non-directory entries with date-like names indicate corruption; warn and skip them.
    LAST_DAY=""
    while IFS= read -r entry; do
        full_path="${DIR_SNAPSHOT}/${entry}"
        if [[ -d "$full_path" ]]; then
            LAST_DAY="$entry"
        else
            echo "$(date +%Y-%m-%d\ %H:%M:%S) : WARNING: expected directory but found non-directory '${full_path}', skipping" >> "$FILE_LOG"
            echo "WARNING: '${full_path}' is not a directory — possible corruption. Skipping." >&2
        fi
    done < <(find "$DIR_SNAPSHOT" -mindepth 1 -maxdepth 1 \
        -exec basename {} \; | grep -E '^[0-9]{4}-[0-9]{2}-[0-9]{2}$' | sort)

    # Don't use today's existing snapshot as the link-dest source.
    if [[ "$LAST_DAY" == "$TODAY" ]]; then
        LAST_DAY=""
    fi

    DIR_LASTDAY=""
    if [[ -n "$LAST_DAY" ]]; then
        DIR_LASTDAY="${DIR_SNAPSHOT}/${LAST_DAY}"
    fi

    if [[ ! -e "$DIR_TODAY" ]]; then
        if [[ -n "$DIR_LASTDAY" && -d "$DIR_LASTDAY" ]]; then
            echo "$(date +%Y-%m-%d\ %H:%M:%S) : Creating snapshot from $DIR_LASTDAY to $DIR_TODAY" >> "$FILE_LOG"
            cp -al "$DIR_LASTDAY" "$DIR_TODAY" >> "$FILE_LOG" 2>&1
        else
            echo "$(date +%Y-%m-%d\ %H:%M:%S) : Creating initial backup directory $DIR_TODAY" >> "$FILE_LOG"
            mkdir -p "$DIR_TODAY"
        fi
    elif [[ ! -d "$DIR_TODAY" ]]; then
        # A non-directory file is squatting on today's path — refuse to proceed.
        echo "$(date +%Y-%m-%d\ %H:%M:%S) : ERROR: '${DIR_TODAY}' exists but is not a directory. Remove it manually and retry." >> "$FILE_LOG"
        echo "ERROR: '${DIR_TODAY}' exists but is not a directory. Remove it manually and retry." >&2
        exit 1
    else
        echo "$(date +%Y-%m-%d\ %H:%M:%S) : Backup for $TODAY already exists, continuing (rsync will update)" >> "$FILE_LOG"
    fi

    echo "$(date +%Y-%m-%d\ %H:%M:%S) : Starting backup for $TODAY" >> "$FILE_LOG"
    echo "Running rsync from '$DIR_SOURCE' to '$DIR_TODAY'" >> "$FILE_LOG"

    if ! rsync \
        -az --delete --delete-excluded \
        --numeric-ids \
        --exclude-from="$FILE_EXCLUDES" \
        "$DIR_SOURCE"/ "$DIR_TODAY"/ >> "$FILE_LOG" 2>&1
    then
        echo "$(date +%Y-%m-%d\ %H:%M:%S) : ERROR during rsync, removing incomplete snapshot" >> "$FILE_LOG"
        if [[ -n "$DIR_TODAY" && "$DIR_TODAY" == "$DIR_SNAPSHOT/"* ]]; then
            rm -rf "$DIR_TODAY"
        fi
        exit 1
    fi

    echo "$(date +%Y-%m-%d\ %H:%M:%S) : Backup completed successfully" >> "$FILE_LOG"
}

create_backup
