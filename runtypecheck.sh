#!/usr/bin/env bash

set -eo pipefail


echo "Running Mypy" >&2
mypy --strict --ignore-missing-imports --warn-unused-configs --warn-return-any searchbox
echo ""

echo "Running Pyright" >&2
pyright --createstub validators
pyright --lib searchbox
echo ""
