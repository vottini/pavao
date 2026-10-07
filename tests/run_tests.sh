#!/bin/bash

coverage run -m pytest -v
coverage report --omit="test_*.py" --show-missing

