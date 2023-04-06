#!/bin/bash

SETTINGS_FILE=settings.sh
if [ ! -e ${SETTINGS_FILE} ]; then
	echo "File '${SETTINGS_FILE}' doesn't exist, aborting..."
	exit 0
fi

source ${SETTINGS_FILE}
if [ -z $APPLICATION ]; then
	echo "Variable APPLICATION needs to be exported on file ${SETTINGS_FILE}"
	exit 0
fi

export PG_USER=postgres
export DB_LOGIN=${APPLICATION}_admin
export DB=${APPLICATION}

check_user() {
	if [ ! "$USER" = "${PG_USER}" ]; then
		echo "This command needs to be run as '${PG_USER}'"
		exit 0
	fi
}

