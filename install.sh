#!/bin/bash

KLIPPER_PATH="${HOME}/klipper"
INSTALL_PATH="${HOME}/klipper-toolchanger"

CONFIG_PATH="${HOME}/printer_data/config"
REPO="VIN-y/klipper-toolchanger.git"

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
        echo -n "[DOWNLOAD] Cloning repository..."
        if git -C $installdirname clone https://github.com/${REPO} $installbasename; then
            chmod +x ${INSTALL_PATH}/install.sh
            echo " complete!"
        else
            echo " failed!"
            exit -1
        fi
    else
        echo "[DOWNLOAD] repository already found locally. [UPDATING]"
        pushd "${INSTALL_PATH}"
        if ! git pull > /dev/null; then
            popd
            echo "Repo dirty, remove and rerun install by running the following command!"
            echo "\trm -rf \"${INSTALL_PATH}\""
            exit -1
        fi
        popd
    fi
    echo
}

function link_extension {
    echo "[INSTALL] Linking extension to Klipper..."
    for file in "${INSTALL_PATH}"/klipper/extras/*.py; do ln -sfn "${file}" "${KLIPPER_PATH}/klippy/extras/"; done
}

function restart_klipper {
    echo "[POST-INSTALL] Restarting Klipper..."
    sudo systemctl restart klipper
}

printf "\n======================================\n"
echo "- Klipper toolchanger install script -"
printf "======================================\n\n"

# Run steps
preflight_checks
check_download
# link_extension
restart_klipper
