#!/usr/bin/env python3
"""Pin the latest stable CLIProxy release after validating its public image index."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import urllib.request

REPOSITORY = 'router-for-me/CLIProxyAPI'
IMAGE = 'eceasy/cli-proxy-api'
VERSION = re.compile(r'^v(\d+)\.(\d+)\.(\d+)$')
PIN = re.compile(r'^ARG UPSTREAM_IMAGE=eceasy/cli-proxy-api:(?:latest|v\d+\.\d+\.\d+)@(sha256:[a-f0-9]{64})$', re.M)
ACCEPT = 'application/vnd.oci.image.index.v1+json, application/vnd.docker.distribution.manifest.list.v2+json'


def fetch(url, headers=None):
    request = urllib.request.Request(url, headers=headers or {})
    with urllib.request.urlopen(request, timeout=60) as response:
        return response.read()


def github_release():
    headers = {'Accept': 'application/vnd.github+json', 'User-Agent': 'cliproxy-unraid-sync'}
    token = os.environ.get('GH_TOKEN')
    if token:
        headers['Authorization'] = 'Bearer ' + token
    return json.loads(fetch('https://api.github.com/repos/' + REPOSITORY + '/releases/latest', headers))


def release_version(release):
    tag = release.get('tag_name', '')
    if release.get('draft') or release.get('prerelease') or not VERSION.fullmatch(tag):
        raise ValueError('Expected a stable upstream release tagged vN.N.N')
    return tag


def registry_manifest(version):
    token_url = 'https://auth.docker.io/token?service=registry.docker.io&scope=repository:eceasy/cli-proxy-api:pull'
    token = json.loads(fetch(token_url))['token']
    return fetch('https://registry-1.docker.io/v2/' + IMAGE + '/manifests/' + version,
                 {'Authorization': 'Bearer ' + token, 'Accept': ACCEPT})


def resolve_image(raw):
    manifest = json.loads(raw)
    platforms = {(m.get('platform', {}).get('os'), m.get('platform', {}).get('architecture'))
                 for m in manifest.get('manifests', [])}
    if not {('linux', 'amd64'), ('linux', 'arm64')} <= platforms:
        raise ValueError('Upstream image must include Linux amd64 and arm64')
    return 'sha256:' + hashlib.sha256(raw).hexdigest()


def update_pin(root, release, digest):
    version = release_version(release)
    if not re.fullmatch(r'sha256:[a-f0-9]{64}', digest):
        raise ValueError('Invalid upstream digest')
    dockerfile = root / 'Dockerfile'
    text = dockerfile.read_text()
    match = PIN.search(text)
    if not match or len(PIN.findall(text)) != 1:
        raise ValueError('Expected exactly one upstream image pin in Dockerfile')
    old = re.search(r':(v\d+\.\d+\.\d+)@', match.group())
    if old:
        old_version = tuple(map(int, VERSION.fullmatch(old[1]).groups()))
        new_version = tuple(map(int, VERSION.fullmatch(version).groups()))
        if new_version < old_version:
            raise ValueError('Refusing to downgrade upstream')
        if new_version == old_version and match[1] != digest:
            raise ValueError('Upstream changed an existing release digest; review required')
    pin = 'ARG UPSTREAM_IMAGE=' + IMAGE + ':' + version + '@' + digest
    metadata = json.dumps({'repository': REPOSITORY, 'version': version, 'digest': digest,
                           'release_url': 'https://github.com/' + REPOSITORY + '/releases/tag/' + version}, indent=2) + '\n'
    metadata_path = root / 'upstream-release.json'
    changed = match.group() != pin or not metadata_path.exists() or metadata_path.read_text() != metadata
    if changed:
        dockerfile.write_text(PIN.sub(pin, text, count=1))
        metadata_path.write_text(metadata)
    return changed


def write_outputs(path, version, digest, changed):
    with path.open('a') as output:
        output.write('version=' + version + '\n')
        output.write('image=' + IMAGE + ':' + version + '@' + digest + '\n')
        output.write('changed=' + str(changed).lower() + '\n')


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path('.'))
    parser.add_argument('--output', type=Path)
    args = parser.parse_args(argv)
    release = github_release()
    version = release_version(release)
    digest = resolve_image(registry_manifest(version))
    changed = update_pin(args.root, release, digest)
    if args.output:
        write_outputs(args.output, version, digest, changed)
    print(version + ' pinned to ' + digest + (' (updated)' if changed else ' (unchanged)'))


if __name__ == '__main__':
    main()
