#!/bin/sh

# Abort on any error
set -e

# Wait for databases to be available
/wait-for-it.sh "$A801_IP:3306" --timeout=60
/wait-for-it.sh "$DB_IP:3306" --timeout=60

# Execute the command
env > /etc/environment
exec $@
