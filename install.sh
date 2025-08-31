#!/bin/bash

KLIPPER_PATH="${HOME}/klipper"
INSTALL_PATH="${HOME}/klipper-toolchanger-easy"
CONFIG_PATH="${HOME}/printer_data/config"

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

    if [ ! -d "${INSTALL_PATH}" ]; then
        echo "[DOWNLOAD] Downloading repository..."
        if git -C $installdirname clone https://github.com/jwellman80/klipper-toolchanger-easy.git $installbasename; then
            chmod +x ${INSTALL_PATH}/install.sh
            printf "[DOWNLOAD] Download complete!\n\n"
        else
            echo "[ERROR] Download of git repository failed!"
            exit -1
        fi
    else
        printf "[DOWNLOAD] repository already found locally. Continuing...\n\n"
    fi
}

function use_tap_per_tool {
    echo "[INSTALL] Tap Per Tool"

    ln -sfn "${INSTALL_PATH}"/examples/z\ probe/per\ tool\ probe/tool_detection.cfg "${CONFIG_PATH}"/toolchanger/readonly-configs/
    cp --update=none "${INSTALL_PATH}"/examples/easy-additions/user-configs/tools/tap_per_tool/* "${CONFIG_PATH}"/toolchanger/tools
    cp --update=none "${INSTALL_PATH}"/examples/easy-additions/user-configs/toolchanger-include.cfg "${CONFIG_PATH}"/toolchanger/toolchanger-include.cfg
}

function z_probe_on_shuttle {
    echo "[INSTALL] Z Probe on Shuttle"

    cp --update=none "${INSTALL_PATH}"/examples/easy-additions/user-configs/tools/probe_on_shuttle/* "${CONFIG_PATH}"/toolchanger/tools
    cp --update=none "${INSTALL_PATH}"/examples/easy-additions/user-configs/toolchanger-include_scanner.cfg "${CONFIG_PATH}"/toolchanger/toolchanger-include.cfg
}

function link_extension {
    echo "[INSTALL] Linking extension to Klipper..."
    for file in "${INSTALL_PATH}"/klipper/extras/*.py; do ln -sfn "${file}" "${KLIPPER_PATH}/klippy/extras/"; done
}

function do_shared_config {

    mkdir -p "${CONFIG_PATH}"/toolchanger
    mkdir -p "${CONFIG_PATH}"/toolchanger/tools
    mkdir -p "${CONFIG_PATH}"/toolchanger/readonly-configs

    ln -sfn "${INSTALL_PATH}"/examples/dock\ location/fixed/toolchanger.cfg "${CONFIG_PATH}"/toolchanger/readonly-configs
    ln -sfn "${INSTALL_PATH}"/examples/easy-additions/homing.cfg "${CONFIG_PATH}"/toolchanger/readonly-configs
    ln -sfn "${INSTALL_PATH}"/examples/calibrate-offsets.cfg "${CONFIG_PATH}"/toolchanger/readonly-configs
    ln -sfn "${INSTALL_PATH}"/examples/easy-additions/toolchanger-macros.cfg "${CONFIG_PATH}"/toolchanger/readonly-configs

    cp --update=none "${INSTALL_PATH}"/examples/easy-additions/user-configs/toolchanger-config.cfg "${CONFIG_PATH}"/toolchanger
}

function z_probe_option {
    echo -e "\n\n\nHow will you Z probe?"
    echo "1. I will use the TAP sensor as my Z probe on each tool"
    echo "2. I will use a shuttle mounted Beacon/Cartographer/Eddy/etc as my Z probe"
    read -rp "Select an option [1-2]: " z_probe_choice

    case $z_probe_choice in
        1)
            use_tap_per_tool
            ;;
        2)
            z_probe_on_shuttle
            ;;
        *)
            echo "[ERROR] Invalid option selected!"
            exit -1
            ;;
    esac
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
do_shared_config
link_extension
z_probe_option
restart_klipper