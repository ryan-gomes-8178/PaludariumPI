#!/bin/bash
# Cronjob to run every minute
# add using command 'crontab -e' as running PaludariumPI user
# * * * * * ~/PaludariumPI/contrib/watchdog.sh

BASEDIR="$(dirname "$(readlink -nf $0)")"
RUN_AS_USER="$(stat -c "%U" "${BASEDIR}")"
MAXTIME=600 # In seconds
LOGFILE="/home/${RUN_AS_USER}/PaludariumPI/log/paludariumpi.log"

if [ ! -f "${LOGFILE}" ]; then
  echo "PaludariumPI logfile does not exists at location: ${LOGFILE}"
  exit 0
fi

PID="$(ps fax | grep paludariumPI.py | grep -v grep | awk {'print $1'})"
AGE="$(("$(date +%s)" - "$(date +%s -r "${LOGFILE}")"))"

if [ $AGE -gt $MAXTIME ]; then
  echo "Logfile is not updated for ${MAXTIME} seconds. Restarting..."
  kill "${PID}"
fi
