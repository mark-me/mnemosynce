#!/bin/bash

NAME_SNAPSHOT=$1;
DIR_BACKUP=$2;
DIR_SOURCE=$3;


function create_backup(){
    FILE_EXCLUDES=excludes.lst;
    TODAY=$(date +%Y-%m-%d)
    DIR_SNAPSHOT=$DIR_BACKUP/$NAME_SNAPSHOT;
    DIR_LASTDAY=${DIR_SNAPSHOT}/$(ls ${DIR_SNAPSHOT} | tail -n 1)
    DIR_TODAY=${DIR_SNAPSHOT}/${TODAY}
    FILE_LOG=${NAME_SNAPSHOT}_backup.log

    printf "Log of step 1: Backup - " + $NAME_SNAPSHOT + ' - ' > $FILE_LOG
    date >> $FILE_LOG

    # mkdir -p $DIR_SNAPSHOT  >> $FILE_LOG   # Check source directory existence

    # Check source directory existence
    # if [[ $DIR_SOURCE == *"@"* ]] && [[ $DIR_SOURCE == *":"* ]];
    # then
    #     readarray -d : -t host_dir <<<"$DIR_SOURCE"
    #     if ssh host_dir[0] '[! -d host_dir[1] ]';
    #        echo $TODAY `date +%H:%M:%S` : Source directory $DIR_SOURCE directory does not exist >> $FILE_LOG 2>&1
    #        exit 1
    #     fi
    # elif [ ! -d "$DIR_SOURCE" ];
    # then
    #     echo $TODAY `date +%H:%M:%S` : Source directory $DIR_SOURCE directory does not exist >> $FILE_LOG 2>&1
    #     exit 1
    # fi

    if [[ ! -e ${DIR_TODAY} && ${DIR_LASTDAY} == ${DIR_SNAPSHOT}/ ]];
    then
        echo $TODAY `date +%H:%M:%S` : Create backup directory $TODAY >> $FILE_LOG ;
        mkdir -p ${DIR_TODAY} >> $FILE_LOG

    elif [[ ! -e ${DIR_TODAY} ]];
    then
        echo $TODAY `date +%H:%M:%S` : Move last day\'s directory $DIR_LASTDAY to $TODAY >> $FILE_LOG
        mv $DIR_LASTDAY $DIR_TODAY  >> $FILE_LOG;
        echo $TODAY `date +%H:%M:%S` : Copy all of $TODAY directory to $DIR_LASTDAY >> $FILE_LOG
        cp -alp $DIR_TODAY $DIR_LASTDAY  >> $FILE_LOG
    else
        echo $TODAY `date +%H:%M:%S` : Back-up for $TODAY already exists, exiting >> $FILE_LOG 2>&1 ;
    fi

    echo $TODAY `date +%H:%M:%S` : Starting backup for $TODAY >> $FILE_LOG 2>&1 ;
    echo "Running rsync from '$DIR_SOURCE' to '$DIR_TODAY'" >> $FILE_LOG
    rsync \
        -az --delete --delete-excluded \
        --mkpath \
        --log-file="$FILE_LOG" \
        --numeric-ids \
        --exclude-from="$FILE_EXCLUDES" \
        "$DIR_SOURCE"/ "$DIR_TODAY"/

#    if [ "$?" -eq "0" ]
#    then
#        rm -rf rm /home/pi/queue/*
#        echo $TODAY `date +%H:%M:%S` : Finished backup $TODAY >> $FILE_LOG 2>&1
#        touch $DIR_TODAY ;
#    else
#        rm -Rf $DIR_TODAY
#        echo $TODAY `date +%H:%M:%S` : Error for backup $TODAY >> $FILE_LOG 2>&1
#        exit 2
#    fi

}

create_backup
