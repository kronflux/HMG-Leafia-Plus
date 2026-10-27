#!/system/bin/sh
. ./scripts/common.sh
# every way out of this run starts again whatever it, or an earlier run, stopped
trap apps_release EXIT
log "preuninstall wireless.carplay.aa"
check_addons || exit 1
if [ -e "$CATALOG_SELECTION" ] && ! catalog_check_backups; then
    log "FAIL: installed patch selection or original backups are invalid; keeping backups"
    exit 1
fi
_rev=$(installed_parts_rev)
log "undoing: $_rev"
apps_hold "$_rev"
uninstall_parts "$_rev" || exit 1
apps_release
rm -f "$PARTS_FILE" "$CATALOG_SELECTION"
adb_net_restore
sync
log "all parts back to stock - reboot the head unit to finish"
exit 0
