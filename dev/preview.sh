#!/usr/bin/env bash

# Preview the web UI locally with PHP 8.4 (as on Raspberry Pi OS Trixie), no Raspberry Pi needed.
# Needs docker and python3. Usage: dev/preview.sh [port]  ->  http://localhost:<port> (default 8090)
# Hardware, sudo and backups do not work here: pages render with default settings only.
# Restart the script to pick up code changes.

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PORT="${1:-8090}"
CONFIG_DIR="$(mktemp -d)"

# config.cfg from the defaults in lib_setup.py
python3 - "${REPO_DIR}/scripts" "${CONFIG_DIR}/config.cfg" <<'EOF'
import sys, types
sys.path.insert(0, sys.argv[1])
configobj			= types.ModuleType('configobj')
configobj.ConfigObj	= dict
sys.modules['configobj']	= configobj
import lib_setup

with open(sys.argv[2], 'w') as f:
	for var, conf in lib_setup.setup._setup__get_config_standard(None).items():
		value	= hex(conf['value']) if conf['type'] == 'int16' and not isinstance(conf['value'], str) else conf['value']
		sep		= "'" if conf['type'] in ['str', 'int16'] else ''
		f.write(f"{var}={sep}{value}{sep}\n")
EOF

exec docker run --rm -p "${PORT}:80" \
	-v "${REPO_DIR}/scripts:/src:ro" \
	-v "${CONFIG_DIR}/config.cfg:/config.cfg:ro" \
	php:8.4-cli \
	sh -c 'cp -r /src /var/www/little-backup-box && cp /config.cfg /var/www/little-backup-box/ && mkdir -p /var/www/little-backup-box/tmp && cd /var/www/little-backup-box && php -S 0.0.0.0:80'
