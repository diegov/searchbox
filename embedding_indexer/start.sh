#!/usr/bin/env bash

set -eEo pipefail

pushd searchbox_indexer
podman build -t localhost/searchbox_indexer:latest .
popd

podman play kube --down pod.yaml || true

postgres_volume_name=searchbox_indexer_postgres_data

# Podman 4 supports `volume create --ignore` which skips creation if the volume already exists
if ! podman volume exists "$postgres_volume_name"; then
    podman volume create "$postgres_volume_name"
fi

podman play kube pod.yaml
