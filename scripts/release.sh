#!/usr/bin/env bash
# Build, test and publish a versioned Docker image of Release Hub to the private registry.
#   ./scripts/release.sh            -> uses the version from pyproject.toml
# Releases are immutable: an existing version is never overwritten.
set -euo pipefail
command -v docker >/dev/null || export PATH="$PATH:/Applications/Docker.app/Contents/Resources/bin"
cd "$(dirname "$0")/.."

REGISTRY="${REGISTRY:-localhost:5001}"
IMAGE="$REGISTRY/releasehub"
VERSION=$(sed -n 's/^version = "\(.*\)"/\1/p' pyproject.toml)
REVISION=$(git rev-parse --short HEAD 2>/dev/null || echo "uncommitted")

echo "== Release Hub $VERSION (git $REVISION) -> $IMAGE =="

# 1. Immutability: refuse to overwrite a version that is already published
if curl -sf -o /dev/null "http://$REGISTRY/v2/releasehub/manifests/$VERSION" \
     -H "Accept: application/vnd.oci.image.index.v1+json,application/vnd.oci.image.manifest.v1+json,application/vnd.docker.distribution.manifest.v2+json"; then
  echo "ERROR: $VERSION is already published. Bump the version in pyproject.toml." >&2
  exit 1
fi

# 2. Quality gate: lint + tests (the 'test' stage fails the build if anything is wrong)
docker build --target test -q -t releasehub:test . >/dev/null
echo "== tests passed =="

# 3. Build the runtime image with traceability labels (which version, which commit)
docker build --target runtime -q \
  --label org.opencontainers.image.version="$VERSION" \
  --label org.opencontainers.image.revision="$REVISION" \
  -t "$IMAGE:$VERSION" -t "$IMAGE:latest" . >/dev/null

# 4. Publish: the immutable version tag, plus the moving 'latest' tag
docker push -q "$IMAGE:$VERSION" >/dev/null
docker push -q "$IMAGE:latest" >/dev/null

DIGEST=$(curl -sI "http://$REGISTRY/v2/releasehub/manifests/$VERSION" \
  -H "Accept: application/vnd.oci.image.index.v1+json,application/vnd.oci.image.manifest.v1+json,application/vnd.docker.distribution.manifest.v2+json" \
  | awk -F': ' 'tolower($1)=="docker-content-digest"{print $2}' | tr -d '\r')
echo "== published =="
echo "  tag:    $IMAGE:$VERSION"
echo "  digest: $IMAGE@$DIGEST"
