#!/system/bin/sh
# Display lookup and compatibility helpers for the package's patch data. Set CARS_DIR to the package's
# patches/ folder before sourcing.
#   patches/cars             <product prefix> <variant> <car name>
#   patches/<variant>/stock  <file name> <md5 of the stock file>
#   patches/<variant>/manifest  <part> <app|file> <name> <patch> <md5 of the result>

. "$CARS_DIR/../scripts/catalog.sh"

car_line() {
    local _p _pre _v _n
    _p=$(getprop ro.build.product 2>/dev/null)
    [ -n "$_p" ] && [ -s "$CARS_DIR/cars" ] || return 1
    while read -r _pre _v _n; do
        case "$_pre" in ''|\#*) continue ;; esac
        case "$_p" in "$_pre"*) echo "$_v $_n"; return 0 ;; esac
    done < "$CARS_DIR/cars"
    return 1
}
car_variant() {
    local _l
    if [ -e "$CATALOG_SELECTION" ]; then catalog_variant; return $?; fi
    # Older installations have no selection record; retain their restoration path.
    _l=$(car_line) || return 1
    echo "${_l%% *}"
}
car_name() {
    local _l _selected _tag _variant _name
    if _l=$(car_line); then echo "${_l#* }"; return 0; fi
    _selected=$(catalog_variant) || return 1
    while read -r _tag _variant _name; do
        [ "$_tag" = name ] && [ "$_variant" = "$_selected" ] && { echo "$_name"; return 0; }
    done < "$CATALOG_SELECTION"
    echo "Compatible head unit"
}

# stock_sum <file name>: md5 of that stock file on this car
stock_sum() {
    local _f _s
    if [ -e "$CATALOG_SELECTION" ]; then catalog_stock_sum "$1"; return $?; fi
    [ -s "$CARS_DIR/$VARIANT/stock" ] || return 1
    while read -r _f _s; do
        [ "$_f" = "$1" ] && { echo "$_s"; return 0; }
    done < "$CARS_DIR/$VARIANT/stock"
    return 1
}

# built_sum <part> <name>: md5 of the file scripts/build.sh builds for that part
built_sum() {
    local _p _k _n _x _s
    if [ -e "$CATALOG_SELECTION" ]; then
        local _lines
        _lines=$(catalog_manifest) || return 1
        while read -r _p _k _n _x _s; do
            [ "$_p" = "$1" ] && [ "$_n" = "$2" ] && { echo "$_s"; return 0; }
        done <<CATALOG_OUTPUTS
$_lines
CATALOG_OUTPUTS
        return 1
    fi
    [ -s "$CARS_DIR/$VARIANT/manifest" ] || return 1
    while read -r _p _k _n _x _s; do
        [ "$_p" = "$1" ] && [ "$_n" = "$2" ] && { echo "$_s"; return 0; }
    done < "$CARS_DIR/$VARIANT/manifest"
    return 1
}
