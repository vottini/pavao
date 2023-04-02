#!/usr/bin/env bash

source common.sh
check_user

#-------------------------------

echo "Removing database '$DB'"
DB_DELETION="DROP DATABASE $DB;"
psql -q -U ${DB_LOGIN} --dbname postgres --command="${DB_DELETION}"

