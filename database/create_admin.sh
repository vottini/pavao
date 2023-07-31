#!/bin/bash

source common.sh
source settings.sh

LOCALIZATION_DIR=localization
DEFAULT_LANG="en_US"

if [ ! -z ${APPLICATION_LANGUAGE} ]; then
	if [ -e ${LOCALIZATION_DIR}/${APPLICATION_LANGUAGE}.sh ]; then
		echo "Using ${APPLICATION_LANGUAGE} localization"
		CHOSEN_LANG=${APPLICATION_LANGUAGE}
	else
		echo "${APPLICATION_LANGUAGE} is not a supported localization"
	fi
fi

if [ -z $CHOSEN_LANG ]; then
	SYSTEM_LANG=$(echo $LANG | cut --delimiter "." --fields 1)
	if [ -e ${LOCALIZATION_DIR}/${SYSTEM_LANG}.sh ]; then
		read -p "Detected supported system localization '${SYSTEM_LANG}', keep it? (Yes/No) " ANSWER

		UPPER_ANSWER=$(echo $ANSWER | tr '[:lower:]' '[:upper:]')
		if [[ ${UPPER_ANSWER} = "YES" ]]; then
				CHOSEN_LANG=$SYSTEM_LANG
		fi
	fi
fi

if [ -z $CHOSEN_LANG ]; then
	echo "No localization was set. Available options are:"

	for LNG in $(ls -1 ${LOCALIZATION_DIR}); do
	  ABBREV_LNG=$(echo $LNG | cut --delimiter '.' --fields 1)
		source ${LOCALIZATION_DIR}/$LNG
	  echo "${ABBREV_LNG} -> ${LANG_NAME}"
	done

	read -p "Choose one or leave it blank for default (${DEFAULT_LANG}): " CHOSEN_LANG

	while true; do
		if [ -e ${LOCALIZATION_DIR}/${CHOSEN_LANG}.sh ]; then
			break
		fi

		if [ -z $CHOSEN_LANG ]; then
			CHOSEN_LANG=${DEFAULT_LANG}
			break
		fi

		read -p "Invalid option, try again: " CHOSEN_LANG
	done
fi

echo "Admin account creation"
read -p "First name: " FIRST_NAME
read -p "Last name: " LAST_NAME

LOWER_FIRST_NAME=$(echo $FIRST_NAME | tr '[:upper:]' '[:lower:]')
LOWER_LAST_NAME=$(echo $LAST_NAME | tr '[:upper:]' '[:lower:]')
LOGIN_SUGGESTION="${LOWER_FIRST_NAME}.${LOWER_LAST_NAME}"

read -p "Login: " -e -i ${LOGIN_SUGGESTION} ADMIN_LOGIN
read -p "Password: " -s ADMIN_PASSWORD
echo ""

source ${LOCALIZATION_DIR}/${CHOSEN_LANG}.sh
ADMIN_AUTH=$(./create_authentication.py ${ADMIN_LOGIN} ${ADMIN_PASSWORD})

ADMIN_CLASS_CREATION="
INSERT INTO
  pavao.class (name, admin)
  VALUES ('${ADMINISTRATOR_GROUP}', TRUE);
"

SYSTEM_CREATION="
INSERT INTO
  pavao.account (login, first_name, managerial)
  VALUES ('system', '${SYSTEM_USER}', TRUE);
"

SET_LANGUAGE="
INSERT INTO
  pavao.parameters (name, type, value)
  VALUES ('language', 'str', '$CHOSEN_LANG');
"

ADMIN_CREATION="
INSERT INTO
	pavao.account (
		login,
		first_name,
		last_name)

	VALUES (
		'${ADMIN_LOGIN}',
		'${FIRST_NAME}',
		'${LAST_NAME}');
"

ADMIN_ASSIGNMENT="
INSERT INTO
  pavao.assignment (account, cls)

  SELECT 
    acc.id,
    cls.id

  FROM
    pavao.account acc CROSS JOIN
    pavao.class cls

  WHERE
    acc.login = '${ADMIN_LOGIN}' AND
    cls.name = '${ADMINISTRATOR_GROUP}';
"

PGPASSWORD=${DATABASE_PASSWORD}
if [ "#$PGPASSWORD" = "#" ]; then
	read -s -p "Type the password for role '${DB_LOGIN}': " PGPASSWORD
	echo ""
fi

psql -q --dbname $DB --username ${DB_LOGIN} --command "${SYSTEM_CREATION}"
psql -q --dbname $DB --username ${DB_LOGIN} --command "${SET_LANGUAGE}"
psql -q --dbname $DB --username ${DB_LOGIN} --command "${ADMIN_CLASS_CREATION}"
psql -q --dbname $DB --username ${DB_LOGIN} --command "${ADMIN_CREATION}"
psql -q --dbname $DB --username ${DB_LOGIN} --command "${ADMIN_ASSIGNMENT}"
psql -q --dbname $DB --username ${DB_LOGIN} --command "${ADMIN_AUTH}"

