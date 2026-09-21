<?php
/*
# Author: Stefan Saam, github@saams.de

#######################################################################
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

// Usage:
//$constants and $config must be defined in main script.-->

function display($clear=true) {
	global $config;
	global $constants;

	if ($config['conf_DISP'] == 'display' and $config['conf_DISP_RESOLUTION_X'] > 0 and $config['conf_DISP_RESOLUTION_Y'] > 0) {
		?>

		<details class="display-panel" id="display-panel">
			<summary title="<?php echo L::config_display_section; ?>"><span id="display-status" data-src="<?php echo str_replace('/var/www/little-backup-box', '' , $constants['const_DISPLAY_CONTENT_OLD_FILE']); ?>"><?php echo L::config_display_section; ?></span></summary>
			<img id="display" src="<?php echo str_replace('/var/www/little-backup-box', '' , $constants['const_DISPLAY_IMAGE_EXPORT_FILE']); ?>" style="width: <?php echo $constants['const_DISPLAY_SIZE_UI_X']; ?>px; height: <?php echo $constants['const_DISPLAY_SIZE_UI_Y']; ?>px; background: #000000; float: right;">
		</details>
		<script>
			(function(panel) {
				try {panel.open = localStorage.getItem('lbb-display-open') === '1';} catch(e) {}
				panel.addEventListener('toggle', function() {
					try {localStorage.setItem('lbb-display-open', panel.open ? '1' : '0');} catch(e) {}
					if (panel.open) {
						var display	= document.getElementById('display');
						display.src	= display.src.split('?')[0] + '?t=' + new Date().getTime();
					}
				});
			})(document.getElementById('display-panel'));
		</script>

		<?php
		if ($clear) {
			print('<div style="clear: both;"></div>');
		}
	}
}
