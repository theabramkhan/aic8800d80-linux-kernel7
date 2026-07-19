# aic8800-linux-kernel71

Get **AIC8800D80 / AIC8800D81** USB WiFi 6 dongles working on **Linux kernel 7.1+** (tested on Fedora 44, kernel 7.1.3). **WiFi only** — see [Bluetooth](#bluetooth) below.

These are the cheap AX900-class dongles that ship as a fake USB CD-ROM and are sold under many names (AX900, WIFI6-BW22, 88M80, Fenvi/Ninepluswifi AX900, etc.). The variant this repo targets reports USB id **`368b:8d81`** once switched into WiFi mode.

## Why this exists

The stock BrosTrend/AIC `aic8800` v1.0.9 driver **does not build on kernel 7.1** and **does not recognize the `0x368B` vendor ID**. On Fedora it fails in three separate ways, and the `dnf` install path also skips two required files. This repo patches all of that.

## Supported hardware

- `368b:8d81` — AIC8800D80/D81 with the newer AIC vendor ID (the case the stock driver misses).
- `a69c:8d81` — same chip, older vendor ID (already handled by the stock driver, but this repo works too).

Check yours: it appears as `a69c:5721 aicsemi Aic MSC` in `lsusb` *before* the WiFi-mode switch.

## Requirements

- Fedora 44 (or any distro on kernel **7.1+**). The patches are version-guarded (`LINUX_VERSION_CODE`), so the driver still builds on 6.x too.
- Build tools (the installer pulls these): `dkms kernel-devel kernel-headers gcc make bc binutils elfutils-libelf-devel`.
- If **Secure Boot** is on, you'll enroll a DKMS signing key (the installer prints the command).

## Install

```bash
git clone https://github.com/<you>/aic8800-linux-kernel71
cd aic8800-linux-kernel71
./install.sh
```

If no WiFi device appears at the end, **unplug and replug the dongle** (it powers on in storage mode; the udev rule switches it on plug), then `sudo modprobe aic8800_fdrv`.

The driver is installed via DKMS, so it **rebuilds automatically on kernel updates**.

## What the patches fix

`patch_kernel71.py` makes five changes to the v1.0.9 source (idempotent, self-checking):

1. **cfg80211 ops signature change (kernel 7.1).** Nine callbacks (`add_key`, `get_key`, `del_key`, `set_default_mgmt_key`, `add_station`, `del_station`, `change_station`, `get_station`, `dump_station`) plus the `cfg80211_new_sta` / `cfg80211_del_sta` calls changed their `struct net_device *` argument to `struct wireless_dev *`. Rewritten with version guards.
2. **`ieee80211_mgmt` action union restructured (kernel 7.1).** The nested `u.action.u` union was removed, breaking `rwnx_tdls.c`. The affected TDLS-discover path is compiled out on 7.1 (TDLS discovery isn't needed for a client adapter) and a dead tracepoint field is swapped for a valid one.
3. **`-Werror` (Fedora).** Fedora builds kernel modules with `-Werror`; the driver's pre-existing warnings are demoted so they aren't fatal.
4. **Missing device ID.** Adds `368b:8d81` (vendor `0x368B` + product `0x8d81`) to the driver's USB id table so it actually binds to this hardware.

The installer also copies the **firmware** (`/lib/firmware/aic8800*`) and the **udev mode-switch rule** (`/lib/udev/rules.d/aic.rules`) — the driver's own non-Debian install path skips both, which leaves the chip with no firmware and no way to leave storage mode on reboot.

## Manual install

If you'd rather not run the script:

```bash
sudo dnf install -y dkms kernel-devel-$(uname -r) gcc make bc binutils elfutils-libelf-devel wget
wget --no-check-certificate -O aic.deb https://linux.brostrend.com/aic8800-dkms.deb
ar x aic.deb && tar xf data.tar.*
python3 patch_kernel71.py usr/src/aic8800-1.0.9
sudo cp -r usr/src/aic8800-1.0.9 /usr/src/
sudo cp -r lib/firmware/aic8800* /lib/firmware/
sudo cp lib/udev/rules.d/aic.rules /lib/udev/rules.d/ && sudo udevadm control --reload-rules
sudo dkms add -m aic8800 -v 1.0.9
sudo dkms build -m aic8800 -v 1.0.9 --force
sudo dkms install -m aic8800 -v 1.0.9 --force
sudo modprobe aic8800_fdrv
```

## Bluetooth

**Not supported.** This driver never registers a Bluetooth HCI (`hci_register_dev`), and its BT firmware-load path is disabled. The BT side is tunneled over an internal transport rather than exposed as a USB interface, and the `368b:8d81` id specifically has no working Bluetooth in any current AIC Linux driver. If you need Bluetooth, a cheap dedicated USB BT dongle (CSR8510, Intel, etc.) works out of the box on Linux.

## Notes

- **Don't re-run the vendor's own installer** afterward — it overwrites the patched source with the stock (unbuildable-on-7.1) version.
- If a future kernel (7.2+) adds new API changes, the automatic DKMS rebuild may fail; the fix is the same pattern — patch the new break and `dkms build/install`. Your previous kernel stays bootable from GRUB.

## Credits & license

Driver source © AICSemi / BrosTrend, GPL-2.0-or-later. These patches are provided under the same license. Firmware blobs are redistributed from the BrosTrend package under their original terms.
