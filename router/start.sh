#!/bin/sh

# Abort on any error
set -e

# Wait for redis to be available
/wait-for-it.sh "$INFRA_HOST:$INFRA_PORT" --timeout=60

# Execute the command
exec $@