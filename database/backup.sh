#!/bin/bash

filename="backup_$(date +%F-%H-%M-%S).tar.gz"
echo "Start backup (compressing into ./$filename)"
start=$(date +%s)

tar -czvf ./$filename /var/lib/mysql/${MYSQL_DATABASE}/{\
	auth*,\
	member_changelog*,\
	player_changelog*,\
	player_privacy*,\
	roles*,\
	sanctions*,\
	tribe_changelog*,\
	tribe_privacy*,\
	tribe_stats_changelog*\
}
compressed=$(date +%s)
echo "Compression took $(($compressed - $start)) seconds"

ftp -n ${BACKUP_HOST} <<ENDSC
quote USER ${BACKUP_USER}
quote PASS ${BACKUP_PASS}
binary
put ./$filename
quit
ENDSC
transferred=$(date +%s)
echo "Transfer took $(($transferred - $compressed)) seconds"

rm ./$filename
end=$(date +%s)
echo "Cleanup took $(($end - $transferred)) seconds"
echo "Total process took $(($end - $start)) seconds"
