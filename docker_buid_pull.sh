#!/bin/sh

docker build -t registry.nutsolution.de/opendox:demo .
docker push registry.nutsolution.de/opendox:demo