#!/bin/sh

# Abort on any error
set -e

# Wait for database and redis to be available
/wait-for-it.sh "$INFRA_HOST:$INFRA_PORT" --timeout=60
/wait-for-it.sh "$DB_IP:3306" --timeout=60

# Execute the command
exec $@