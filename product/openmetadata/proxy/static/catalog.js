// OM 2.0.5 shows its first-visit prompts once per user (localStorage loggedInUsers, cookie STAR_OMD_USER_<name>)
// and once per version (cookie VERSION_<snake_case version>). Mark them seen from the user and version the
// API returns, before the app reads them.
(function () {
  // Test switch for browsers that offer service workers but cannot run them (Claude's in-app browser): OM then
  // keeps the session in tab memory and loses it on the first reload. With localStorage agi-no-service-worker=1
  // the API is hidden before OM starts, so OM uses its own localStorage fallback and the login survives.
  try {
    if (localStorage.getItem('agi-no-service-worker') === '1') delete Navigator.prototype.serviceWorker;
  } catch (e) {}

  var expires = new Date(Date.now() + 31 * 864e5).toUTCString();

  function setCookie(name) {
    document.cookie = name + '=true; expires=' + expires + '; path=/; SameSite=Lax';
  }

  function markSeen(kind, body) {
    try {
      if (kind === 'user' && body && body.name) {
        var users = (localStorage.getItem('loggedInUsers') || '').split(',');
        if (users.indexOf(body.name) < 0) {
          users.push(body.name);
          localStorage.setItem('loggedInUsers', users.filter(Boolean).join(','));
        }
        setCookie('STAR_OMD_USER_' + body.name);
      } else if (kind === 'version' && body && body.version) {
        setCookie('VERSION_' + String(body.version).replace(/-SNAPSHOT$/, '').replace(/[^0-9A-Za-z]+/g, '_'));
      }
    } catch (e) {}
  }

  // The UI's HTTP client (axios) sends these over XMLHttpRequest; 'load' fires before its response handler.
  var open = XMLHttpRequest.prototype.open;
  XMLHttpRequest.prototype.open = function (method, url) {
    var kind = /\/api\/v1\/users\/loggedInUser(\?|$)/.test(String(url)) ? 'user'
      : /\/api\/v1\/system\/version(\?|$)/.test(String(url)) ? 'version' : '';
    if (kind) {
      this.addEventListener('load', function () {
        if (this.status === 200) {
          try { markSeen(kind, JSON.parse(this.responseText)); } catch (e) {}
        }
      });
    }
    return open.apply(this, arguments);
  };

  // Brand: the product is AGI (team name). OM's name is compiled into its UI, so swap it where users read it: the tab
  // title ("<page> | OpenMetadata", rewritten by OM on every page), the sign-in heading and the logo's alt text.
  function rebrand() {
    if (document.title.indexOf('OpenMetadata') >= 0) document.title = document.title.replace(/OpenMetadata/g, 'AGI');
    var nodes = document.querySelectorAll('[data-testid="login-form-container"] .header-text, img[alt*="OpenMetadata"]');
    for (var i = 0; i < nodes.length; i++) {
      var n = nodes[i];
      if (n.tagName === 'IMG') n.alt = n.alt.replace(/OpenMetadata/g, 'AGI');
      else if (n.textContent.indexOf('OpenMetadata') >= 0) n.textContent = n.textContent.replace(/OpenMetadata/g, 'AGI');
    }
  }

  // Demo access: a one-tap "Sign in to the demo" under the sign-in form, with the login shown beside it. The agent serves
  // the login from the server's .env (/agent/demo-login, 404 when unset), so the repo never holds the password.
  var demo = null, demoAsked = false;
  function setInput(input, value) {
    Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set.call(input, value);
    input.dispatchEvent(new Event('input', { bubbles: true }));
  }
  function demoAccess() {
    var form = document.querySelector('[data-testid="login-form-container"] .login-form');
    if (!form || form.querySelector('.agi-demo')) return;
    if (!demoAsked) {
      demoAsked = true;
      fetch('/agent/demo-login').then(function (r) { return r.ok ? r.json() : null; })
        .then(function (d) { demo = d; demoAccess(); }).catch(function () {});
      return;
    }
    if (!demo) return;
    var box = document.createElement('div');
    box.className = 'agi-demo';
    box.innerHTML = '<div class="agi-demo-or"><span>or</span></div>'
      + '<button type="button" class="agi-demo-btn"><span class="agi-demo-mark">✦</span> Sign in to the demo</button>'
      + '<div class="agi-demo-creds">Demo login: <code></code> · <code></code></div>';
    var codes = box.querySelectorAll('code');
    codes[0].textContent = demo.email;
    codes[1].textContent = demo.password;
    box.querySelector('button').addEventListener('click', function () {
      // React may have re-rendered the form since the card was added: look the fields up now.
      var page = document.querySelector('[data-testid="login-form-container"]');
      var email = page && page.querySelector('#email'), password = page && page.querySelector('#password');
      var submit = page && page.querySelector('[data-testid="login"]');
      if (!email || !password || !submit) return;
      setInput(email, demo.email);
      setInput(password, demo.password);
      setTimeout(function () { submit.click(); }, 0);
    });
    form.appendChild(box);
  }

  // The sign-in page says what AGI is, under its heading.
  function tagline() {
    var heading = document.querySelector('[data-testid="login-form-container"] .header-text');
    if (!heading || heading.parentNode.querySelector('.agi-tagline')) return;
    var p = document.createElement('p');
    p.className = 'agi-tagline';
    p.textContent = 'The data catalog that answers — with sources you can check.';
    heading.insertAdjacentElement('afterend', p);
  }

  // The search box offers the assistant too (chat.js turns a question typed there into an AI answer).
  var SEARCH_HINT = 'Ask AI anything, or search tables, metrics, terms…';
  function searchHint() {
    var box = document.getElementById('searchBox');
    if (box && box.placeholder !== SEARCH_HINT) box.placeholder = SEARCH_HINT;
  }

  function ask(question) {
    if (typeof window.agiAsk === 'function') window.agiAsk(question);
  }
  // A shortcut that needs another page first (e.g. "document this table") goes there with ?agi-ask=<question>.
  function askOnPage(path, question) {
    location.assign(path + '?agi-ask=' + encodeURIComponent(question));
  }
  function askFromUrl() {
    var params = new URLSearchParams(location.search), question = params.get('agi-ask');
    if (!question || typeof window.agiAsk !== 'function') return;
    params.delete('agi-ask');
    history.replaceState(history.state, '', location.pathname + (params.toString() ? '?' + params : '') + location.hash);
    setTimeout(function () { ask(question); }, 800);  // let OM render the page the question is about
  }

  var REPORT = '/table/greenplum.dwh.datamart_regtech.overdue_loans_report';
  var UNDOCUMENTED = '/table/greenplum.dwh.datamart.customer_segments';
  var QUESTIONS = [
    ['How is a loan classified as overdue?',
      'How do we decide a contract is overdue, and how are its days past due counted?'],
    ['Where does the 91–180 days figure come from?',
      'Where does the 91–180 days figure in September’s Overdue Loans Report come from, and did it pass its checks?'],
    ['May I use customers’ PINFL?',
      'I need customers’ PINFL with their overdue status — where is it, and may I use it?']
  ];
  var FEATURES = [
    ['Ask in your own words', 'Answers come from the catalog: tables, columns, owners, rules — with links.',
      'Ask a question', function () { ask(QUESTIONS[0][1]); }],
    ['Traced to the source', 'Every figure follows lineage from the central-bank report back to the core system, with the checks it passed.',
      'Trace a figure', function () { ask(QUESTIONS[1][1]); }],
    ['Documents itself — you approve', 'The assistant drafts table and column descriptions; nothing is written until a steward clicks Apply.',
      'Document a table', function () { askOnPage(UNDOCUMENTED, 'Document this table.'); }],
    ['Governed by design', 'Runs inside the bank’s perimeter under each user’s own permissions; every question is journaled.',
      'See the report’s lineage', function () { location.assign(REPORT + '/lineage'); }]
  ];

  // Home page: the banner becomes the assistant's front door — a promise, question shortcuts and what AGI does.
  function home() {
    var header = document.querySelector('[data-testid="landing-page-header"] .dashboard-header');
    if (!header || header.querySelector('.agi-home')) return;
    var welcome = header.querySelector('.welcome-user');
    if (welcome) {
      var sub = document.createElement('p');
      sub.className = 'agi-home-sub';
      sub.textContent = 'Ask anything about the bank’s data. Every answer cites its tables, lineage and checks.';
      welcome.parentNode.insertAdjacentElement('afterend', sub);
    }
    var search = header.querySelector('[data-testid="customise-search-container"]');
    var chips = document.createElement('div');
    chips.className = 'agi-home agi-chips';
    QUESTIONS.forEach(function (q) {
      var b = document.createElement('button');
      b.type = 'button';
      b.className = 'agi-chip';
      b.textContent = '✦ ' + q[0];
      b.title = q[1];
      b.addEventListener('click', function () { ask(q[1]); });
      chips.appendChild(b);
    });
    // Right under the search row (search box + domain selector), above "recently viewed".
    if (search && search.parentNode) search.parentNode.insertAdjacentElement('afterend', chips);
    else header.appendChild(chips);
    var cards = document.createElement('div');
    cards.className = 'agi-features';
    FEATURES.forEach(function (f) {
      var c = document.createElement('div');
      c.className = 'agi-feature';
      c.innerHTML = '<strong></strong><p></p><button type="button"></button>';
      c.querySelector('strong').textContent = f[0];
      c.querySelector('p').textContent = f[1];
      c.querySelector('button').textContent = f[2] + ' →';
      c.querySelector('button').addEventListener('click', f[3]);
      cards.appendChild(c);
    });
    header.appendChild(cards);
  }

  // Table pages: the assistant's two table actions sit next to the table's name.
  function tableActions() {
    if (!/^\/table\//.test(location.pathname)) return;
    var title = document.querySelector('[data-testid="entity-header-title"]');
    if (!title || (title.nextElementSibling && title.nextElementSibling.classList.contains('agi-table-actions'))) return;
    var box = document.createElement('div');
    box.className = 'agi-table-actions';
    [['✦ Ask about this table', 'What is this table, how is it built, and who owns it?', ''],
     ['✦ Document with AI', 'Document this table.', 'agi-secondary-action']].forEach(function (a) {
      var b = document.createElement('button');
      b.type = 'button';
      b.className = 'agi-table-action ' + a[2];
      b.textContent = a[0];
      b.addEventListener('click', function () { ask(a[1]); });
      box.appendChild(b);
    });
    title.insertAdjacentElement('afterend', box);
  }

  function refresh() {
    rebrand(); demoAccess(); tagline(); searchHint(); home(); tableActions();
  }
  var queued = false;
  new MutationObserver(function () {
    if (!queued) { queued = true; requestAnimationFrame(function () { queued = false; refresh(); }); }
  }).observe(document.documentElement, { childList: true, subtree: true, characterData: true });
  window.addEventListener('load', function () { setTimeout(askFromUrl, 1500); });

  // The hidden sign-in video would still download and play on load.
  var play = HTMLMediaElement.prototype.play;
  HTMLMediaElement.prototype.play = function () {
    if (this.getAttribute('data-testid') === 'login-video') {
      return Promise.resolve();
    }
    return play.apply(this, arguments);
  };
})();
