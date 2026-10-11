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

  // Demo access: a one-tap "Sign in as jury" under the sign-in form, with the login shown beside it. The agent serves
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
      + '<button type="button" class="agi-demo-btn"><span class="agi-demo-mark">✦</span> Sign in as jury</button>'
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

  var queued = false;
  new MutationObserver(function () {
    if (!queued) { queued = true; requestAnimationFrame(function () { queued = false; rebrand(); demoAccess(); }); }
  }).observe(document.documentElement, { childList: true, subtree: true, characterData: true });

  // The hidden sign-in video would still download and play on load.
  var play = HTMLMediaElement.prototype.play;
  HTMLMediaElement.prototype.play = function () {
    if (this.getAttribute('data-testid') === 'login-video') {
      return Promise.resolve();
    }
    return play.apply(this, arguments);
  };
})();
