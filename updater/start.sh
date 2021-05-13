#!/bin/sh

# Abort on any error
set -e

# Wait for databases to be available
/wait-for-it.sh "$A801_IP:3306"
/wait-for-it.sh "$DB_IP:3306"

# Execute the command
exec $@
