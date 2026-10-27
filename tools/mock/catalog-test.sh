#!/bin/sh
# Exercise content selection without firmware or manufacturer files.
set -eu
ROOT=$(cd "$(dirname "$0")/../.." && pwd)
TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT
export CARS_DIR="$TMP/patches" CATALOG_SYSTEM="$TMP/system"
export CATALOG_BACKUP="$TMP/backup" CATALOG_SELECTION="$TMP/selection"
export CATALOG_PARTS="$TMP/parts"
mkdir -p "$CARS_DIR" "$CATALOG_SYSTEM/app" "$CATALOG_BACKUP"
echo original > "$CATALOG_SYSTEM/app/A.apk"
echo code > "$CATALOG_SYSTEM/app/A.odex"
A=$(md5sum "$CATALOG_SYSTEM/app/A.apk"); A=${A%% *}
O=$(md5sum "$CATALOG_SYSTEM/app/A.odex"); O=${O%% *}
echo patched > "$TMP/patched"
P=$(md5sum "$TMP/patched"); P=${P%% *}
cat > "$CARS_DIR/catalog" <<EOF
catalog 1
family set-1111111111111111111111111111111111111111111111111111111111111111 revision-1
name set-1111111111111111111111111111111111111111111111111111111111111111 Example head unit
input set-1111111111111111111111111111111111111111111111111111111111111111 /system/app/A.apk $A
input set-1111111111111111111111111111111111111111111111111111111111111111 /system/app/A.odex $O
output set-1111111111111111111111111111111111111111111111111111111111111111 2_tbt app A set-1111111111111111111111111111111111111111111111111111111111111111/A.lpd $P
EOF
[ -f "$ROOT/packages/wireless-carplay-aa/scripts/catalog.sh" ] || { echo 'FAIL: content resolver is absent'; exit 1; }
cp "$CARS_DIR/catalog" "$TMP/original-catalog"
mkdir -p "$TMP/scripts"
cp "$ROOT/packages/wireless-carplay-aa/scripts/catalog.sh" "$TMP/scripts/catalog.sh"
. "$ROOT/packages/wireless-carplay-aa/scripts/cars.sh"
catalog_md5() { local s; s=$(md5sum "$1" 2>/dev/null) || return 1; echo "${s%% *}"; }
getprop() { echo UNKNOWN.VERSION; }
expect_fail() { if "$@"; then echo "FAIL: accepted $*"; exit 1; fi; }
catalog_inventory "$TMP/inventory"
catalog_resolve "$TMP/inventory" "$CATALOG_SELECTION"
[ "$(catalog_variant)" = set-1111111111111111111111111111111111111111111111111111111111111111 ]
echo 'PASS: known originals select without a product label'
[ "$(car_name)" = 'Example head unit' ]
echo 'PASS: content group retains its display name for unknown firmware'
cp "$CATALOG_SELECTION" "$TMP/previous-selection"
echo different > "$CATALOG_SYSTEM/app/A.apk"
catalog_inventory "$TMP/inventory"
expect_fail catalog_resolve "$TMP/inventory" "$CATALOG_SELECTION"
cmp "$CATALOG_SELECTION" "$TMP/previous-selection"
echo 'PASS: changed wrapper refuses matching code'
echo original > "$CATALOG_SYSTEM/app/A.apk"
catalog_inventory "$TMP/inventory"
ln -s /dev/full "$TMP/full.new"
code=0
catalog_resolve "$TMP/inventory" "$TMP/full" 2>/dev/null || code=$?
[ "$code" = 2 ] || { echo "FAIL: storage error returned $code instead of 2"; exit 1; }
echo 'PASS: storage errors are distinct from incompatible content'

echo original > "$CATALOG_SYSTEM/app/A.apk"
cp "$CATALOG_SYSTEM/app/A.apk" "$CATALOG_BACKUP/A.apk"
cp "$CATALOG_SYSTEM/app/A.odex" "$CATALOG_BACKUP/A.odex"
cp "$TMP/patched" "$CATALOG_SYSTEM/app/A.apk"
echo optimized > "$CATALOG_SYSTEM/app/A.odex"
echo 2_tbt > "$CATALOG_PARTS"
catalog_inventory "$TMP/inventory"
catalog_resolve "$TMP/inventory" "$CATALOG_SELECTION"
echo 'PASS: owned originals select behind installed outputs'
catalog_check_backups
echo 'PASS: complete original backups pass restoration preflight'
rm "$CATALOG_PARTS" "$CATALOG_SELECTION"
catalog_inventory "$TMP/inventory"
expect_fail catalog_resolve "$TMP/inventory" "$TMP/rejected"
echo 'PASS: unowned backups refuse selection'
echo 2_tbt > "$CATALOG_PARTS"
catalog_inventory "$TMP/inventory"
catalog_resolve "$TMP/inventory" "$CATALOG_SELECTION"
cp "$CATALOG_SELECTION" "$TMP/selected"
rm "$CATALOG_BACKUP/A.odex"
expect_fail catalog_check_backups
echo 'PASS: incomplete backups block restoration'
echo code > "$CATALOG_BACKUP/A.odex"

echo conflicting > "$CATALOG_BACKUP/A.apk"
catalog_inventory "$TMP/inventory"
expect_fail catalog_resolve "$TMP/inventory" "$TMP/rejected"
echo 'PASS: conflicting backup refuses selection'
echo original > "$CATALOG_BACKUP/A.apk"
echo unknown > "$CATALOG_SYSTEM/app/A.apk"
catalog_inventory "$TMP/inventory"
expect_fail catalog_resolve "$TMP/inventory" "$TMP/rejected"
echo 'PASS: unknown live APK refuses valid backup'
echo original > "$CATALOG_SYSTEM/app/A.apk"
echo code > "$CATALOG_SYSTEM/app/A.odex"
rm "$CATALOG_BACKUP/A.apk" "$CATALOG_BACKUP/A.odex"
catalog_inventory "$TMP/inventory"
sed 's/ set-1111111111111111111111111111111111111111111111111111111111111111 / set-2222222222222222222222222222222222222222222222222222222222222222 /g' "$CARS_DIR/catalog" | sed '1d' >> "$CARS_DIR/catalog.duplicate"
cat "$CARS_DIR/catalog.duplicate" >> "$CARS_DIR/catalog"
expect_fail catalog_resolve "$TMP/inventory" "$TMP/rejected"
echo 'PASS: ambiguous families refuse selection'
expect_fail catalog_validate_selection "$CATALOG_SELECTION"
echo 'PASS: changed catalog invalidates persisted selection'
echo 'selection 1 bad ../../escape' > "$CATALOG_SELECTION"
expect_fail catalog_validate_selection "$CATALOG_SELECTION"
echo 'PASS: malformed selection is data, never executed'

# The builder must refresh its inventory, not trust a prior selection or staged output.
cp "$TMP/original-catalog" "$CARS_DIR/catalog"
catalog_inventory "$TMP/inventory"
catalog_resolve "$TMP/inventory" "$CATALOG_SELECTION"
mkdir -p "$TMP/pkg/scripts" "$TMP/pkg/patches"
cp "$ROOT/packages/wireless-carplay-aa/scripts/"*.sh "$TMP/pkg/scripts/"
cp "$CARS_DIR/catalog" "$TMP/pkg/patches/catalog"
(
    cd "$TMP/pkg"
    . ./scripts/build.sh
    BUILD_DIR="$TMP/build"
    catalog_md5() { local s; s=$(md5sum "$1" 2>/dev/null) || return 1; echo "${s%% *}"; }
    log() { echo "$1"; }
    build_one() { touch "$TMP/builder-ran"; return 0; }
    echo changed-after-selection > "$CATALOG_SYSTEM/app/A.apk"
    expect_fail build_payloads
    [ ! -e "$TMP/builder-ran" ]
)
echo 'PASS: changed inputs are rejected before payload construction'

(
    cd "$TMP/pkg"
    saved_path=$PATH
    . ./scripts/common.sh
    trap - EXIT
    PATH=$saved_path
    PARTS_FILE="$TMP/cleanup.parts"
    CATALOG_BACKUP="$TMP/cleanup.backup"
    CATALOG_SELECTION="$TMP/cleanup.selection"
    echo pending > "$CATALOG_SELECTION"
    discard_uninstalled_selection
    [ ! -e "$CATALOG_SELECTION" ]
    echo installed > "$CATALOG_SELECTION"
    echo 2_tbt > "$PARTS_FILE"
    discard_uninstalled_selection
    [ -s "$CATALOG_SELECTION" ]
    rm "$PARTS_FILE"
    mkdir "$CATALOG_BACKUP"
    discard_uninstalled_selection
    [ -s "$CATALOG_SELECTION" ]
)
echo 'PASS: failed fresh selection is cleared while restoration state is retained'
