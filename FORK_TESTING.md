# Testing this fork

This is [Sivivatu's fork](https://github.com/Sivivatu/CLIProxyAPI_unraid) of
[OzoneH3/CLIProxyAPI_unraid](https://github.com/OzoneH3/CLIProxyAPI_unraid).
GitHub retains the fork relationship. In the working checkout, `origin` points
to Sivivatu and `upstream` points to OzoneH3, so upstream changes can still be
fetched and reviewed without sending a pull request.

## What changed

The bundled CLIProxyAPI moves from v8.0.2 to v8.0.56, which includes
[upstream's Codex OAuth refresh recovery fix](https://github.com/router-for-me/CLIProxyAPI/issues/6742).
The wrapper, account storage and dashboard stay the same.

An image reference containing `latest@sha256:...` selects the exact digest. It
does not follow subsequent changes to `latest`. This fork uses an explicit
release tag and its verified multi-platform digest for a reproducible trial.
Removing the digest would only change which base image a future build selects;
it would not update the CLIProxyAPI binary inside an already-published wrapper
image or a running container. The wrapper still needs rebuilding.

An already-invalidated refresh token requires a fresh provider login. The image
update cannot restore that token, and successful local smoke tests do not prove
that a live account's refresh problem is resolved.

## Build or load a local test image

On the Unraid host, build from this fork without publishing anything:

```sh
git clone https://github.com/Sivivatu/CLIProxyAPI_unraid.git CLIProxyAPI-unraid-test
cd CLIProxyAPI-unraid-test
docker build -t cliproxyapi-unraid:test-v8.0.56 .
```

Alternatively, load an image archive produced from the same source:

```sh
docker load -i /path/to/cliproxyapi-unraid-test-v8.0.56-amd64.tar.gz
```

An amd64 archive is for x86-64 Unraid hosts. Build from source for another
architecture. The local image tag is `cliproxyapi-unraid:test-v8.0.56`.

## Trial in Unraid

Use Docker -> Add Container and select the existing CLIProxyAPI template. Change
these settings before applying it:

- Name: `CLIProxyAPI-test`.
- Repository: `cliproxyapi-unraid:test-v8.0.56` (the locally built or loaded image).
- Host API port: `18317`; keep the container port at `8317`.
- Host WebUI port: `18318`; keep the container port at `8318`.
- API Public Port: `18317`.
- Host appdata: `/mnt/user/appdata/cliproxyapi-test`; keep the container path at
  `/data`. Use this separate directory rather than the existing installation's
  appdata.
- WebUI Password: choose a password for the test dashboard.

This tests the new backend with fresh storage while keeping the existing
container available. The original template points to OzoneH3's image until its
Repository field is changed as above.

Open `http://UNRAID-IP:18318`, confirm the reported upstream version is v8.0.56,
and connect the affected account through a fresh OAuth login. Point a test
client at `http://UNRAID-IP:18317/v1` using the test dashboard's client key, then
send a small inference request.

Check another request after a container restart and after normal idle use.
Observe a subsequent automatic credential refresh before concluding that the
intermittent authentication issue is fixed. One successful request proves the
new login and routing work, not that future refreshes will succeed. If it fails,
record the backend version, timestamp, HTTP status and provider error code;
keep tokens and complete credential files out of reports.

Use the test installation's own login credentials. Do not copy one OAuth token
set between independently refreshing installations. To roll back the trial,
stop the test container and return the client to the original endpoint.

## Optional publication later

The fork's publish workflow targets `ghcr.io/sivivatu/cliproxyapi-unraid`. A normal
push to `main` runs validation and does not publish an image. Publication only
runs after an explicit workflow dispatch or a matching version-tag push, and
only after the validation job succeeds. A manual dispatch on `main` publishes
the `latest` tag; version-tag runs publish their configured version/SHA tags.

When ready, run **Actions -> Publish GHCR -> Run workflow** on `main`. The first
publication may need package visibility/access configuration before Unraid can
pull it. Verify access before changing a container's Repository to
`ghcr.io/sivivatu/cliproxyapi-unraid:latest`.

The inherited template and `scripts/activate-release.py` still target OzoneH3's
public image. They are not a deployment path for this fork; use the explicit
Repository override described here. No upstream contribution or registry
publication is needed for the local trial.
