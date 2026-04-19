#!/bin/bash

NAME_SNAPSHOT=$1;
DIR_BACKUP=$2;
DIR_SNAPSHOT=$DIR_BACKUP/$NAME_SNAPSHOT;
FILE_LOG=${NAME_SNAPSHOT}_remove_old.log

printf "Log of step 2: Removing irrelevant backups - " + $NAME_SNAPSHOT + ' - ' > $FILE_LOG
date >> $FILE_LOG

function listYearlyBackups() {
        for i in 0 1 2 3 4 5
                do ls ${DIR_SNAPSHOT} | egrep "$(date +%Y -d "${i} year ago")-[0-9]{2}-[0-9]{2}" | sort -u | head -n 1
        done
}

function listMonthlyBackups() {
        for i in 0 1 2 3 4 5 6 7 8 9 10 11 12
                do ls ${DIR_SNAPSHOT} | egrep "$(date +%Y-%m -d "${i} month ago")-[0-9]{2}" | sort -u | head -n 1
        done
}

function listWeeklyBackups() {
        for i in 0 1 2 3 4
                do ls ${DIR_SNAPSHOT} | grep "$(date +%Y-%m-%d -d "last monday -${i} weeks")"
        done
}

function listDailyBackups() {
        for i in 0 1 2 3 4 5 6
                do ls ${DIR_SNAPSHOT} | grep "$(date +%Y-%m-%d -d "-${i} day")"
        done
}

function getAllBackups() {
        listYearlyBackups
        listMonthlyBackups
        listWeeklyBackups
        listDailyBackups
}

function listUniqueBackups() {
        getAllBackups | sort -u
}

function listBackupsToDelete() {
        ls ${DIR_SNAPSHOT} | grep -v -e "$(echo -n $(listUniqueBackups) |sed "s/ /\\\|/g")"
}

cd ${DIR_SNAPSHOT}
printf Removing listBackupsToDelete >> $FILE_LOG
listBackupsToDelete | while read file_to_delete; do
        echo Removing ${file_to_delete} >> $FILE_LOG
        rm -rf ${file_to_delete} >> $FILE_LOG
done
