#!/system/bin/sh
# Resolve one coherent patch family from original files. Selection is plain data.
CATALOG_SYSTEM=${CATALOG_SYSTEM:-/system}
CATALOG_BACKUP=${CATALOG_BACKUP:-/data/nemesis/backup/projection.tbt}
CATALOG_SELECTION=${CATALOG_SELECTION:-/data/nemesis/wireless.carplay.aa.selection}
CATALOG_PARTS=${CATALOG_PARTS:-/data/nemesis/wireless.carplay.aa.parts}

catalog_md5() {
    local _s _tool
    _tool=${LPATCH:-$CARS_DIR/../tools/lpatch}
    chmod 755 "$_tool" 2>/dev/null || true
    _s=$("$_tool" md5 "$1" 2>/dev/null) || return 1
    echo "${_s%% *}"
}

catalog_rows() {
    local _tag _id _rest
    while read -r _tag _id _rest; do
        [ "$_id" = "$1" ] && echo "$_tag $_id $_rest"
    done < "$CARS_DIR/catalog"
    return 0
}

catalog_validate_selection() {
    local _tag _version _hash _family _extra _want _body _actual
    [ -s "$1" ] || return 1
    read -r _tag _version _hash _family _extra < "$1" || return 1
    [ "$_tag $_version" = 'selection 1' ] && [ -z "$_extra" ] || return 1
    case "$_family" in ''|*[!A-Za-z0-9_.-]*|.|..) return 1 ;; esac
    _want=$(catalog_md5 "$CARS_DIR/catalog") || return 1
    [ "$_hash" = "$_want" ] || return 1
    _body=$(catalog_rows "$_family")
    case "$_body" in "family $_family "*) ;; *) return 1 ;; esac
    _want=$(echo "selection 1 $_hash $_family"; echo "$_body")
    _actual=$(cat "$1") || return 1
    [ "$_actual" = "$_want" ]
}

catalog_variant() {
    local _tag _version _hash _family
    catalog_validate_selection "$CATALOG_SELECTION" || return 1
    read -r _tag _version _hash _family < "$CATALOG_SELECTION"
    echo "$_family"
}

# Inventory each path once, including live bytes and any original backup.
# A backup is usable only when its ownership and the live APK/library agree.
catalog_inventory() {
    local _tag _id _path _sum _extra _seen=' ' _live _backup _lh _bh _owner
    _owner=no
    if catalog_validate_selection "$CATALOG_SELECTION"; then
        _owner=yes
    elif [ -s "$CATALOG_PARTS" ]; then
        case " $(cat "$CATALOG_PARTS") " in *' 2_tbt '*) _owner=yes ;; esac
    fi
    : > "$1" || return 1
    while read -r _tag _id _path _sum _extra; do
        [ "$_tag" = input ] || continue
        case "$_seen" in *" $_path "*) continue ;; esac
        _seen="$_seen$_path "
        case "$_path" in /system/app/*|/system/lib/*) ;; *) return 1 ;; esac
        _live="$CATALOG_SYSTEM/${_path#/system/}"
        _backup="$CATALOG_BACKUP/${_path##*/}"
        _lh=$(catalog_md5 "$_live") || _lh=missing
        _bh=none
        if [ -e "$_backup" ]; then
            _bh=$(catalog_md5 "$_backup") || _bh=missing
        fi
        echo "$_path $_lh $_bh $_owner" >> "$1" || return 1
    done < "$CARS_DIR/catalog"
}

catalog_known_output() {
    local _tag _id _part _kind _name _patch _sum
    while read -r _tag _id _part _kind _name _patch _sum; do
        [ "$_tag" = output ] && [ "$_id" = "$1" ] || continue
        case "$_kind" in app) _name="/system/app/$_name.apk" ;; file) _name="/system/lib/$_name" ;; esac
        [ "$_name" = "$2" ] && [ "$_sum" = "$3" ] && return 0
    done < "$CARS_DIR/catalog"
    return 1
}

catalog_matches() {
    local _tag _id _path _want _extra _p _live _backup _owner _found _apk _al _ab _ao
    while read -r _tag _id _path _want _extra; do
        [ "$_tag" = input ] && [ "$_id" = "$1" ] || continue
        _found=no
        while read -r _p _live _backup _owner; do
            [ "$_p" = "$_path" ] || continue
            _found=yes
            if [ "$_backup" = none ]; then
                [ "$_live" = "$_want" ] || return 1
            else
                [ "$_owner" = yes ] && [ "$_backup" = "$_want" ] || return 1
                if [ "$_live" != "$_want" ]; then
                    case "$_path" in
                        *.odex)
                            # Optimized code varies by runtime; bind it to a recognized live APK.
                            [ "$_live" != missing ] || return 1
                            _apk=${_path%.odex}.apk
                            _al=missing
                            while read -r _p _al _ab _ao; do [ "$_p" = "$_apk" ] && break; done < "$2"
                            catalog_known_output "$1" "$_apk" "$_al" || return 1 ;;
                        *) catalog_known_output "$1" "$_path" "$_live" || return 1 ;;
                    esac
                fi
            fi
            break
        done < "$2"
        [ "$_found" = yes ] || return 1
    done < "$CARS_DIR/catalog"
    return 0
}

catalog_resolve() {
    local _tag _id _rest _chosen='' _hash
    while read -r _tag _id _rest; do
        [ "$_tag" = family ] || continue
        if catalog_matches "$_id" "$1"; then
            [ -z "$_chosen" ] || return 1
            _chosen=$_id
        fi
    done < "$CARS_DIR/catalog"
    [ -n "$_chosen" ] || return 1
    _hash=$(catalog_md5 "$CARS_DIR/catalog") || return 2
    { echo "selection 1 $_hash $_chosen" && catalog_rows "$_chosen"; } > "$2.new" || return 2
    chmod 600 "$2.new" || return 2
    mv "$2.new" "$2" || return 2
}

catalog_manifest() {
    local _tag _id _rest
    catalog_validate_selection "$CATALOG_SELECTION" || return 1
    while read -r _tag _id _rest; do
        [ "$_tag" = output ] && echo "$_rest"
    done < "$CATALOG_SELECTION"
    return 0
}

catalog_stock_sum() {
    local _tag _id _path _sum
    catalog_validate_selection "$CATALOG_SELECTION" || return 1
    while read -r _tag _id _path _sum; do
        [ "$_tag" = input ] && [ "${_path##*/}" = "$1" ] && { echo "$_sum"; return 0; }
    done < "$CATALOG_SELECTION"
    return 1
}

# Validate every original before any part starts restoring files.
catalog_check_backups() {
    local _tag _id _path _sum _file _any=no
    catalog_validate_selection "$CATALOG_SELECTION" || return 1
    [ -d "$CATALOG_BACKUP" ] && _any=yes
    while read -r _tag _id _path _sum; do
        [ "$_tag" = input ] || continue
        if [ "$_any" = yes ]; then _file="$CATALOG_BACKUP/${_path##*/}"
        else _file="$CATALOG_SYSTEM/${_path#/system/}"; fi
        [ "$(catalog_md5 "$_file")" = "$_sum" ] || return 1
    done < "$CATALOG_SELECTION"
    return 0
}
