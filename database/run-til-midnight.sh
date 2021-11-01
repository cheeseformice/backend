#!/bin/bash

if [ "$(id -u)" = "0" ]; then
	mkdir /home/mysql
	chown -R mysql /home/mysql
	echo "Switching to dedicated user 'mysql'"
	exec gosu mysql "$BASH_SOURCE" "$@"
fi

while true
do
	# Run until midnight
	midnight=$(date -d 'tomorrow 00:05:00' +%s)
	now=$(date +%s)
	seconds=$(($midnight - $now))
	timeout --preserve-status ${seconds}s "$@"

	# Backup data
	/backup.sh
done
