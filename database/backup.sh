#!/bin/bash

filename="backup_$(date +%F-%H-%M-%S).tar.gz"
echo "Start backup (compressing into ~/$filename)"
start=$(date +%s)

tar -czvf ~/$filename /var/lib/mysql/${MYSQL_DATABASE}/{auth*,member_changelog*,player_changelog*,player_privacy*,roles*,sanctions*,tribe_changelog*,tribe_privacy*,tribe_stats_changelog*,disqualified*,last_log*}
compressed=$(date +%s)
echo "Compression took $(($compressed - $start)) seconds"

/transfer.sh "$filename" &
