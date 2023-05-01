$workspace = (Get-Location).Path
docker build -f docker/dev/Dockerfile -t yaada/dev:latest docker/dev
docker run --rm -it --name=yaada-dev --privileged=true -v "$workspace`:/workspace" -v "/var/run/docker.sock:/var/run/docker.sock" $env:DEV_PORTS yaada/dev:latest $args
