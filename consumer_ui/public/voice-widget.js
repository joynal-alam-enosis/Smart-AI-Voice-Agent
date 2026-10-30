/* OmniVox floating concierge widget. Load once, then call OmniVoxWidget.mount(). */
(function () {
  'use strict';

  var script = document.currentScript;
  var defaultAppUrl = script && script.src ? new URL('./', script.src).toString() : 'http://localhost:3000/';

  function buildWidget(options) {
    var config = options || {};
    var appUrl = config.appUrl || defaultAppUrl;
    var tenantId = config.tenantId || 'grand-meridian';
    var target = config.target || document.body;
    if (!target) return null;

    var host = document.createElement('div');
    host.setAttribute('data-omnivox-widget', '');
    var shadow = host.attachShadow({ mode: 'open' });
    var style = document.createElement('style');
    style.textContent = ':host { all: initial; } .launcher { position: fixed; z-index: 2147483000; right: 24px; bottom: 24px; display: inline-flex; align-items: center; gap: 10px; border: 0; border-radius: 999px; padding: 13px 17px; color: #fff; background: linear-gradient(135deg, #111827, #6d28d9); box-shadow: 0 16px 42px rgba(30, 27, 75, .35); font: 600 14px/1 ui-sans-serif, system-ui, sans-serif; cursor: pointer; } .launcher:focus-visible { outline: 3px solid #c4b5fd; outline-offset: 3px; } .dot { width: 9px; height: 9px; border-radius: 50%; background: #5eead4; box-shadow: 0 0 0 4px rgba(94, 234, 212, .17); } .panel { position: fixed; z-index: 2147483001; right: 20px; bottom: 82px; width: min(440px, calc(100vw - 32px)); height: min(720px, calc(100vh - 110px)); border: 0; border-radius: 24px; box-shadow: 0 24px 80px rgba(15, 23, 42, .26); background: #fff; opacity: 0; pointer-events: none; transform: translateY(10px) scale(.98); transition: opacity 160ms ease, transform 160ms ease; } .panel.open { opacity: 1; pointer-events: auto; transform: translateY(0) scale(1); } @media (max-width: 560px) { .launcher { right: 16px; bottom: 16px; padding: 13px; } .label { display: none; } .panel { right: 8px; bottom: 72px; width: calc(100vw - 16px); height: min(760px, calc(100vh - 88px)); border-radius: 20px; } }';

    var button = document.createElement('button');
    button.className = 'launcher';
    button.type = 'button';
    button.setAttribute('aria-expanded', 'false');
    button.setAttribute('aria-label', 'Open Grand Meridian concierge');
    button.innerHTML = '<span class="dot" aria-hidden="true"></span><span class="label">Ask Elena</span>';

    var frame = document.createElement('iframe');
    frame.className = 'panel';
    frame.title = 'Grand Meridian digital concierge';
    frame.allow = 'microphone';
    frame.loading = 'lazy';
    frame.src = new URL('?embed=1&tenant=' + encodeURIComponent(tenantId), appUrl).toString();

    function toggle(forceOpen) {
      var open = typeof forceOpen === 'boolean' ? forceOpen : !frame.classList.contains('open');
      frame.classList.toggle('open', open);
      button.setAttribute('aria-expanded', String(open));
      button.querySelector('.label').textContent = open ? 'Close concierge' : 'Ask Elena';
    }
    button.addEventListener('click', function () { toggle(); });
    document.addEventListener('keydown', function (event) { if (event.key === 'Escape') toggle(false); });

    shadow.appendChild(style);
    shadow.appendChild(frame);
    shadow.appendChild(button);
    target.appendChild(host);
    return { close: function () { toggle(false); }, open: function () { toggle(true); }, destroy: function () { host.remove(); } };
  }

  window.OmniVoxWidget = window.OmniVoxWidget || { mount: buildWidget };
  if (script && script.dataset.autostart !== 'false') {
    buildWidget({ tenantId: script.dataset.tenant, appUrl: script.dataset.appUrl });
  }
}());
