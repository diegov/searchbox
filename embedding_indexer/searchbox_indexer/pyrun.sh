#!/usr/bin/env bash

set -eEo pipefail

if [ ! -d .venv ]; then
    rm -rf .venv
    python3 -m venv .venv
fi

source .venv/bin/activate

"$@"
