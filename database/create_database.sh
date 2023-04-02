#!/usr/bin/env bash

source common.sh
check_user

#-------------------------------

echo "Creating database '$DB'..."
CMD="CREATE DATABASE $DB WITH OWNER = ${DB_LOGIN} TEMPLATE = template0"
psql -q -U ${PG_USER} --command="$CMD"

#--------------------------------------------------

echo "Enabling extension 'unaccent' on it"
UNACCENT="CREATE EXTENSION unaccent;"
psql -q -U ${PG_USER} -d $DB --command="$UNACCENT"

#--------------------------------------------------

PGPASSWORD=${DATABASE_PASSWORD}
echo "Creating pavao structures"
if [ "#$PGPASSWORD" = "#" ]; then
	echo -n "Type the password for role '${DB_LOGIN}': "
	read -s PGPASSWORD
fi

TABLES_DIR=tables
for ARQ in $(ls ${TABLES_DIR} | sort); do
	echo "Executing file $ARQ..."
	psql -q --dbname $DB --username ${DB_LOGIN} --file=${TABLES_DIR}/$ARQ
done


