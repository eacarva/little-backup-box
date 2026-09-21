#!/usr/bin/env bash

# Fork: quick update. When only scripts/ changed since the last install, copy the files,
# rewrite the setup and restart the display: no apt, no downloads beyond git, no reboot.
# When anything else changed (installer, etc/, satellite scripts), run the regular update instead.
# Usage: bash update-quick.sh [branch]

branch="${1:-main}"
REPO="${LBB_REPO:-https://github.com/eacarva/little-backup-box.git}"
WEB_ROOT="${LBB_WEB_ROOT:-/var/www/little-backup-box}"
INSTALLED_DIR="${LBB_INSTALLED_DIR:-$HOME/little-backup-box}"	# clone left by the installer, used as the reference

if pgrep -f "${WEB_ROOT}/backup.py" >/dev/null; then
	echo "A backup is running. Update after it ends."
	exit 1
fi

NEW_DIR="$(mktemp -d)/little-backup-box"

echo "Downloading Little Backup Box (${branch})..."
if ! git clone --quiet --depth 1 --branch "${branch}" "${REPO}" "${NEW_DIR}"; then
	echo "Download failed."
	exit 1
fi

# only scripts/ may differ, everything the installer applies to the system must be unchanged
if [ ! -d "${INSTALLED_DIR}" ] || ! diff -rq --exclude=.git --exclude=scripts --exclude=dev --exclude='*.md' "${INSTALLED_DIR}" "${NEW_DIR}" >/dev/null; then
	echo "System files changed since the last install: running the regular update."
	cp -f "${NEW_DIR}/install-little-backup-box.sh" "${HOME}/install-little-backup-box.sh"
	exec bash "${HOME}/install-little-backup-box.sh" "${branch}" code
fi

echo "Only Little Backup Box files changed: quick update."
echo "const_SOFTWARE_BRANCH='${branch}'" >> "${NEW_DIR}/scripts/constants.sh"

# config, runtime files and the media link created by view.php stay
sudo rsync -a --delete \
	--exclude config.cfg --exclude config-standards.cfg --exclude tmp/ --exclude cache/ --exclude media \
	"${NEW_DIR}/scripts/" "${WEB_ROOT}/"

sudo python3 "${WEB_ROOT}/lib_setup.py"
sudo chown www-data:www-data "${WEB_ROOT}" -R
sudo find "${WEB_ROOT}" -mindepth 1 -maxdepth 1 ! -type l -exec chmod 777 {} + # not through the media link
sudo python3 "${WEB_ROOT}/lib_git.py" --write-installed

# restart the display daemon so the new display.py runs
sudo python3 "${WEB_ROOT}/lib_display.py" 'set:kill'
sleep 3
sudo python3 "${WEB_ROOT}/lib_display.py" "set:temp,time=3" ":$(python3 "${WEB_ROOT}/lib_language.py" box_cmd_update_stop1)" ":$(python3 "${WEB_ROOT}/lib_language.py" box_cmd_update_stop2)"

# this download is the reference for the next quick update
sudo rm -rf "${INSTALLED_DIR}"
mv "${NEW_DIR}" "${INSTALLED_DIR}"

echo "Update completed, no reboot needed."
