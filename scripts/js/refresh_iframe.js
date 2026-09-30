// refresh_iframe.js
// The framed page (same origin) flows with the host page: no inner scrollbar, no own padding.
// Refresh swaps the body in place, so nothing blanks or jumps while the slow commands run.
function startIframeRefresh(iframeId, src, intervalMs) {
	var iframe = document.getElementById(iframeId);

	function fit() {
		var doc = iframe.contentDocument;
		if (!doc || !doc.body) return;
		doc.documentElement.style.overflow = "hidden";
		doc.documentElement.style.setProperty("min-height", "0", "important");
		doc.body.style.setProperty("min-height", "0", "important");
		doc.body.style.padding = "0";
		doc.body.style.margin = "0";
		iframe.style.height = doc.documentElement.scrollHeight + "px";
	}

	iframe.addEventListener("load", fit);
	window.addEventListener("resize", fit);

	return setInterval(function () {
		fetch(src, { cache: "no-store" })
			.then(function (response) { return response.text(); })
			.then(function (html) {
				iframe.contentDocument.body.innerHTML = new DOMParser().parseFromString(html, "text/html").body.innerHTML;
				fit();
			})
			.catch(function () {});
	}, intervalMs);
}
