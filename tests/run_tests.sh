#!/bin/bash

export DB_NAME="database_name"
export DB_ROLE="database_role"
export BAD_LONGITUDE="John Doe"

coverage run -m pytest -v
coverage report --show-missing

