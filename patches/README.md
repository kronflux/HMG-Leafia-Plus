# Patch sets

Content-derived groups in `catalog.json` select shared patch files. Historical folders and manifests remain for restoration of older installations; their names are storage labels, not compatibility identities. The head unit rebuilds the modified projection apps from its own stock files with these (see `packages/wireless-carplay-aa/scripts/build.sh`), so no modified app is shipped.

| Folder | Car | Firmware |
|---|---|---|
| `ev6/` | Kia EV6, US (`CVEV.USA.*`) | 260507 |
| `ev6_ca/` | Kia EV6, Canada (`CVEV.CAN.*`): same code as the US EV6, so its manifest uses the `ev6/` patches on Canada's own APKs | 260206 |
| `ev6_ca_v014/` | Kia EV6, Canada: historical folder for the observed 250818 release; its app code and Android Auto library have separate deltas from the observed 260206 release | 250818 |
| `neev/` | Hyundai Ioniq 5, US (`NEEV.USA.*`, `NEEV23.USA.*`) | 260507 |
| `neev_ca/` | Hyundai Ioniq 5, Canada (`NEEV.CAN.*`): its Android Auto library differs from the US one, so it carries its own library delta | 260206 |
| `dl3hev/` | Kia K5 Hybrid, Korea: kept, not in `cars` (no Korean unit has shown Wi-Fi hardware) | 260902 |
| `neev_kr/` | Hyundai Ioniq 5, Korea: kept, not in `cars` (as above) | 260902 |
| `common/` | `libautoreceiver_infobank.so` for every car with the US stock library (a car with a different one has its own delta in its folder); `optional`: fixes applied wherever the stock file matches | |

`catalog.json` binds complete patch families to the exact original APK, ODEX and library identities. The head unit selects a family from those contents, regardless of the product label. `cars` supplies display names and supports restoration of older installations.

Run `python3 tools/patch-catalog.py --refresh-identities` after changing the content contract; this updates group IDs and their compatibility-page bindings together. Run `python3 tools/compat-built.py` when outputs change. For metadata-only changes, run `python3 tools/patch-catalog.py`. The compiler validates the complete input/output group, dependencies, payload SHA-256 and each delta's embedded source identity, then generates the plain-data `catalog` used on the unit. `tools/build-package.sh` refuses stale catalog data. Shared outputs reference the same delta file rather than duplicating it.

A full installation requires exactly one matching family and the existing Wi-Fi and cluster checks. Unknown content retains basic wireless projection on a fresh installation. Conflicting installed state is refused. Original backups must belong to the installation and match the selected input identities; live APKs and libraries must be recognized stock or selected outputs. Optimized ODEX files are bound to their recognized APKs and original ODEX backups.

The selected family and catalog identity are persisted as data through installation and restoration. Uninstall checks original backups before restoring them and removes the selection after restoration succeeds. Unknown firmware bytes require a reviewed new family; this catalog does not infer changes to unfamiliar code.

## Group identities

Every active group uses `set-<full SHA-256>` rather than a model, region or partial firmware version. The digest covers canonical JSON (`sort_keys=True`, compact separators, ASCII encoding) containing the identity format `leafia-patch-set-1`, original path-to-MD5 bindings, behavior revision, sorted capabilities and dependencies, and outputs sorted by part and component name. Each output includes its part, kind, name, expected output MD5 and patch payload SHA-256. Full digests are retained; abbreviated prefixes are only for display.

Names, firmware aliases, `legacy_id` and patch storage paths are excluded. Renaming or relocating the same patch does not change a group; changing a relevant original, patch payload or behavior contract does. The original-file identities remain MD5 as used by the on-unit patch helper. The group's SHA-256 fingerprints that contract; it is not a SHA-256 measurement of each original file. A fingerprint identifies a combination, while review and validation establish compatibility.

`legacy_id` links each group to its previous restoration manifest. Firmware prefixes are descriptive lookup metadata, not exact release identities or selection gates. Complete observed release strings can be recorded as provenance without affecting the group identity. New groups still require complete compatible component sets; this scheme does not independently mix unvalidated component recipes.

## Files

- `<App>.tbt.lpd`: rebuilds the turn-by-turn version of the app's code from the stock `<App>.odex`.
- `<App>.bridge.lpd`: rebuilds the CarPlay-bridge version (turn-by-turn included).
- `stock`: md5 of each stock file this car must have (`<file name> <md5>`).
- `manifest`: one line per output: `<part> <app|file> <name> <patch> <md5 of the result>`.

An `.lpd` holds the md5 of the exact stock file it needs and of the result. `lpatch delta` writes nothing unless both match.

## Adding a car

Have the owner run the **port** Leafia kit (`leafia-kit-port.zip`) on the new car and send its `LEAFIA/private` folder privately (`stock/` holds the projection apps and the framework), then:

```
tools/port.py --variant <name> --prefix <product prefix> --name "<car name>" --new-stock <dir> --new-fw <LEAFIA/private/stock/framework> --ref-stock <EV6 stock dir> --ref-fw <EV6 framework> --ref-builds <builds dir> --out-builds <dir>
```

`<dir>` holds the new car's `app/<App>.apk`, `app/<App>.odex` and `lib/libautoreceiver_infobank.so`.

It compares the new car's apps with the EV6's class by class:

- Classes that are identical, or that differ but carry none of our changes, are taken as they are.
- Classes that differ and carry our changes are merged automatically when the difference is only renamed members (obfuscation shifts between firmwares), or when our change applies cleanly as a 3-way patch.
- Anything else stops the port and is listed for a person to merge.

Every result is then checked: each reference inside the app must resolve, and every system call must exist in the new car's framework. If all checks pass, it writes `patches/<name>/` and adds the car to `cars`. The full builds in `--out-builds` stay private.

Ported this way, the Ioniq 5 comes out byte for byte identical to its hand-made set, and the K5 Hybrid class for class identical.

## Optional fixes (`common/optional`)

Fixes that aren't tied to one car's projection apps, listed in `common/optional` in the manifest's line format. The head unit applies each one only when its stock file is the exact one the `.lpd` was made from; otherwise it logs a skip and the install carries on.

- `HKMC_BtSettings.menu.<stock md5 prefix>.lpd` (part `5_menu`), one per stock version of the Bluetooth settings app: with our wireless features on, Settings > Phone Projection would open the wireless projection page, which has no CarPlay split-screen option and lists no phones paired through our bridge. On US/Canada units this keeps it on Device Connections, as on stock US firmware. Make one for a car with `tools/mkmenu.py <stock dir>` (it adds the line here); the unit uses the first line whose stock file it has.

## Making a set by hand

Needs the car's stock files (`app/<name>.apk`, `app/<name>.odex`, `lib/libautoreceiver_infobank.so`), the modified builds in the `2_tbt/<files>` and `3_bridge/<files>` layout, the host `lpatch` (`tools/lpatch/build.sh`) and `pip install --require-hashes -r tools/requirements.txt`:

```
tools/mkpatches.py <ev6|neev|dl3hev> <stock dir> <builds dir> patches
```

The installer's stock checksums (`comp/2_tbt`) and expected app checksums (`comp/3_bridge`) must match the new set.
