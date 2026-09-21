<?php
/*
# Fork: status home page. What is going on, what is plugged in, one button for the default backup.
# The full backup page (index.php) stays untouched and is linked as "other backup".
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.

# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#######################################################################*/

	$WORKING_DIR=dirname(__FILE__);
	$config = parse_ini_file($WORKING_DIR . "/config.cfg", false);
	$constants = parse_ini_file($WORKING_DIR . "/constants.sh", false);

	$theme = $config["conf_THEME"];
	$background = $config["conf_BACKGROUND_IMAGE"] == ""?"":"background='" . $constants["const_MEDIA_DIR"] . '/' . $constants["const_BACKGROUND_IMAGES_DIR"] . "/" . $config["conf_BACKGROUND_IMAGE"] . "'";

	include("sub-i18n-loader.php");

	function backup_running($WORKING_DIR) {
		exec("pgrep -f " . escapeshellarg("$WORKING_DIR/backup.py"), $pids);
		return(count($pids) > 0);
	}

	function mode_label($mode) {
		$parts	= explode(':', $mode, 2);
		$key	= $parts[0] == 'social' ? "social_$parts[1]" : $parts[0];
		$label	= defined("L::box_backup_mode_$key") ? constant("L::box_backup_mode_$key") : $mode;
		return($parts[0] == 'cloud' ? "$label: $parts[1]" : $label);
	}

	function human_size($bytes) {
		foreach (array('B', 'KB', 'MB', 'GB', 'TB') as $unit) {
			if ($bytes < 1000 or $unit == 'TB') {
				return(($bytes < 10 ? round($bytes, 1) : round($bytes)) . " $unit");
			}
			$bytes	/= 1000;
		}
	}

	// USB and NVMe partitions, plus cameras when no backup is using them
	function connected_devices($running) {
		$devices	= array();

		$lsblk	= json_decode(shell_exec('lsblk -J -b -o PATH,TYPE,TRAN,MODEL,LABEL,SIZE,FSAVAIL,MOUNTPOINT 2>/dev/null'), true);
		foreach ($lsblk['blockdevices'] ?? array() as $disk) {
			if (!in_array($disk['tran'] ?? '', array('usb', 'nvme'))) {continue;}

			foreach ($disk['children'] ?? array($disk) as $part) {
				if (empty($part['size'])) {continue;}

				$mountpoint	= $part['mountpoint'] ?? '';
				$role		= str_ends_with($mountpoint, '_target') ? L::main_target : (str_ends_with($mountpoint, '_source') ? L::main_source : '');

				$devices[]	= array(
					'type'	=> $disk['tran'],
					'name'	=> $part['label'] ?: trim($disk['model'] ?? '') ?: basename($part['path']),
					'size'	=> human_size($part['size']),
					'free'	=> empty($part['fsavail']) ? '' : human_size($part['fsavail']),
					'role'	=> $role
				);
			}
		}

		if (!$running) {
			exec('gphoto2 --auto-detect 2>/dev/null', $lines);
			foreach (array_slice($lines, 2) as $line) {
				$model	= trim(preg_split('/\s+usb:/', $line)[0]);
				if ($model) {
					$devices[]	= array('type' => 'camera', 'name' => $model, 'size' => '', 'free' => '', 'role' => '');
				}
			}
		}

		return($devices);
	}

	function print_devices($devices) {
		if (!$devices) {
			print('<p class="home-empty">' . L::home_no_devices . '</p>');
			return;
		}

		print('<ul class="home-devices">');
		foreach ($devices as $device) {
			$details	= array_filter(array($device['size'], $device['free'] ? $device['free'] . ' ' . L::box_backup_storage_free : ''));
			print('<li class="device-' . htmlspecialchars($device['type']) . '">');
			print('<span class="device-name">' . htmlspecialchars($device['name']) . '</span>');
			print('<span class="device-details">' . htmlspecialchars(implode(' · ', $details)) . '</span>');
			if ($device['role']) {
				print('<span class="device-role">' . $device['role'] . '</span>');
			}
			print('</li>');
		}
		print('</ul>');
	}

	$running	= backup_running($WORKING_DIR);

	// device list refresh
	if (isset($_GET['devices'])) {
		print_devices(connected_devices($running));
		exit;
	}

	$default_source		= $config['conf_BACKUP_DEFAULT_SOURCE'];
	$default_target		= $config['conf_BACKUP_DEFAULT_TARGET'];
	$default_available	= $default_source != 'none' && $default_target != 'none';

	// start the default backup with the options from the settings, like index.php does
	if (isset($_POST['start']) and $default_available and !$running) {
		$bool	= function($key) use ($config) {return($config[$key] ? 'True' : 'False');};

		$SecBackupArgs	= '';
		if ($config['conf_BACKUP_DEFAULT_SOURCE2'] != 'none' and $config['conf_BACKUP_DEFAULT_TARGET2'] != 'none') {
			$SecBackupArgs	= "--SecSourceName " . escapeshellarg($config['conf_BACKUP_DEFAULT_SOURCE2']) . " --SecTargetName " . escapeshellarg($config['conf_BACKUP_DEFAULT_TARGET2']);
		}

		shell_exec("sudo $WORKING_DIR/stop_backup.sh");
		shell_exec("sudo python3 $WORKING_DIR/backup.py --SourceName " . escapeshellarg($default_source) . " --TargetName " . escapeshellarg($default_target) . " --move-files " . $bool('conf_BACKUP_MOVE_FILES') . " --rename-files " . $bool('conf_BACKUP_RENAME_FILES') . " --force-sync-database False --generate-thumbnails " . $bool('conf_BACKUP_GENERATE_THUMBNAILS') . " --update-exif " . $bool('conf_BACKUP_UPDATE_EXIF') . " --checksum " . $bool('conf_BACKUP_CHECKSUM') . " --device-identifier-preset-source '' --device-identifier-preset-target '' --telegram-chat-id " . escapeshellarg($config['conf_SOCIAL_TELEGRAM_CHAT_ID']) . " --matrix-room-id " . escapeshellarg($config['conf_SOCIAL_MATRIX_ROOM_ID']) . " --power-off " . $bool('conf_POWER_OFF') . " $SecBackupArgs > /dev/null 2>&1 &");
	}

	if (isset($_POST['stopbackup'])) {
		shell_exec("sudo $WORKING_DIR/stop_backup.sh");
	}

	if ($_SERVER['REQUEST_METHOD'] == 'POST') {
		header('Location: /status.php');
		exit;
	}
?>

<html lang="<?php echo $config["conf_LANGUAGE"]; ?>" data-theme="<?php echo $theme; ?>">

<head>
	<?php include "sub-standards-header-loader.php"; ?>
	<script type="text/javascript" src="js/display.js"></script>
</head>

<body class="page-home" onload="refreshDisplay(); refreshDevices();" <?php echo $background; ?>>
	<?php include "{$WORKING_DIR}/sub-standards-body-loader.php"; ?>
	<?php include "{$WORKING_DIR}/sub-menu.php"; ?>
	<?php include "{$WORKING_DIR}/sub-display.php"; ?>

	<?php display(false); ?>

	<form class="card home-action" method="POST">
		<?php if ($running) { ?>
			<p class="home-running"><?php echo L::home_running; ?></p>
			<button name="stopbackup" class="danger"><?php echo L::main_stopbackup_button; ?></button>
		<?php } elseif ($default_available) { ?>
			<button name="start" class="home-start">
				<span><?php echo L::home_start; ?></span>
				<small><?php echo htmlspecialchars(mode_label($default_source) . ' → ' . mode_label($default_target)); ?></small>
			</button>
		<?php } else { ?>
			<p><?php echo L::home_no_default; ?> <a href="/setup.php"><?php echo L::home_setup_default; ?></a></p>
		<?php } ?>
		<a class="home-other" href="/index.php"><?php echo L::home_other; ?></a>
	</form>

	<div class="card">
		<h3><?php echo L::home_devices; ?></h3>
		<div id="home-devices">
			<?php print_devices(connected_devices($running)); ?>
		</div>
	</div>

	<script>
		function refreshDevices() {
			setTimeout(function() {
				fetch('/status.php?devices=1')
					.then(response => response.ok ? response.text() : null)
					.then(html => {if (html !== null) {document.getElementById('home-devices').innerHTML = html;}})
					.catch(() => {})
					.finally(refreshDevices);
			}, 5000);
		}
	</script>
</body>
</html>
