#!/usr/bin/env bash
# Install one pinned Xray release for Kaveh's isolated validation runner.
set -euo pipefail

readonly XRAY_VERSION="v26.3.27"
readonly ASSET_NAME="Xray-linux-64.zip"
readonly EXPECTED_SHA256="23cd9af937744d97776ee35ecad4972cf4b2109d1e0fe6be9930467608f7c8ae"
readonly INSTALL_DIR="${1:-.tools/xray}"
readonly DOWNLOAD_URL="https://github.com/XTLS/Xray-core/releases/download/${XRAY_VERSION}/${ASSET_NAME}"

if [[ -x "${INSTALL_DIR}/xray" ]]; then
  exit 0
fi

workspace="$(mktemp -d)"
cleanup() { rm -rf "${workspace}"; }
trap cleanup EXIT

curl --fail --location --silent --show-error --retry 2 --retry-delay 2 \
  --output "${workspace}/${ASSET_NAME}" "${DOWNLOAD_URL}"
actual_sha256="$(sha256sum "${workspace}/${ASSET_NAME}" | awk '{print $1}')"
if [[ "${actual_sha256}" != "${EXPECTED_SHA256}" ]]; then
  echo "Xray checksum verification failed" >&2
  exit 1
fi

mkdir -p "${INSTALL_DIR}"
unzip -q "${workspace}/${ASSET_NAME}" xray -d "${INSTALL_DIR}"
chmod 0755 "${INSTALL_DIR}/xray"
"${INSTALL_DIR}/xray" version >/dev/null
