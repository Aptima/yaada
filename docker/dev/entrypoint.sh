#!/bin/bash
SHELL=/bin/bash
export SHELL

if [[ $# -eq 0 ]]
then
    pipenv shell
else
    pipenv run $@
fi
