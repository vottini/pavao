#!/bin/bash

source common.sh

function get-owner() {
	echo $(stat -c "%U" $1)
}

function allow-user-access() {
    setfacl -m $1:X $2
}

OWNER=$(get-owner .)
allow-user-access ${PG_USER} .
PARENT_OWNER=$(get-owner ..)
cd ..

while [ $OWNER = $PARENT_OWNER ]; do
  echo "Allowing '${PG_USER}' to access $(pwd)"
  allow-user-access ${PG_USER} .
  PARENT_OWNER=$(get-owner ..)
  cd ..
done

