#!/bin/bash

while true
do
	# Run until midnight
	midnight=$(date -d 'tomorrow 00:05:00' +%s)
	now=$(date +%s)
	seconds=$(($midnight - $now))
	timeout --preserve-status ${seconds}s $@

	# Backup data
	/backup.sh
done
