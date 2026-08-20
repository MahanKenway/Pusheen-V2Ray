#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 1 ]]; then
  echo "usage: $0 <destination-directory>" >&2
  exit 64
fi

# This binary is intentionally used only by the opt-in beta compatibility lane.
# Production publication remains pinned to sing-box 1.13.19.
readonly VERSION="1.14.0-beta.17"
readonly ASSET="sing-box-${VERSION}-linux-amd64.tar.gz"
readonly SHA256="ecb0055e3b7f236191db41a9c23988b558796104cd231246a4fd12a193a1a933"
readonly URL="https://github.com/SagerNet/sing-box/releases/download/v${VERSION}/${ASSET}"

destination="$1"
temp_dir="$(mktemp -d)"
trap 'rm -rf "$temp_dir"' EXIT

curl --fail --location --retry 3 --retry-delay 2 --proto '=https' --tlsv1.2 \
  "$URL" --output "$temp_dir/$ASSET"
printf '%s  %s\n' "$SHA256" "$temp_dir/$ASSET" | sha256sum --check --status

rm -rf "$destination"
mkdir -p "$destination"
tar -xzf "$temp_dir/$ASSET" -C "$destination" --strip-components=1
chmod 0755 "$destination/sing-box"
"$destination/sing-box" version >/dev/null
