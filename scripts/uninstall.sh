#!/bin/bash
#
# Original written by Viesturs Zarins
# Modified by Justin F. Hallett
# Modified by Chinh Nhan Vo, Dec 2024
#

## Global variables ------------------------------------------
REPO="VIN-y/klipper-toolchanger.git"
MACRODIR="misschanger_macros"
SERVICE="/etc/systemd/system/ToolChanger.service"
KLIPPER_PATH="${HOME}/klipper"
INSTALL_PATH="${HOME}/klipper-toolchanger"
CONFIG_PATH="${HOME}/printer_data/config"

### Functions ------------------------------------------------
function remove_links {
    echo -n "[UNINSTALL] old links..."
    if ! rm -rf ${CONFIG_PATH}/${MACRODIR}; then
        echo " failed!"
        exit -1
    fi
    echo " complete!"
    if [ -f "${SERVICE}" ]; then
        echo -n "[UNINSTALL] service..."
        sudo rm "${SERVICE}"
        echo " complete!"
    fi
}

function remove_root {
    echo -n "[UNINSTALL] old files..."
    if ! rm -rf "${INSTALL_PATH}"/; then
        echo " failed!"
        exit -1
    fi
    echo " complete!"
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
