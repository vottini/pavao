#!/bin/bash

cd "$(dirname "$0")/.."
coverage run -m pytest tests/ -v
coverage report --show-missing

