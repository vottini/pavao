#!/usr/bin/env bash

source common.sh
check_user

#-------------------------------

echo "Removing role '${DB_LOGIN}'"
ROLE_DELETION="DROP ROLE ${DB_LOGIN};"
psql -q -U ${PG_USER} --command="${ROLE_DELETION}"

