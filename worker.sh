#!/usr/bin/env bash

# Script location directory:
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

export PYTHONPATH=$DIR
export FLASK_APP=orcid_hub
export LANG=en_US.UTF-8

# Add $RANDOM to make the neame unique:
exec flask rq worker -n ORCIDHUB.$RANDOM $@
