#!/usr/bin/env bash

source settings.sh
source common.sh
check_user

#-------------------------------

get_password() {
	read -s -p "Type a password for role ${DB_LOGIN}: " FIRST_PASSWORD; echo ""
	read -s -p "Re-type the password: " SECOND_PASSWORD; echo ""
}

ask_password() {
	get_password
	
	while [ ! "${FIRST_PASSWORD}" = "${SECOND_PASSWORD}" ]; do
		echo "Error: Passwords don't match!"
		get_password
	done

	DATABASE_PASSWORD=${FIRST_PASSWORD}
}

if [ "#${DATABASE_PASSWORD}" = "#" ]; then
	ask_password
fi

#-------------------------------

ROLE_CREATION="
CREATE ROLE ${DB_LOGIN} WITH LOGIN;
ALTER ROLE ${DB_LOGIN} WITH REPLICATION CREATEDB;
ALTER ROLE ${DB_LOGIN} WITH ENCRYPTED PASSWORD '${DATABASE_PASSWORD}';
"

ROLE_CHECK="
SELECT
	CASE COUNT(*)
		WHEN 0 THEN 'Error creating Role'
		ELSE 'Role created!'
	END
FROM pg_catalog.pg_user
WHERE usename ILIKE '${DB_LOGIN}';
"

echo -n "Creating role '${DB_LOGIN}'..."
psql -q -U ${PG_USER} --command="$ROLE_CREATION"
psql -U ${PG_USER} --command="$ROLE_CHECK" -t

