#!/bin/bash -e

docker run \
	--mount type=bind,source=$(pwd)/artifacts.json,target=/app/artifacts.json \
	-v $(pwd)/db:/app/db \
	artifact_listener:latest
