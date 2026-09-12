#!/usr/bin/env bash
# Installer for AIC8800D80 / AIC8800D81 USB WiFi 6 dongles (USB id 368b:8d81) on
# Linux kernel 7.1 and 7.2 (tested on Fedora 44). WiFi only.
#
# Downloads the BrosTrend aic8800 driver, applies the kernel-7.1/7.2 source
# patches, installs firmware + the udev mode-switch rule, and builds via DKMS.
set -euo pipefail

DEB_URL=https://linux.brostrend.com/aic8800-dkms.deb
HERE="$(cd "$(dirname "$0")" && pwd)"

echo ">>> [1/6] Installing build prerequisites (dnf)..."
sudo dnf install -y dkms "kernel-devel-$(uname -r)" kernel-headers gcc make bc \
    binutils elfutils-libelf-devel wget

work="$(mktemp -d)"; trap 'rm -rf "$work"' EXIT; cd "$work"
echo ">>> [2/6] Downloading driver package..."
wget --no-check-certificate -qO aic.deb "$DEB_URL"
ar x aic.deb && tar xf data.tar.*

# The package version is whatever the .deb extracts to (e.g. 1.0.9 or 6.4.3.0 -
# BrosTrend has shipped both; the code is identical). Detect it, don't hardcode.
SRCDIR="$(ls -d usr/src/aic8800-*/ | head -1)"; SRCDIR="${SRCDIR%/}"
VER="$(basename "$SRCDIR" | sed 's/^aic8800-//')"
SRC="/usr/src/aic8800-$VER"
echo "    detected package version: $VER"

echo ">>> [3/6] Applying kernel 7.1/7.2 patches..."
python3 "$HERE/patch_kernel71.py" "$SRCDIR"

echo ">>> [4/6] Installing source, firmware, and udev mode-switch rule..."
sudo rm -rf "$SRC"; sudo cp -r "$SRCDIR" /usr/src/
sudo cp -r lib/firmware/aic8800* /lib/firmware/
sudo cp lib/udev/rules.d/aic.rules /lib/udev/rules.d/
sudo udevadm control --reload-rules && sudo udevadm trigger || true

echo ">>> [5/6] Building and installing via DKMS..."
sudo dkms remove -m aic8800 -v "$VER" --all 2>/dev/null || true
sudo dkms add    -m aic8800 -v "$VER" 2>/dev/null || true
sudo dkms build  -m aic8800 -v "$VER" --force
sudo dkms install -m aic8800 -v "$VER" --force

echo ">>> [6/6] Loading driver..."
sudo modprobe -r aic8800_fdrv aic_load_fw 2>/dev/null || true
sudo modprobe aic8800_fdrv
sleep 3

echo
if nmcli device 2>/dev/null | grep -q wifi; then
    echo ">>> SUCCESS - WiFi device present:"
    nmcli device | grep wifi
else
    echo ">>> Driver installed, but no WiFi device yet."
    echo "    Unplug and replug the dongle (it powers on in storage mode; the udev"
    echo "    rule switches it on replug), then run:  sudo modprobe aic8800_fdrv"
fi
echo
echo "NOTE: If Secure Boot is enabled, enroll the DKMS signing key so the module can load:"
echo "      sudo mokutil --import /var/lib/dkms/mok.pub   # then reboot -> 'Enroll MOK'"
