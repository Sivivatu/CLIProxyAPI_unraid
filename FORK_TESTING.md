# Fork releases and isolated testing

This is [Sivivatu's fork](https://github.com/Sivivatu/CLIProxyAPI_unraid) of
[OzoneH3/CLIProxyAPI_unraid](https://github.com/OzoneH3/CLIProxyAPI_unraid).
The `main` branch publishes the production image
`ghcr.io/sivivatu/cliproxyapi-unraid`; the source project is
[router-for-me/CLIProxyAPI](https://github.com/router-for-me/CLIProxyAPI).

## Daily upstream release process

The **Sync upstream and publish GHCR** workflow checks the latest stable
CLIProxyAPI release every day at 05:23 UTC. It can also be started manually from
GitHub Actions on `main`. It accepts stable `vN.N.N` releases, retrieves the
matching `eceasy/cli-proxy-api` image, and verifies that its manifest contains
Linux amd64 and arm64 before changing the pin. The selected version and immutable
digest are recorded together in `Dockerfile` and `upstream-release.json`.

The workflow commits a changed pin to `main`, then runs the reusable build and
smoke checks on native amd64 and arm64 runners at that exact commit. If checks
fail, the workflow does not publish or move `latest`; a later daily run retries.
After checks pass, one multi-platform image build receives all of these tags:

- the upstream version without `v`, such as `8.0.61`;
- the major/minor tag, such as `8.0`;
- the major tag, such as `8`;
- the short source commit tag, such as `sha-abcdef0`;
- `latest`.

The workflow then creates or updates the GitHub release with the `v` prefix, such
as `v8.0.61`. Later runs compare the release and image tags and retry if the
publication was incomplete. Version tags and `latest` are built from the same
source and image, so `latest` tracks the most recently tested upstream release.
Creating a release tag manually does not publish an image.

Build checks cover both CPU architectures, Go tests, template validation,
container startup, wrapper login, API authentication and fresh/legacy appdata
migration. They do not perform real provider consent or a live inference request;
verify those in an isolated Unraid trial before switching the primary container.

## Test on Unraid

The fork's GHCR image is public. To trial it without replacing the existing
container, use **Docker → Add Container** and set:

- Name: `CLIProxyAPI-test`.
- Repository: `ghcr.io/sivivatu/cliproxyapi-unraid:latest`.
- Host API port: `18317`; container port: `8317`.
- Host WebUI port: `18318`; container port: `8318`.
- API Public Port: `18317`.
- Host appdata: `/mnt/user/appdata/cliproxyapi-test`; container path: `/data`.
- WebUI Password: a unique password for the test dashboard.

Use a separate appdata directory. Do not run two containers against the same
provider credentials or configuration. Open `http://UNRAID-IP:18318`, confirm
the upstream version shown on Overview, connect a provider, then send a small
request to `http://UNRAID-IP:18317/v1` with the test dashboard's client key.
Check again after restart and after normal idle time. One successful request
does not establish future automatic credential refresh or all provider flows.

To return to the original setup, stop the test container and point clients back
to the primary endpoint. Keep the separate test appdata until you have decided
whether to retain or remove the test installation.

## Local development

Build and test without publishing:

```sh
go mod download
go vet ./...
go test -race ./...
go build ./...
python3 -m unittest discover -s tests -v
python3 scripts/validate-template.py
node --check web/static/app.js
docker build -t cliproxyapi-unraid:local .
python3 scripts/smoke.py cliproxyapi-unraid:local
python3 scripts/smoke.py cliproxyapi-unraid:local --legacy
```

The release pin updater can be run locally to verify the latest source metadata:

```sh
python3 scripts/sync-upstream.py
git diff -- Dockerfile upstream-release.json
```

It may update those files; review the pin and digest before committing local
changes. The GH Actions workflow is responsible for production publication.
