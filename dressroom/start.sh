#!/bin/sh

# Abort on any error
set -e

# Wait for redis to be available
if [[ $INFRA_ADDR == *":"* ]]; then
	/wait-for-it.sh "$INFRA_ADDR" --timeout=60
fi

# Execute the command
exec $@