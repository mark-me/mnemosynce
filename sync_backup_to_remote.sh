#!/bin/bash

NAME_SNAPSHOT=$1
DIR_LOCAL=$2/$1
DIR_REMOTE=$3
FILE_LOG=${NAME_SNAPSHOT}_sync_remote.log

printf "Log of step 3: Synching backups - " + $NAME_SNAPSHOT + ' - ' > $FILE_LOG
date >> $FILE_LOG

rsync -azhtH --numeric-ids --delete --log-file=$FILE_LOG \
  -e "ssh -i /root/.ssh/id_ed25519_backup" ${DIR_LOCAL} ${DIR_REMOTE}