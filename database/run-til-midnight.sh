#!/bin/bash

if [ "$(id -u)" = "0" ]; then
	echo "Switching to dedicated user 'mysql'"
	exec gosu mysql "$BASH_SOURCE" "$@"
fi

while true
do
	echo "start"
	# Run until midnight
	midnight=$(date -d 'tomorrow 00:05:00' +%s)
	now=$(date +%s)
	seconds=$(($midnight - $now))
	timeout --preserve-status ${seconds}s "$@"

	# Backup data
	echo "$@ $(id)"
	sleep infinity
	#/backup.sh
done
