#!/bin/bash
#
# Original written by Viesturs Zarins
# Modified by Justin F. Hallett
# Modified by Chinh Nhan Vo, Dec 2024
#

## Global variables ------------------------------------------
REPO="VIN-y/klipper-toolchanger.git"
BRANCH="test-machine"
MACRODIR="misschanger_macros"
SERVICE="/etc/systemd/system/ToolChanger.service"
KLIPPER_PATH="${HOME}/klipper"
INSTALL_PATH="${HOME}/klipper-toolchanger"
CONFIG_PATH="${HOME}/printer_data/config"

### Functions ------------------------------------------------
set -eu
export LC_ALL=C

function preflight_checks {
    if [ "$EUID" -eq 0 ]; then
        echo "[PRE-CHECK] This script must not be run as root!"
        exit -1
    fi
    if [ "$(sudo systemctl list-units --full -all -t service --no-legend | grep -F 'klipper.service')" ]; then
        printf "[PRE-CHECK] Klipper service found! Continuing...\n\n"
    else
        echo "[ERROR] Klipper service not found, please install Klipper first!"
        exit -1
    fi
}

function check_download {
    local installdirname installbasename
    installdirname="$(dirname ${INSTALL_PATH})"
    installbasename="$(basename ${INSTALL_PATH})"
    doclone=0
    if [ ! -d "${INSTALL_PATH}" ]; then
        doclone=1
    else
        if [[ "$(cd "${INSTALL_PATH}" && git remote get-url origin)" != *"${REPO}"* ]]; then
            echo "[DOWNLOAD] Incorrect repository found in ${INSTALL_PATH}, remove and rerun install!"
            echo " -> rm -rf \"${INSTALL_PATH}\""
            exit -1
        fi
    fi
    if [ $doclone -gt 0 ]; then
        echo -n "[DOWNLOAD] Clone repository..."
        if git -C $installdirname clone -b ${BRANCH} https://github.com/${REPO} $installbasename; then
            chmod +x ${INSTALL_PATH}/scripts/install.sh
            echo " complete!"
        else
            echo " failed!"
            exit -1
        fi
    else
        echo "[DOWNLOAD] Repository already found locally. [UPDATING]"
        pushd "${INSTALL_PATH}"
        if ! git pull > /dev/null; then
            popd
            echo "Repo dirty, remove before rerun install"
            echo "by running the following command:"
            echo " -> rm -rf \"${INSTALL_PATH}\""
            exit -1
        fi
        popd
    fi
}

function remove_links {
    echo -n "[UNINSTALL] Remove old links..."
    if ! rm -rf ${CONFIG_PATH}/${MACRODIR}; then
        echo " failed!"
        exit -1
    fi
    echo " complete!"
    if [ -f "${SERVICE}" ]; then
        echo -n "[UNINSTALL] Service..."
        sudo rm "${SERVICE}"
        echo " complete!"
    fi
}

function remove_root {
    echo -n "[UNINSTALL] Purge old files..."
    if ! rm -rf "${INSTALL_PATH}"/; then
        echo " failed!"
        exit -1
    fi
    echo " complete!"
}

function link_extension {
    echo -n "[INSTALL] Link extension to Klipper..."
    for file in "${INSTALL_PATH}"/klipper/extras/*.py; do
        if ! ln -sfn ${file} "${KLIPPER_PATH}"/klippy/extras/; then
            echo " failed!"
            exit -1
        fi
    done
    echo " complete!"
}

function link_macros {
    echo -n "[INSTALL] Link macros to Klipper..."
    ## make sure macro folder exist
    if [ ! -d "${CONFIG_PATH}"/${MACRODIR} ]; then
        mkdir "${CONFIG_PATH}"/${MACRODIR}
    fi
    ## symbolically link files into macro folder
    for file in "${INSTALL_PATH}"/macros/*.cfg; do
        if ! ln -sfn ${file} "${CONFIG_PATH}"/${MACRODIR}/; then
            echo " failed!"
            exit -1
        fi
    done
    echo " complete!"
}

function copy_examples {
    ## This function is current not in use for MissChanger
    echo -n "[INSTALL] Copy in examples to Klipper..."
    for file in "${INSTALL_PATH}"/examples/*.cfg; do
        if ! cp -n ${file} "${CONFIG_PATH}"/; then
            echo " failed!"
            exit -1
        fi
    done
    echo " complete!"
}

function copy_settings {
    echo -n "[INSTALL] Copy setting template to user's config..."
    if [ ! -d "${INSTALL_PATH}"/scripts/misschanger_settings.cfg ]; then
        if ! cp -n "${INSTALL_PATH}"/scripts/misschanger_settings.cfg "${CONFIG_PATH}"/; then
            echo " failed!"
            exit -1
        fi
        echo " complete!"
    else
        echo " skip!"
        echo -n "    Existing user's config detected..."
    fi
}

function add_updater {
    if [ ! -f "${CONFIG_PATH}"/moonraker.conf ]; then
        echo "[INSTALL] No moonraker config found."
        echo
        return
    fi

    if [ "$(grep -c "$(head -n1 "${INSTALL_PATH}"/scripts/moonraker_update.txt | sed -e 's/\[/\\\[/' -e 's/\]/\\\]/')" "${CONFIG_PATH}"/moonraker.conf || true)" -eq 0 ]; then
        echo -n "[INSTALL] Adding update manager to moonraker.conf..."
        echo -e "\n" >> "${CONFIG_PATH}"/moonraker.conf
        while read -r line; do
            echo -e "${line}" >> "${CONFIG_PATH}"/moonraker.conf
        done < "${INSTALL_PATH}"/scripts/moonraker_update.txt
        echo -e "\n" >> "${CONFIG_PATH}"/moonraker.conf
        echo " complete!"
        sudo systemctl restart moonraker
    else
        echo "[INSTALL] Moonraker update entry found. [SKIPPED]"
    fi

    if ! grep ToolChanger "${CONFIG_PATH}"/../moonraker.asvc; then
        echo -n "[INSTALL] Adding update manager to moonraker.conf..."
        echo -e "\nToolChanger" >> "${CONFIG_PATH}"/../moonraker.asvc
        echo " complete!"
    else
        echo "[INSTALL] ToolChanger service authorized in moonraker. [SKIPPED]"
    fi
    echo
}

function install_service {
    if [ -f "${SERVICE}" ]; then
        echo "[INSTALL] Service already installed. [SKIPPED]"
        return
    fi
    echo -n "[INSTALL] Install Service..."
    S=$(<"${INSTALL_PATH}"/scripts/ToolChanger.service)
    S=$(sed "s/TC_USER/$(whoami)/g" <<< $S)
    echo "$S" | sudo tee "${SERVICE}" > /dev/null
    echo " complete!"
}

function check_includes {
    echo -n "[CHECK-INSTALL] Check for missing includes..."
    found=0
    for file in "${INSTALL_PATH}"/macros/*.cfg; do
        filename="${MACRODIR}/$(basename ${file})";
        if ! grep -qE "^([/s|/t]+)?.include ${filename}.$" "${CONFIG_PATH}"/printer.cfg; then
            if [ $found -lt 1 ]; then
                echo " found!"
                found=1
            fi
            echo " - Missing [include ${MACRODIR}/${filename}] in printer.cfg"
        fi
    done
    if [ $found -lt 1 ]; then
        echo " complete!"
    fi
}

function restart_klipper {
    echo -n "[POST-INSTALL] Restart Klipper..."
    if ! sudo systemctl restart klipper; then
        echo " failed!"
        exit -1
    fi
    echo " complete!"
}

### Run the script -------------------------------------------
printf "\n========================================\n"
echo "- Klipper toolchanger uninstall script -"
printf "========================================\n\n"
remove_links
remove_root
printf "\n========================================\n"
echo "- Some files are not removed           -"
echo "- please delete the user config files  -"
echo "- manually.                            -"
printf "========================================\n\n"
