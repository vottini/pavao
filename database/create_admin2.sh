#!/bin/bash

shopt -s expand_aliases
alias read="read -e"

LOCALIZATION_DIR=localization
DEFAULT_LANG="en_US"

while [[ $# -gt 0 ]]; do
  case $1 in
    -c|--config)
      SETTINGS_FILE="$2"
      if [ -e ${SETTINGS_FILE} ]; then
        source ${SETTINGS_FILE}
		LOADED=$?
      fi

      if [ ! -e ${SETTINGS_FILE} ] || [ ! 0 -eq $LOADED ]; then
        echo "[Warn] Unable to load file '$SETTINGS_FILE', skipping"
      fi

      shift
      shift
      ;;

    -d|--database)
      PAVAO_DATABASE="$2"
      shift
      shift
      ;;

    -r|--db-role)
      PAVAO_DB_ROLE="$2"
      shift
      shift
      ;;

    -w|--db-password)
      PAVAO_DB_PASSWORD="$2"
      shift
      shift
      ;;

    -n|--first-name)
      PAVAO_ADMIN_FIRST_NAME="$2"
      shift
      shift
      ;;

    -s|--last-name)
      PAVAO_ADMIN_LAST_NAME="$2"
      shift
      shift
      ;;

    -l|--login)
      PAVAO_ADMIN_LOGIN="$2"
      shift
      shift
      ;;

    -p|--password)
      PAVAO_ADMIN_PASSWORD="$2"
      shift
      shift
      ;;

    *)
      echo "Unknown option $1"
      exit 1
      ;;
  esac
done

if [ -z ${PAVAO_DATABASE} ]; then
  echo "Database not specified!"
  echo "It can be specified either through the variable 'PAVAO_DATABASE'"
  echo "or through the command line flag '--database <database>'"
  echo "Aborting..."
  exit 1
fi

if [ -z ${PAVAO_DB_ROLE} ]; then
  echo "Database role not specified!"
  echo "It can be specified either through the variable 'PAVAO_DB_ROLE'"
  echo "or through the command line flag '--db-role <role>'"
  echo "Aborting..."
  exit 1
fi

echo "Using configuration:"
echo "Database = ${PAVAO_DATABASE}"
echo "Role = ${PAVAO_DB_ROLE}"

PGPASSWORD=${PAVAO_DB_PASSWORD}
if [ "#$PGPASSWORD" = "#" ]; then
	read -s -p "Type the password for database role '${PAVAO_DB_ROLE}': " PGPASSWORD
	echo ""
fi

QUERY_LANGUAGE="

  SELECT value
    FROM pavao.parameters
    WHERE name = 'language'

"

PAVAO_LANG=$(psql -qtA \
  --dbname ${PAVAO_DATABASE} \
  --username ${PAVAO_DB_ROLE}\
  --command "${QUERY_LANGUAGE}")

if [ 0 -ne $? ]; then
  echo "Error querying configured language."
  echo "Either the database credentials are wrong or pavao has not yet created the table structure."
  echo "Make sure the role and its password are valid and run this script only after pavao has succesfuly ran once."
  echo "Aborting..."
  exit 1
fi

if [ ! -e "${LOCALIZATION_DIR}/${PAVAO_LANG}.sh" ]; then
  echo "There's no support for localization '${PAVAO_LANG}' which is what pavao is configured to use."
  echo "The available localization options are:"

  for LNG in $(ls -1 ${LOCALIZATION_DIR}); do
    ABBREV_LNG=$(echo $LNG | cut --delimiter '.' --fields 1)
    source ${LOCALIZATION_DIR}/$LNG
    echo "${ABBREV_LNG} -> ${LANG_NAME}"
  done

  read -p "Choose one or leave it blank for default (${DEFAULT_LANG}): " PAVAO_LANG
  while true; do
    if [ -e ${LOCALIZATION_DIR}/${PAVAO_LANG}.sh ]; then
      break
    fi

    if [ -z $PAVAO_LANG ]; then
      PAVAO_LANG=${DEFAULT_LANG}
      break
    fi

    read -p "Invalid option, try again: " PAVAO_LANG
  done
fi

source ${LOCALIZATION_DIR}/${PAVAO_LANG}.sh
echo "Localization = ${PAVAO_LANG}"

echo "Admin account creation"
while [ -z ${PAVAO_ADMIN_FIRST_NAME} ]; do
  read -p "First name: " PAVAO_ADMIN_FIRST_NAME
done

if [ -z ${PAVAO_ADMIN_LAST_NAME} ]; then
  read -p "Last name (can be empty): " PAVAO_ADMIN_LAST_NAME
fi

if [ -z ${PAVAO_ADMIN_LOGIN} ]; then
  LOWER_FIRST_NAME=$(echo $PAVAO_ADMIN_FIRST_NAME | tr '[:upper:]' '[:lower:]')
  PAVAO_ADMIN_LOGIN=$LOWER_FIRST_NAME

  if [ ! -z ${PAVAO_ADMIN_LAST_NAME} ]; then
    LOWER_LAST_NAME=$(echo $PAVAO_ADMIN_LAST_NAME | tr '[:upper:]' '[:lower:]')
    PAVAO_ADMIN_LOGIN="${LOWER_FIRST_NAME}.${LOWER_LAST_NAME}"
  fi

  while true; do
    read -p "Login: " -i "${PAVAO_ADMIN_LOGIN}" PAVAO_ADMIN_LOGIN

    while [ -z ${PAVAO_ADMIN_LOGIN} ]; do
      read -p "Login: " -i "${PAVAO_ADMIN_LOGIN}" PAVAO_ADMIN_LOGIN
    done

    PAVAO_ADMIN_LOGIN=$(echo $PAVAO_ADMIN_LOGIN | tr '[:upper:]' '[:lower:]')

    QUERY_LOGIN_USAGE="

      SELECT COUNT(*)
        FROM pavao.account
        WHERE login  = '${PAVAO_ADMIN_LOGIN}';

    "

    LOGIN_USAGE=$(psql -qtA \
      --dbname ${PAVAO_DATABASE} \
      --username ${PAVAO_DB_ROLE}\
      --command "${QUERY_LOGIN_USAGE}")

    if [ "0" = ${LOGIN_USAGE} ]; then
      break
    fi

    echo "This login is already in use, choose another."
  done
fi


if [ -z ${PAVAO_ADMIN_PASSWORD} ]; then
  read -s -p "Password: " PASSWORD1
  read -s -p "Confirm password: " PASSWORD2

  while [ ! "${PASSWORD1}" = "${PASSWORD2}" ]; do
    echo "Passwords don't match! Try again:"
    read -s -p "Password: " PASSWORD1
    read -s -p "Confirm password: " PASSWORD2
  done

  PAVAO_ADMIN_PASSWORD=${PASSWORD1}
fi

#------------------------------------------------------------------------------

ADMIN_ROLE="

  INSERT INTO
    pavao.\"role\" (name, admin)
    VALUES ('${ADMINISTRATOR_GROUP}', TRUE)
    ON CONFLICT DO NOTHING;

"

LAST_NAME_SANED="NULL"
if [ ! -z ${PAVAO_ADMIN_LAST_NAME} ]; then
  LAST_NAME_SANED="'${PAVAO_ADMIN_LAST_NAME}'"
fi

ADMIN_USER_CREATION="

  INSERT INTO
    pavao.account (
      login,
      first_name,
      last_name)

    VALUES (
      '${PAVAO_ADMIN_LOGIN}',
      '${PAVAO_ADMIN_FIRST_NAME}',
      ${LAST_NAME_SANED});

"

ADMIN_USER_AUTH=$(./create_authentication.py \
  ${PAVAO_ADMIN_LOGIN} \
  ${PAVAO_ADMIN_PASSWORD})

ADMIN_USER_ASSIGNMENT="

  INSERT INTO
    pavao.assignment (account, \"role\")

    SELECT 
      acc.id,
      rl.id

    FROM
      pavao.account acc CROSS JOIN
      pavao.\"role\" rl

    WHERE
      acc.login = '${PAVAO_ADMIN_LOGIN}' AND
      rl.name = '${ADMINISTRATOR_GROUP}';
"

psql -q --dbname ${PAVAO_DATABASE} --username ${PAVAO_DB_ROLE} --command "${ADMIN_ROLE}"
psql -q --dbname ${PAVAO_DATABASE} --username ${PAVAO_DB_ROLE} --command "${ADMIN_USER_CREATION}"
psql -q --dbname ${PAVAO_DATABASE} --username ${PAVAO_DB_ROLE} --command "${ADMIN_USER_AUTH}"
psql -q --dbname ${PAVAO_DATABASE} --username ${PAVAO_DB_ROLE} --command "${ADMIN_USER_ASSIGNMENT}"

