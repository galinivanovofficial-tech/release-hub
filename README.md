# Release Hub

![CI/CD](https://github.com/galinivanovofficial-tech/release-hub/actions/workflows/ci.yml/badge.svg)

A small **software delivery platform**: version, test, package, store and ship releases to customers,
securely. Built to learn how artifact repositories and release pipelines work.

```
code ──► CI: lint + tests ──► build (wheel + Docker image) ──► registry (versioned, immutable)
                                                                   │
customer ──[token]──► REST API ── entitlement check ── download + SHA-256 checksum + audit log
```

## What's inside
| Part | What it does |
|---|---|
| `releasehub` package | Semantic versioning (`Version` class, `bump`, numeric ordering), CLI: `releasehub bump 1.4.2 minor` |
| Artifact API (`releasehub.server`) | FastAPI + PostgreSQL. Immutable versioned releases, customer tokens stored only as SHA-256 hashes, per-product entitlements (401 vs 403), checksums, download audit log, path-traversal-safe uploads streamed in chunks |
| Private registry | `registry:2` in Docker Compose. `scripts/release.sh` publishes versioned images and refuses to overwrite a version |
| CI/CD | GitHub Actions: lint + tests on every push / PR; a `v*` tag publishes the image to GitHub Container Registry |

## Run locally
```bash
cp .env.example .env          # set ADMIN_TOKEN and POSTGRES_PASSWORD
docker compose up -d          # API on :8080 (docs at /docs), Postgres, registry on :5001
./scripts/check.sh            # lint + 33 tests + wheel build, all inside Docker
./scripts/release.sh          # publish the current version to the local registry
```

## Release a new version
```bash
# 1. bump version in pyproject.toml, commit
git tag v0.3.0 && git push origin v0.3.0      # CI tests, then publishes ghcr.io/.../releasehub:0.3.0
```

## Design decisions
- **Immutable releases**: enforced in code and with a UNIQUE constraint; the release script and CI refuse to republish a version.
- **Tags vs digests**: `latest` moves, a digest never changes. Deploy by version or digest, never `latest`.
- **Build once**: the same image is promoted, never rebuilt per environment.
- **Secrets**: only via environment variables / CI secret store; `.env` is git-ignored.
- **Same checks everywhere**: tests run inside the Docker build, so local and CI run the same command.
