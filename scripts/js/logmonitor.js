// refreshLogMonitor
// Refresh the log monitor iframe every 2 seconds
// needs:
// in <head>: <script type="text/javascript" src="js/logmonitor.js"></script>
// '<body onload="refreshLogMonitor('true/false')">'
// and '<iframe id="logmonitor" ...'

let LogMonitorInterval = 'undefined';

function refreshLogMonitor() {
	var logmonitor = document.getElementById("logmonitor");
	logmonitor.onload = function() {styleLogMonitor(logmonitor);};

	if (!(logmonitor === document.activeElement)) {

		logmonitor.contentWindow.location.reload();

		if (LogMonitorInterval === 'undefined') {
			LogMonitorInterval = setInterval('logmonitor.contentWindow.scrollTo(0, 999999)',200);
		}

	} else {
		clearIntervalLogMonitor();
	}

	var t = setTimeout(refreshLogMonitor, 2000);
}

function clearIntervalLogMonitor() {
	if (LogMonitorInterval !== 'undefined') {
		clearInterval(LogMonitorInterval);
		LogMonitorInterval = 'undefined'
	}
}

// the log is a plain-text file: give it the page's theme colors
function styleLogMonitor(logmonitor) {
	try {
		var page	= getComputedStyle(document.documentElement);
		var style	= logmonitor.contentDocument.createElement('style');
		style.textContent	= 'html, body {margin: 0; color-scheme: ' + page.colorScheme + '; color: ' + page.getPropertyValue('--cfg') + '; background: ' + page.getPropertyValue('--csurface2') + ';}' +
			' pre {margin: .5rem .75rem; font: ' + page.getPropertyValue('--font-c') + '; white-space: pre-wrap;}';
		logmonitor.contentDocument.head.appendChild(style);
	} catch(e) {}
}
