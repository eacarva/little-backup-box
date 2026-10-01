// setup-nav.js
// Settings as a side menu with one section at a time; on a phone a list, then the section.
// Cards keep their place in or out of the form, so every POST stays as upstream.
// Without JS the page is the upstream accordion.
(function () {
	var T = window.SETTINGS_TEXT || {};

	// [group, hash, a field inside the section's card]
	var SECTIONS = [
		['use', 'backup', '#conf_BACKUP_CHECKSUM'],
		['use', 'language', '#conf_LANGUAGE'],
		['use', 'appearance', '#conf_THEME'],
		['use', 'view', '#conf_BACKUP_GENERATE_THUMBNAILS'],
		['box', 'display', '#conf_DISP_OLD'],
		['box', 'menu', '#conf_MENU_ENABLED'],
		['box', 'energy', '#conf_POWER_OFF_IDLE_TIME'],
		['box', 'hardware', '#conf_FAN_PWM_TEMP_C'],
		['network', 'wifi', '#conf_WIFI_PASSWORD_TYPE'],
		['network', 'vpn', '#conf_VPN_TYPE_RSYNC'],
		['network', 'cloud', '#restart_rclone_gui'],
		['network', 'rsync', '#conf_RSYNC_SERVER'],
		['network', 'comitup', 'a[href*="CMD=comitup_reset"]'],
		['alerts', 'mail', '#conf_MAIL_NOTIFICATIONS'],
		['alerts', 'social', '#conf_SOCIAL_PUBLISH_DATE'],
		['system', 'password', '#conf_PASSWORD_1'],
		['system', 'debug', '#conf_LOGLEVEL'],
		['system', 'settings-file', '#settings_file'],
		['system', 'update', '[onclick*="CMD=update\'"]'],
		['system', 'exit', '[name="exit_lbb"]']
	];
	var GROUPS = ['use', 'box', 'network', 'alerts', 'system', 'other'];
	var INLINE = /^(A|B|I|EM|CODE|SPAN|SMALL|U|SUP|SUB)$/;

	var form = document.querySelector('form:has(button[name="save"])');
	if (!form) return;
	var saveBar = form.querySelector('.card[style*="sticky"]');

	var root = document.createElement('div');
	root.className = 'settings';
	var nav = document.createElement('nav');
	nav.className = 'settings-nav';
	var main = document.createElement('div');
	main.className = 'settings-main';
	var back = document.createElement('a');
	back.className = 'settings-back';
	back.href = '#';
	back.textContent = '‹ ' + (T.back || '');
	root.append(nav, main);
	form.before(root);

	var cards = [];
	var next = form.nextElementSibling;
	main.append(back, form);
	while (next && next.classList.contains('card')) {
		var card = next;
		next = next.nextElementSibling;
		main.append(card);
	}
	main.querySelectorAll('.card').forEach(function (card) {
		if (card.querySelector(':scope > details')) cards.push(card);
	});

	var sections = {};
	var other = 0;
	cards.forEach(function (card) {
		var def = SECTIONS.find(function (s) { return card.querySelector(s[2]); });
		var hash = def ? def[1] : 'section-' + (++other);
		sections[hash] = {
			card: card,
			details: card.querySelector(':scope > details'),
			group: def ? def[0] : 'other',
			rank: def ? SECTIONS.indexOf(def) : SECTIONS.length + other
		};
	});
	var order = Object.keys(sections).sort(function (a, b) { return sections[a].rank - sections[b].rank; });

	GROUPS.forEach(function (group) {
		var hashes = order.filter(function (h) { return sections[h].group === group; });
		if (!hashes.length) return;
		var title = document.createElement('div');
		title.className = 'settings-group';
		title.textContent = (T.groups || {})[group] || group;
		nav.append(title);
		hashes.forEach(function (hash) {
			var link = document.createElement('a');
			link.href = '#' + hash;
			link.textContent = sections[hash].details.querySelector(':scope > summary').textContent.trim();
			sections[hash].link = link;
			nav.append(link);
		});
	});

	// upstream markup has no wrapper per field: pair switch + label, loose text becomes help
	function tidy(box) {
		var run = [];
		var afterField = false;
		function flush() {
			if (run.some(function (n) { return n.nodeType === 3 && n.textContent.trim(); })) {
				var help = document.createElement('span');
				help.className = afterField ? 'help indent' : 'help';
				run[0].before(help);
				run.forEach(function (n) { help.append(n); });
			}
			run = [];
		}
		Array.from(box.childNodes).forEach(function (n) {
			if (n.parentNode !== box) return;
			if (n.nodeType === 3 || (n.nodeType === 1 && INLINE.test(n.tagName))) {
				run.push(n);
				return;
			}
			flush();
			if (n.nodeType !== 1 || n.tagName === 'BR') return;
			if (n.tagName === 'STRONG') {
				if (afterField) n.classList.add('indent');
				return;
			}
			afterField = false;
			if (n.matches('input[type=checkbox], input[type=radio]') && n.nextElementSibling && n.nextElementSibling.tagName === 'LABEL') {
				var field = document.createElement('div');
				field.className = 'settings-field';
				n.before(field);
				field.append(n, n.nextElementSibling);
				afterField = true;
			} else if (n.tagName === 'DETAILS') {
				n.open = true;
				tidy(n);
			} else if (n.tagName === 'DIV' && !n.className) {
				tidy(n);
			}
		});
		flush();
	}

	// each subsection (h3, inner accordion, field div) becomes its own block
	function group(details) {
		var block = null;
		Array.from(details.children).forEach(function (n) {
			if (n.tagName === 'SUMMARY') return;
			if (n.tagName === 'DETAILS' || (n.tagName === 'DIV' && !n.className && n.querySelector(':scope > h3'))) {
				n.classList.add('settings-block');
				block = null;
				return;
			}
			if (n.tagName === 'H3' || !block) {
				block = document.createElement('div');
				block.className = 'settings-block';
				n.before(block);
			}
			block.append(n);
		});
	}

	order.forEach(function (hash) {
		var details = sections[hash].details;
		tidy(details);
		group(details);
		// the section title opens that section (also when a stale cached CSS shows every section)
		details.querySelector(':scope > summary').addEventListener('click', function (event) {
			event.preventDefault();
			location.hash = hash;
		});
		details.querySelectorAll('details > summary').forEach(function (summary) {
			summary.addEventListener('click', function (event) { event.preventDefault(); });
		});
	});

	var wide = window.matchMedia('(min-width: 700px)');
	var active = null;
	var dirty = 0;

	// the save bar shows in form sections, and on the phone list while changes are pending
	function bar() {
		root.classList.toggle('settings-noform', active ? !form.contains(active.card) : dirty === 0);
	}

	function show() {
		var hash = location.hash.slice(1);
		if (!sections[hash] && wide.matches) hash = order[0];
		root.classList.toggle('settings-list', !sections[hash]);
		root.classList.toggle('settings-section', !!sections[hash]);
		order.forEach(function (h) {
			var s = sections[h];
			s.card.classList.toggle('settings-hidden', h !== hash);
			if (h === hash) {
				s.details.open = true;
				s.link.setAttribute('aria-current', 'page');
			} else {
				s.link.removeAttribute('aria-current');
			}
		});
		active = sections[hash] || null;
		bar();
		if (root.getBoundingClientRect().top < 0) root.scrollIntoView();
	}

	window.addEventListener('hashchange', show);
	wide.addEventListener('change', show);
	show();

	// back to the same section after any POST on this page
	document.querySelectorAll('.settings form').forEach(function (f) {
		f.addEventListener('submit', function () {
			f.action = f.action.split('#')[0] + location.hash;
		});
	});

	// unsaved changes
	var fields = Array.from(form.elements).filter(function (el) {
		return el.name && !/^(file|hidden|submit|button|reset)$/.test(el.type);
	});
	function value(el) {
		return (el.type === 'checkbox' || el.type === 'radio') ? el.checked : el.value;
	}
	var initial = new Map(fields.map(function (el) { return [el, value(el)]; }));
	var status = document.createElement('span');
	status.className = 'settings-dirty';
	if (saveBar) saveBar.prepend(status);
	var submitting = false;

	function count() {
		var names = new Set();
		fields.forEach(function (el) {
			if (value(el) !== initial.get(el)) names.add(el.name);
		});
		dirty = names.size;
		bar();
		status.textContent = dirty === 0 ? T.unsavedNone : dirty === 1 ? T.unsavedOne : (T.unsavedCount || '').replace('{n}', dirty);
		if (saveBar) {
			saveBar.classList.toggle('settings-unsaved', dirty > 0);
			saveBar.classList.toggle('settings-clean', dirty === 0);
		}
	}

	form.addEventListener('input', count);
	form.addEventListener('change', count);
	form.addEventListener('submit', function () { submitting = true; });
	window.addEventListener('beforeunload', function (event) {
		if (dirty && !submitting) {
			event.preventDefault();
			event.returnValue = '';
		}
	});
	count();
})();
