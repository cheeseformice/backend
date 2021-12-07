#!/bin/bash

echo "Transferring"

start=$(date +%s)
sshpass -p ${BACKUP_PASS} scp -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null ~/$1 ${BACKUP_USER}@${BACKUP_HOST}:$1
transferred=$(date +%s)
echo "Transfer took $(($transferred - $start)) seconds"

rm ~/$1
end=$(date +%s)
echo "Cleanup took $(($end - $transferred)) seconds"