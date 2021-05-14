#!/bin/bash

cat > /etc/nginx/conf.d/cloudflare-allow.conf <<- EOF
# ipv4
$(curl --silent https://www.cloudflare.com/ips-v4 | awk '{print "allow", $1, ";"}')

# ipv6
$(curl --silent https://www.cloudflare.com/ips-v6 | awk '{print "allow", $1, ";"}')
EOF
