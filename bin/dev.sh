#!/bin/bash
PLATFORM="${PLATFORM:-amd64}"
echo "running dev container for platform ${PLATFORM}"
echo "set PLATFORM=arm64 if running on an ARM machine (e.g. recent Mac) and want better performance."
SCRIPT_DIR=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )
cd ${SCRIPT_DIR}/..
docker build -f docker/dev/Dockerfile -t yaada/dev:latest --build-arg PLATFORM=${PLATFORM} docker/dev
docker run --rm -it --platform=linux/${PLATFORM} --name=yaada-dev --privileged=true -v $(pwd):/workspace -v /var/run/docker.sock:/var/run/docker.sock  ${DEV_PORTS} yaada/dev:latest $@
