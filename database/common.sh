
source settings.sh

export PG_USER=postgres
export DB_LOGIN=${APPLICATION}_admin
export DB=${APPLICATION}

check_user() {
	if [ ! "$USER" = "${PG_USER}" ]; then
		echo "This command needs to be run as '${PG_USER}'"
		exit 0
	fi
}

