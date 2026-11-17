# Netmaker v1.7.0

This is the rock1881 fork of Netmaker Community Edition v1.7.0, with selectable
one-way/two-way device policies. It is a community modification, not an official
Gravitl release. Upstream base: `9b0f07fd351511a89ad5cdbf67b84c4dc0285bb4`.

Source and downloads: https://github.com/rock1881/netmaker

## Container image

```sh
docker pull ghcr.io/rock1881/netmaker:v1.7.0
```

The image targets Linux amd64. Use it in place of the original Netmaker server
image in your existing v1.7.0 Compose deployment; retain your volumes, environment,
reverse proxy, and authentication settings. Follow upstream's required v1.6.0
migration before upgrading older deployments to v1.7.0.

A Docker image archive is also available in the release. After verifying
`SHA256SUMS`, import it with:

```sh
gzip -dc netmaker-v1.7.0-docker-linux-amd64.tar.gz | docker load
```

## Standalone binary

`netmaker-v1.7.0-linux-amd64.tar.gz` contains the server executable and license.
The binary uses musl libc (the same runtime as the upstream Alpine image).
Use it in the Alpine container or an environment with the musl amd64 loader;
it is not a static binary for arbitrary glibc-only Linux installations.

## UI direction selector

The UI patch archive contains the patch and a build helper, which downloads the
pinned official UI image and creates a local image with the direction dropdown:

```sh
mkdir netmaker-ui
cd netmaker-ui
tar -xzf ../netmaker-ui-v1.7.0-patch.tar.gz
python3 build-ui.py --tag netmaker-ui:v1.7.0
```

Use `netmaker-ui:v1.7.0` as the UI service image. The helper verifies the upstream
asset hash and refuses to modify an unreviewed UI build. Upstream UI licensing
continues to apply to that image; the release distributes the patch, not the
upstream UI bundle.

## Policy behavior

- One-way permits source-initiated connections and their replies.
- Two-way permits either endpoint to initiate connections.
- Enabled allow policies are additive. A matching two-way or All Nodes policy
  still allows both directions.
- Existing tracked connections and upstream DNS/management exceptions remain.
- Linux Netclient enforces the rules; static WireGuard clients use their gateway.
- This fork preserves direction at server startup. Stock CE converts one-way
  policies back to two-way on startup; review active policies before reverting.

Validated with Netclient v1.6.0 and v1.7.0, iptables and nftables, TCP/UDP/ICMP
forward traffic, responses, and reverse NEW rejection. Existing client production
code is unchanged. The source repository includes rule-generation and gateway
regression tests.
