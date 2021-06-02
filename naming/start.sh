#!/bin/sh

# Abort on any error
set -e

# Wait for database and redis to be available
if [[ $INFRA_ADDR == *":"* ]]; then
	/wait-for-it.sh "$INFRA_ADDR" --timeout=60
fi
/wait-for-it.sh "$DB_IP:3306" --timeout=60

# Execute the command
exec $@