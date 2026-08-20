#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 1 ]]; then
  echo "usage: $0 <destination-directory>" >&2
  exit 64
fi

readonly VERSION="1.13.19"
readonly ASSET="sing-box-${VERSION}-linux-amd64.tar.gz"
readonly SHA256="ef88a9e577d474210867bd708933d042e9b70106529df2656182c9db90106aa1"
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
