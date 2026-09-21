// refreshDisplay
// Refresh the display status banner and the display image every 2 seconds
// needs:
// in <head>: <script type="text/javascript" src="js/display.js"></script>
// '<body onload="refreshDisplay('true/false')">'
// and '<iframe id="display" ...'

let DisplayInterval = 'undefined';

function refreshDisplay() {
	var display = document.getElementById("display");
	var status	= document.getElementById("display-status");

	// status banner: the text the box's display shows right now
	if (status) {
		fetch(status.dataset.src + '?t=' + new Date().getTime())
			.then(response => response.ok ? response.text() : '')
			.then(text => renderDisplayStatus(status, text))
			.catch(() => {});
	}

	// skip the image download while the display panel is collapsed
	let panel = display ? display.closest('details') : null;
	if (display && (!panel || panel.open)) {
		// Get the original src without query parameters
		let originalSrc = display.src.split('?')[0];

		// Append a timestamp to bust the cache
		display.src = originalSrc + '?t=' + new Date().getTime();
	}

	if (DisplayInterval === 'undefined') {
		// Schedule next refresh
		setTimeout(refreshDisplay, 2000);
	}
}

// display content lines look like "s=hc:Text"; "set:..." lines are settings, "PGBAR=n" is progress,
// "s=b:..." lines are older messages kept below the current one, so they are skipped
function renderDisplayStatus(status, text) {
	let lines		= [];
	let progress	= null;

	text.split('\n').forEach(function(line) {
		line = line.trim();
		if (!line || line.startsWith('set:') || line.startsWith('s=b:')) {return;}

		line = line.slice(line.indexOf(':') + 1).trim();
		if (!line || line.startsWith('IMAGE=')) {return;}

		if (line.startsWith('PGBAR=')) {
			progress = parseFloat(line.slice(6)) || 0;
		} else if (line.startsWith('>') && lines.length) {
			// "USB" + "> USB" is source and target
			lines[lines.length - 1] += ' → ' + line.slice(1).trim();
		} else if (/^\p{Ll}/u.test(line) && lines.length) {
			// the display wraps one sentence over two lines: "Settings" + "saved."
			lines[lines.length - 1] += ' ' + line;
		} else {
			lines.push(line);
		}
	});

	if (!lines.length) {return;}

	let first		= document.createElement('strong');
	first.textContent	= lines[0];
	let rest		= document.createElement('span');
	if (progress !== null) {
		lines.splice(1, 0, Math.round(progress) + '%');
	}
	rest.textContent	= lines.slice(1).map(line => ' · ' + line).join('');
	status.replaceChildren(first, rest);

	let panel = status.closest('details');
	panel.classList.toggle('working', progress !== null);
	panel.style.setProperty('--progress', Math.min(progress || 0, 100) + '%');
}
