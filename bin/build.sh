#!/bin/bash -e

# Builds the docker with specified code version.
# Should be executed from project root dir

export IMAGE=${1}
export TAG=${2}

if [ -z "$IMAGE" ]; then
  echo "Image is required"
  exit 1
fi

if [ -z "$TAG" ]; then
  echo "Tag is required"
  exit 1
fi

export TS=$(date +%s)

mkdir -p tmp

git archive --prefix=mrld-crawler-${VERSION}/ -o tmp/mrld-crawler-${VERSION}.tar.gz HEAD

docker build --build-arg VERSION=${VERSION} --label version=${VERSION} --label build-time=${TS} -t ${IMAGE}:${TAG} .

echo "-------------------------"
echo "${IMAGE}:${TAG} is ready"