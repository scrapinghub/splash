#!/bin/bash -e

# Pushes the requested image to a the requested ecr repository.
# Should be executed from project root dir

export IMAGE=$1
export TAG=$2
export REPOSITORY=$3
export REGION=${4:-"us-east-1"}

if [ -z "$IMAGE" ]; then
  echo "Image is required"
  exit 1
fi

if [ -z "$TAG" ]; then
  echo "Tag is required"
  exit 1
fi

if [ -z "$REPOSITORY" ]; then
  echo "Repository is required"
  exit 1
fi

$(aws ecr get-login --no-include-email --region ${REGION})
docker tag ${IMAGE}:${TAG} ${REPOSITORY}:${TAG}
docker push ${REPOSITORY}:${TAG}

echo "-------------------------"
echo "${IMAGE}:${TAG} is pushed to ${REPOSITORY}:${TAG}"