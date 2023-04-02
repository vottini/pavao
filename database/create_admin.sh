#!/bin/bash

source common.sh

LOCALIZATION_DIR=localization
SYSTEM_LANG=$(echo $LANG | cut --delimiter "." --fields 1)
if [ -e ${LOCALIZATION_DIR}/${SYSTEM_LANG}.sh ]; then
  echo "Detected support for language '${SYSTEM_LANG}', proceed?"
fi

