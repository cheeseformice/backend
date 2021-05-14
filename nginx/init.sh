#!/bin/bash

# grab cloudflare ips
/update-cloudflare.sh
# start cron in the background
cron
