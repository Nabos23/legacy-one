/*!
 * One-AI embeddable chatbot widget loader.
 *
 * Usage:
 *   <script src="https://app.your-domain.com/widget.js" defer></script>
 *   <script>
 *     window.addEventListener('load', function () {
 *       OneAIWidget.init({
 *         widgetId: 'YOUR_WIDGET_ID',
 *         apiUrl: 'https://api.your-domain.com',
 *         chatUrl: 'https://app.your-domain.com',
 *         previewToken: 'OPTIONAL_DRAFT_PREVIEW_TOKEN'
 *       });
 *     });
 *   </script>
 *
 * This script runs in the HOST PAGE's own origin, which is deliberate: every
 * network call to the backend (config/session/message/lead/upload) is made
 * from here, not from inside the iframe, so the Origin header the backend's
 * per-widget allowlist checks against is genuinely the site embedding the
 * widget. The iframe is a pure rendering surface -- it never talks to the
 * network directly, only exchanges postMessage with this script.
 */
(function (window, document) {
  'use strict';

  function OneAIWidgetInstance(opts) {
    if (!opts || !opts.widgetId || !opts.apiUrl || !opts.chatUrl) {
      throw new Error('OneAIWidget.init requires { widgetId, apiUrl, chatUrl }');
    }

    var widgetId = opts.widgetId;
    var apiUrl = String(opts.apiUrl).replace(/\/+$/, '');
    var chatUrl = String(opts.chatUrl).replace(/\/+$/, '');
    var previewToken = opts.previewToken ? String(opts.previewToken) : null;
    var storageKey = 'oneai_widget_session_' + widgetId;

    // postMessage target-origin asymmetry, documented once:
    // - parent -> iframe messages target the iframe's ACTUAL origin (derived
    //   from chatUrl) so a hijacked/renavigated frame can never receive
    //   widget config or visitor message content.
    // - iframe -> parent messages stay '*' BY DESIGN: the widget is embedded
    //   on arbitrary customer origins the iframe cannot know in advance, and
    //   nothing the iframe posts is secret (the parent page already sees all
    //   of it). Both sides still validate event.source before acting.
    var chatOrigin = (function () {
      try { return new URL(chatUrl).origin; } catch (e) { return chatUrl; }
    })();

    var isOpen = false;
    var iframeEl = null;
    var iframeLoaded = false; // src assigned (lazy -- see loadIframe)
    var iframeReady = false;  // iframe sent oneai:ready
    var containerEl = null;
    var launcherEl = null;
    var closeTimer = null;
    var offlineQueue = []; // sends attempted while navigator.onLine === false
    var DEFAULT_LAYOUT = {
      widget_width: 380, widget_height: 600, widget_min_width: 300, widget_min_height: 400,
      widget_max_width: 480, widget_max_height: 760, launcher_size: 56, launcher_shape: 'circle',
      launcher_icon: 'chat', launcher_icon_url: null, launcher_hover_effect: 'scale',
      offset_x: 20, offset_y: 20, border_radius: 16, shadow_style: 'medium', bubble_style: 'rounded',
      send_button_shape: 'circle', spacing_density: 'comfortable', animation_style: 'fade',
      mobile_full_screen: true, mobile_breakpoint_px: 640,
    };
    var config = { branding: { theme_color: '#4F46E5', position: 'bottom-right' }, layout: DEFAULT_LAYOUT, triggers: {}, behavior: {}, availability: {}, accessibility: {}, lead_fields: [] };
    var visitorSessionId = null;
    var scrollHandlerAttached = false;
    var scrollHandler = null;
    var mobileHandlerAttached = false;
    var unreadCount = 0;
    var badgeEl = null;

    var SHADOW_MAP = {
      none: 'none',
      soft: '0 2px 10px rgba(0,0,0,0.12)',
      medium: '0 12px 40px rgba(0,0,0,0.25)',
      strong: '0 20px 60px rgba(0,0,0,0.4)',
    };
    var LAUNCHER_SHADOW_MAP = {
      none: 'none',
      soft: '0 2px 8px rgba(0,0,0,0.15)',
      medium: '0 4px 16px rgba(0,0,0,0.2)',
      strong: '0 8px 28px rgba(0,0,0,0.35)',
    };
    var LAUNCHER_ICON_SVG = {
      chat: '<path d="M21 11.5a8.38 8.38 0 0 1-.9 3.8 8.5 8.5 0 0 1-7.6 4.7 8.38 8.38 0 0 1-3.8-.9L3 21l1.9-5.7a8.38 8.38 0 0 1-.9-3.8 8.5 8.5 0 0 1 4.7-7.6 8.38 8.38 0 0 1 3.8-.9h.5a8.48 8.48 0 0 1 8 8v.5z" stroke="white" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>',
      message: '<path d="M4 4h16v12H7l-3 3V4z" stroke="white" stroke-width="2" stroke-linejoin="round" fill="none"/>',
      robot: '<rect x="4" y="8" width="16" height="11" rx="2" stroke="white" stroke-width="2" fill="none"/><path d="M12 8V4M9 4h6" stroke="white" stroke-width="2" stroke-linecap="round"/><circle cx="9" cy="13.5" r="1.3" fill="white"/><circle cx="15" cy="13.5" r="1.3" fill="white"/>',
    };

    function getStoredSession() {
      try { return window.localStorage.getItem(storageKey); } catch (e) { return null; }
    }
    function storeSession(id) {
      try { window.localStorage.setItem(storageKey, id); } catch (e) { /* storage unavailable */ }
    }

    function apiFetch(path, method, body) {
      return fetch(apiUrl + path, {
        method: method,
        headers: body ? { 'Content-Type': 'application/json' } : undefined,
        body: body ? JSON.stringify(body) : undefined,
      }).then(function (res) {
        if (!res.ok) {
          return res.json().catch(function () { return {}; }).then(function (data) {
            throw new Error((data && data.detail) || ('Request failed: ' + res.status));
          });
        }
        // 204 No Content (e.g. POST /lead) has nothing to parse.
        if (res.status === 204) return null;
        return res.json();
      });
    }

    function ensureSession() {
      var existing = getStoredSession();
      if (existing) {
        visitorSessionId = existing;
        return Promise.resolve(existing);
      }
      return apiFetch('/widget/' + widgetId + '/session', 'POST', {}).then(function (data) {
        visitorSessionId = data.visitor_session_id;
        storeSession(visitorSessionId);
        return visitorSessionId;
      });
    }

    // Simple glob: a trailing "*" matches any suffix; otherwise exact match.
    function matchesPath(pattern, path) {
      if (!pattern) return false;
      if (pattern.charAt(pattern.length - 1) === '*') {
        return path.indexOf(pattern.slice(0, -1)) === 0;
      }
      return path === pattern;
    }

    // Picks the locale-copy override matching the visitor's language: exact
    // tag first ("fr-CA"), then base language ("fr"). Returns [tag, copy] or null.
    function resolveLocale() {
      var locales = (config.branding && config.branding.locales) || {};
      var lang = (navigator.language || '').toLowerCase();
      if (!lang) return null;
      var tags = Object.keys(locales);
      for (var i = 0; i < tags.length; i++) {
        if (tags[i].toLowerCase() === lang) return [tags[i], locales[tags[i]]];
      }
      var base = lang.split('-')[0];
      for (var j = 0; j < tags.length; j++) {
        if (tags[j].toLowerCase() === base) return [tags[j], locales[tags[j]]];
      }
      return null;
    }

    // Branding with the visitor's locale copy merged in (non-copy fields
    // untouched). Cheap enough to derive on every use.
    function localizedBranding() {
      var resolved = resolveLocale();
      if (!resolved) return config.branding;
      var copy = resolved[1];
      var merged = {};
      for (var k in config.branding) merged[k] = config.branding[k];
      var COPY_FIELDS = ['header_title', 'header_subtitle', 'greeting_message', 'input_placeholder', 'loading_text', 'empty_state_text', 'error_message_text', 'quick_replies'];
      for (var i = 0; i < COPY_FIELDS.length; i++) {
        var f = COPY_FIELDS[i];
        if (copy[f] != null) merged[f] = copy[f];
      }
      return merged;
    }

    function resolveGreeting() {
      // Precedence: page-targeted greeting > locale greeting > base greeting.
      var greetings = (config.triggers && config.triggers.targeted_greetings) || [];
      var path = window.location.pathname;
      for (var i = 0; i < greetings.length; i++) {
        if (matchesPath(greetings[i].path_pattern, path)) return greetings[i].greeting;
      }
      return localizedBranding().greeting_message;
    }

    function positionStyle(pos) {
      return pos === 'bottom-left'
        ? { left: '20px', right: 'auto' }
        : { right: '20px', left: 'auto' };
    }

    function buildLauncherIcon() {
      var layout = config.layout || DEFAULT_LAYOUT;
      if (layout.launcher_icon === 'custom' && layout.launcher_icon_url) {
        return '<img src="' + layout.launcher_icon_url + '" alt="" style="width:26px;height:26px;object-fit:contain;" />';
      }
      var path = LAUNCHER_ICON_SVG[layout.launcher_icon] || LAUNCHER_ICON_SVG.chat;
      return '<svg width="26" height="26" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">' + path + '</svg>';
    }

    function buildLauncher() {
      var btn = document.createElement('button');
      btn.setAttribute('aria-label', 'Open chat');
      btn.style.cssText = [
        'position:fixed', 'border:none', 'cursor:pointer',
        'z-index:2147483000', 'display:flex', 'align-items:center', 'justify-content:center',
        'transition:transform 0.15s ease, box-shadow 0.15s ease',
      ].join(';');
      btn.onclick = function () { instance.toggle(); };
      return btn;
    }

    function applyLauncherLayout() {
      var layout = config.layout || DEFAULT_LAYOUT;
      var size = layout.launcher_size || 56;
      var radius = layout.launcher_shape === 'rounded-square' ? Math.min(16, size / 3.5) : size / 2;
      var shadow = LAUNCHER_SHADOW_MAP[layout.shadow_style || 'medium'];
      launcherEl.style.width = size + 'px';
      launcherEl.style.height = size + 'px';
      launcherEl.style.borderRadius = radius + 'px';
      launcherEl.style.boxShadow = shadow;
      launcherEl.innerHTML = buildLauncherIcon();
      var hover = layout.launcher_hover_effect || 'scale';
      launcherEl.onmouseenter = function () {
        if (hover === 'scale' || hover === 'both') launcherEl.style.transform = 'scale(1.06)';
        if (hover === 'shadow' || hover === 'both') launcherEl.style.boxShadow = LAUNCHER_SHADOW_MAP.strong;
      };
      launcherEl.onmouseleave = function () {
        launcherEl.style.transform = 'scale(1)';
        launcherEl.style.boxShadow = shadow;
      };
    }

    function buildIframe() {
      // Created WITHOUT a src: the embed page (its whole React bundle) isn't
      // fetched until the visitor actually opens the widget -- see
      // loadIframe()/prefetch below. Most visitors never open it.
      var frame = document.createElement('iframe');
      frame.title = 'Chat widget';
      frame.style.cssText = [
        'position:fixed', 'border:none', 'z-index:2147483000', 'display:none', 'background:#fff',
        'opacity:1', 'transform:none', 'transition:opacity 0.18s ease, transform 0.18s ease',
      ].join(';');
      frame.allow = 'microphone';
      return frame;
    }

    function loadIframe() {
      if (iframeLoaded) return;
      iframeLoaded = true;
      iframeEl.src = chatUrl + '/embed/' + encodeURIComponent(widgetId);
    }

    // Prefetch the embed page once the host page has been idle for a while,
    // so a later open feels instant -- but never compete with the host page's
    // own initial load.
    function schedulePrefetch() {
      setTimeout(function () {
        if (iframeLoaded) return;
        if (typeof window.requestIdleCallback === 'function') {
          window.requestIdleCallback(function () { loadIframe(); }, { timeout: 5000 });
        } else {
          loadIframe();
        }
      }, 3000);
    }

    function applyIframeLayout() {
      var layout = config.layout || DEFAULT_LAYOUT;
      iframeEl.style.width = (layout.widget_width || 380) + 'px';
      iframeEl.style.height = (layout.widget_height || 600) + 'px';
      iframeEl.style.minWidth = (layout.widget_min_width || 300) + 'px';
      iframeEl.style.minHeight = (layout.widget_min_height || 400) + 'px';
      iframeEl.style.maxWidth = (layout.widget_max_width || 480) + 'px';
      iframeEl.style.maxHeight = 'min(' + (layout.widget_max_height || 760) + 'px, calc(100vh - 110px))';
      iframeEl.style.borderRadius = (layout.border_radius != null ? layout.border_radius : 16) + 'px';
      iframeEl.style.boxShadow = SHADOW_MAP[layout.shadow_style || 'medium'];
    }

    function applyPosition() {
      var layout = config.layout || DEFAULT_LAYOUT;
      var pos = positionStyle(config.branding.position);
      var offsetX = layout.offset_x != null ? layout.offset_x : 20;
      var offsetY = layout.offset_y != null ? layout.offset_y : 20;
      var launcherSize = layout.launcher_size || 56;
      launcherEl.style.right = pos.right === 'auto' ? 'auto' : offsetX + 'px';
      launcherEl.style.left = pos.left === 'auto' ? 'auto' : offsetX + 'px';
      launcherEl.style.bottom = offsetY + 'px';
      iframeEl.style.right = pos.right === 'auto' ? 'auto' : offsetX + 'px';
      iframeEl.style.left = pos.left === 'auto' ? 'auto' : offsetX + 'px';
      iframeEl.style.top = 'auto';
      iframeEl.style.bottom = (offsetY + launcherSize + 12) + 'px';
      if (badgeEl) {
        var badgeOffset = offsetX + launcherSize - 10;
        badgeEl.style.right = pos.right === 'auto' ? 'auto' : badgeOffset + 'px';
        badgeEl.style.left = pos.left === 'auto' ? 'auto' : badgeOffset + 'px';
        badgeEl.style.bottom = (offsetY + launcherSize - 10) + 'px';
      }
    }

    function buildBadge() {
      var span = document.createElement('span');
      span.style.cssText = [
        'position:fixed', 'min-width:20px', 'height:20px', 'padding:0 5px', 'border-radius:10px',
        'background:#EF4444', 'color:#fff', 'font:600 11px/20px system-ui,sans-serif', 'text-align:center',
        'box-shadow:0 0 0 2px #fff', 'z-index:2147483001', 'display:none', 'pointer-events:none',
      ].join(';');
      return span;
    }

    function updateBadge() {
      if (!badgeEl) return;
      if (unreadCount > 0) {
        badgeEl.textContent = unreadCount > 9 ? '9+' : String(unreadCount);
        badgeEl.style.display = 'block';
      } else {
        badgeEl.style.display = 'none';
      }
    }

    function applyMobileLayout() {
      var layout = config.layout || DEFAULT_LAYOUT;
      var breakpoint = layout.mobile_breakpoint_px || 640;
      var isMobile = layout.mobile_full_screen && window.innerWidth <= breakpoint;
      if (isMobile) {
        iframeEl.style.top = '0';
        iframeEl.style.left = '0';
        iframeEl.style.right = '0';
        iframeEl.style.bottom = '0';
        iframeEl.style.width = '100vw';
        iframeEl.style.height = '100vh';
        iframeEl.style.maxWidth = '100vw';
        iframeEl.style.maxHeight = '100vh';
        iframeEl.style.minWidth = '0';
        iframeEl.style.minHeight = '0';
        iframeEl.style.borderRadius = '0';
      } else {
        applyIframeLayout();
        applyPosition();
      }
      if (!mobileHandlerAttached) {
        mobileHandlerAttached = true;
        window.addEventListener('resize', applyMobileLayout);
      }
    }

    function applyTheme() {
      launcherEl.style.background = config.branding.theme_color || '#4F46E5';
    }

    function setupTriggers() {
      var triggers = config.triggers || {};
      if (triggers.auto_open) {
        setTimeout(function () { instance.open(); }, triggers.auto_open_delay_ms || 4000);
      }
      if (triggers.open_on_scroll_percent != null && !scrollHandlerAttached) {
        scrollHandlerAttached = true;
        var threshold = triggers.open_on_scroll_percent;
        scrollHandler = function () {
          var doc = document.documentElement;
          var scrollable = (doc.scrollHeight || 1) - doc.clientHeight;
          var percent = scrollable > 0 ? (window.scrollY / scrollable) * 100 : 0;
          if (percent >= threshold) {
            instance.open();
            window.removeEventListener('scroll', scrollHandler);
            scrollHandler = null;
          }
        };
        window.addEventListener('scroll', scrollHandler, { passive: true });
      }
    }

    function postToIframe(message) {
      if (!iframeEl || !iframeEl.contentWindow) return;
      iframeEl.contentWindow.postMessage(message, chatOrigin);
    }

    function sendInitToIframe() {
      var resolved = resolveLocale();
      var availability = config.availability;
      // Locale copy owns offline_message too, so all translations live together.
      if (resolved && resolved[1].offline_message != null && availability) {
        availability = {};
        for (var k in config.availability) availability[k] = config.availability[k];
        availability.offline_message = resolved[1].offline_message;
      }
      postToIframe({
        type: 'oneai:init',
        payload: {
          widgetId: widgetId,
          branding: localizedBranding(),
          layout: config.layout || DEFAULT_LAYOUT,
          greeting: resolveGreeting(),
          availability: availability,
          accessibility: config.accessibility,
          leadFields: config.lead_fields,
          welcomeSound: !!(config.behavior && config.behavior.welcome_sound),
          allowAttachments: !!(config.behavior && config.behavior.allow_attachments),
          online: navigator.onLine !== false,
          // e.g. "es" -- the embed uses it to localize its built-in
          // micro-strings (Online/Away/Continue/Enter-hint) and RTL detection.
          locale: resolved ? resolved[0] : (navigator.language || null),
        },
      });
      maybeHydrateHistory();
    }

    // Returning visitor: restore the server-side transcript once per page
    // load, so reopening the widget doesn't read as amnesia. Only runs when
    // the session id came from storage (a brand-new session has no history).
    var historyHydrated = false;
    function maybeHydrateHistory() {
      if (historyHydrated || !getStoredSession()) return;
      historyHydrated = true;
      ensureSession()
        .then(function (sessionId) {
          return apiFetch('/widget/' + widgetId + '/session/' + encodeURIComponent(sessionId) + '/messages', 'GET');
        })
        .then(function (data) {
          if (data && data.messages && data.messages.length) {
            postToIframe({ type: 'oneai:history', payload: { messages: data.messages } });
          }
        })
        .catch(function () { /* hydration is best-effort -- greeting-only is fine */ });
    }

    function notifyAssistantActivity() {
      if (!isOpen) {
        unreadCount += 1;
        updateBadge();
      }
    }

    /* ---------------------------- messaging ---------------------------- */

    // Streams the assistant reply over SSE, forwarding progress to the iframe
    // as oneai:assistant-delta {clientId, kind: 'start'|'delta'|'done'} events.
    // The backend frames every event as `data: {"type": ..., "payload": ...}\n\n`;
    // today it emits tool_call/routing progress plus a final done/error, and
    // this parser also understands incremental token/delta events so nothing
    // changes here when the backend starts streaming tokens.
    // Rejects when the stream fails before a done event, so the caller can
    // fall back to the plain (non-streaming) endpoint.
    function streamMessage(sessionId, payload) {
      var body = { visitor_session_id: sessionId, message: payload.text };
      if (payload.attachments && payload.attachments.length) body.attachments = payload.attachments;
      return fetch(apiUrl + '/widget/' + widgetId + '/message/stream', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      }).then(function (res) {
        if (!res.ok || !res.body) throw new Error('Stream request failed: ' + res.status);
        postToIframe({ type: 'oneai:assistant-delta', payload: { clientId: payload.clientId, kind: 'start' } });

        var reader = res.body.getReader();
        var decoder = new TextDecoder();
        var buffer = '';
        var finished = false;

        function handleEvent(evt) {
          if (!evt || typeof evt !== 'object') return;
          var p = evt.payload || {};
          if (evt.type === 'token' || evt.type === 'delta') {
            var text = p.content != null ? p.content : (p.text != null ? p.text : p.delta);
            if (text) {
              postToIframe({ type: 'oneai:assistant-delta', payload: { clientId: payload.clientId, kind: 'delta', text: String(text) } });
            }
          } else if (evt.type === 'done') {
            finished = true;
            postToIframe({
              type: 'oneai:assistant-delta',
              payload: {
                clientId: payload.clientId,
                kind: 'done',
                // single-agent done payloads carry `reply`, supervisor ones `response`
                reply: p.reply != null ? p.reply : p.response,
                name: p.name,
              },
            });
            notifyAssistantActivity();
          } else if (evt.type === 'error') {
            throw new Error((p && p.message) || 'Stream error');
          } else if (evt.type === 'tool_call' || evt.type === 'routing') {
            // Surface engine progress as status text under the typing
            // indicator ("Using Web Search…" / "Routing to Billing…") so the
            // wait feels alive even though tokens only arrive at done.
            var label = evt.type === 'routing'
              ? (p.agent_name ? 'Routing to ' + p.agent_name + '…' : null)
              : (p.display_name ? 'Using ' + p.display_name + '…' : null);
            if (label) {
              postToIframe({ type: 'oneai:assistant-status', payload: { clientId: payload.clientId, text: label } });
            }
          }
        }

        function processBuffer(flush) {
          var chunks = buffer.split('\n\n');
          buffer = flush ? '' : chunks.pop();
          for (var i = 0; i < chunks.length; i++) {
            var lines = chunks[i].split('\n');
            for (var j = 0; j < lines.length; j++) {
              var line = lines[j];
              if (line.indexOf('data:') !== 0) continue;
              var raw = line.slice(5).replace(/^\s/, '');
              var evt;
              try { evt = JSON.parse(raw); } catch (e) { continue; }
              handleEvent(evt);
            }
          }
        }

        function pump() {
          return reader.read().then(function (result) {
            if (result.done) {
              buffer += decoder.decode();
              processBuffer(true);
              if (!finished) throw new Error('Stream ended without a done event');
              return null;
            }
            buffer += decoder.decode(result.value, { stream: true });
            processBuffer(false);
            return pump();
          });
        }
        return pump();
      });
    }

    function plainMessage(sessionId, payload) {
      var body = { visitor_session_id: sessionId, message: payload.text };
      if (payload.attachments && payload.attachments.length) body.attachments = payload.attachments;
      return apiFetch('/widget/' + widgetId + '/message', 'POST', body).then(function (res) {
        postToIframe({ type: 'oneai:assistant-message', payload: { reply: res.reply, name: res.name, clientId: payload.clientId } });
        notifyAssistantActivity();
      });
    }

    function attemptSend(payload) {
      return ensureSession().then(function (sessionId) {
        return streamMessage(sessionId, payload).catch(function () {
          // Stream transport failed -- fall back to the non-streaming endpoint.
          return plainMessage(sessionId, payload);
        });
      });
    }

    function handleSendMessage(payload) {
      if (navigator.onLine === false) {
        // Queued until connectivity returns -- the iframe is already showing
        // its offline notice, and flushOfflineQueue() below drains this.
        offlineQueue.push(payload);
        return;
      }
      attemptSend(payload).catch(function () {
        // One automatic retry with a short backoff before surfacing the
        // manual "Not sent -- Retry" affordance in the iframe.
        setTimeout(function () {
          attemptSend(payload).catch(function (err) {
            postToIframe({
              type: 'oneai:send-failed',
              payload: { clientId: payload.clientId, message: (err && err.message) || 'Message could not be sent.' },
            });
          });
        }, 1500);
      });
    }

    function flushOfflineQueue() {
      var queued = offlineQueue;
      offlineQueue = [];
      for (var i = 0; i < queued.length; i++) handleSendMessage(queued[i]);
    }

    function handleUploadRequest(payload) {
      var file = payload && payload.file;
      var uploadId = payload && payload.uploadId;
      if (!file || !uploadId) return;
      ensureSession()
        .then(function (sessionId) {
          var form = new FormData();
          form.append('file', file, file.name);
          form.append('visitor_session_id', sessionId);
          return fetch(apiUrl + '/widget/' + widgetId + '/upload', { method: 'POST', body: form });
        })
        .then(function (res) {
          if (!res.ok) {
            return res.json().catch(function () { return {}; }).then(function (data) {
              throw new Error((data && data.detail) || ('Upload failed: ' + res.status));
            });
          }
          return res.json();
        })
        .then(function (json) {
          // The upload response wraps the chat-shaped attachment payload as
          // {attachment_id, url, attachment}; only the inner `attachment` is
          // what /message accepts back in `attachments`.
          var attachment = (json && json.attachment) || json || {};
          if (json && json.url && !attachment.url) attachment.url = json.url;
          postToIframe({ type: 'oneai:upload-result', payload: { uploadId: uploadId, ok: true, attachment: attachment } });
        })
        .catch(function (err) {
          postToIframe({
            type: 'oneai:upload-result',
            payload: { uploadId: uploadId, ok: false, message: (err && err.message) || 'Upload failed.' },
          });
        });
    }

    function handleParentMessage(event) {
      if (event.source !== iframeEl.contentWindow) return;
      var data = event.data;
      if (!data || typeof data !== 'object') return;

      if (data.type === 'oneai:ready') {
        iframeReady = true;
        sendInitToIframe();
        if (isOpen) postToIframe({ type: 'oneai:visibility', payload: { open: true } });
      } else if (data.type === 'oneai:lead-submit') {
        var values = (data.payload && data.payload.values) || {};
        ensureSession()
          .then(function (sessionId) {
            return apiFetch('/widget/' + widgetId + '/lead', 'POST', { visitor_session_id: sessionId, values: values });
          })
          .then(function () {
            postToIframe({ type: 'oneai:lead-ack' });
          })
          .catch(function (err) {
            postToIframe({ type: 'oneai:error', payload: { message: (err && err.message) || 'Something went wrong.' } });
          });
      } else if (data.type === 'oneai:send-message') {
        var p = data.payload || {};
        if (!p.text) return;
        handleSendMessage({ text: p.text, clientId: p.clientId, attachments: p.attachments });
      } else if (data.type === 'oneai:upload-request') {
        handleUploadRequest(data.payload);
      } else if (data.type === 'oneai:minimize') {
        instance.close();
      } else if (data.type === 'oneai:feedback') {
        var fb = data.payload || {};
        ensureSession()
          .then(function (sessionId) {
            return apiFetch('/widget/' + widgetId + '/feedback', 'POST', {
              visitor_session_id: sessionId,
              message_id: fb.messageId,
              rating: fb.rating,
              message_excerpt: fb.excerpt || null,
            });
          })
          .catch(function () { /* best-effort -- the visitor's own UI already reflects their click */ });
      }
    }

    function handleConnectivityChange() {
      var online = navigator.onLine !== false;
      postToIframe({ type: 'oneai:connection', payload: { online: online } });
      if (online) flushOfflineQueue();
    }

    function mount() {
      containerEl = document.createElement('div');
      containerEl.id = 'oneai-widget-container';
      launcherEl = buildLauncher();
      iframeEl = buildIframe();
      badgeEl = buildBadge();
      containerEl.appendChild(iframeEl);
      containerEl.appendChild(launcherEl);
      containerEl.appendChild(badgeEl);
      document.body.appendChild(containerEl);
      applyLauncherLayout();
      applyIframeLayout();
      applyPosition();
      applyTheme();
      applyMobileLayout();
      window.addEventListener('message', handleParentMessage);
      window.addEventListener('online', handleConnectivityChange);
      window.addEventListener('offline', handleConnectivityChange);
      schedulePrefetch();
    }

    function animateOpen() {
      if (closeTimer) { clearTimeout(closeTimer); closeTimer = null; }
      var style = (config.layout && config.layout.animation_style) || 'fade';
      iframeEl.style.display = 'block';
      if (style === 'none') {
        iframeEl.style.opacity = '1';
        iframeEl.style.transform = 'none';
        return;
      }
      var startTransform = style === 'slide' ? 'translateY(16px)' : style === 'scale' ? 'scale(0.96)' : 'none';
      iframeEl.style.opacity = '0';
      iframeEl.style.transform = startTransform;
      // Force layout so the transition below actually animates from this state.
      void iframeEl.offsetHeight;
      iframeEl.style.opacity = '1';
      iframeEl.style.transform = 'none';
    }

    function animateClose() {
      var style = (config.layout && config.layout.animation_style) || 'fade';
      if (style === 'none') {
        iframeEl.style.display = 'none';
        return;
      }
      // Reverse of animateOpen: fade/slide/scale out, THEN hide.
      var endTransform = style === 'slide' ? 'translateY(16px)' : style === 'scale' ? 'scale(0.96)' : 'none';
      iframeEl.style.opacity = '0';
      iframeEl.style.transform = endTransform;
      closeTimer = setTimeout(function () {
        closeTimer = null;
        iframeEl.style.display = 'none';
        iframeEl.style.opacity = '1';
        iframeEl.style.transform = 'none';
      }, 200);
    }

    var instance = {
      open: function () {
        isOpen = true;
        loadIframe(); // lazy -- first open (or an auto-open trigger) loads the embed page
        animateOpen();
        if (iframeReady) postToIframe({ type: 'oneai:visibility', payload: { open: true } });
        unreadCount = 0;
        updateBadge();
      },
      close: function () {
        isOpen = false;
        if (iframeReady) postToIframe({ type: 'oneai:visibility', payload: { open: false } });
        animateClose();
      },
      toggle: function () {
        if (isOpen) instance.close(); else instance.open();
      },
      // Full teardown for SPA unmounts (React/Vue/Angular embed snippets call
      // this): removes the DOM and every window-level listener this instance
      // attached. A later init() creates a fresh instance.
      destroy: function () {
        if (closeTimer) { clearTimeout(closeTimer); closeTimer = null; }
        window.removeEventListener('message', handleParentMessage);
        window.removeEventListener('online', handleConnectivityChange);
        window.removeEventListener('offline', handleConnectivityChange);
        if (mobileHandlerAttached) window.removeEventListener('resize', applyMobileLayout);
        if (scrollHandler) window.removeEventListener('scroll', scrollHandler);
        if (containerEl && containerEl.parentNode) containerEl.parentNode.removeChild(containerEl);
        containerEl = null; iframeEl = null; launcherEl = null; badgeEl = null;
        isOpen = false;
      },
    };

    mount();
    var configPath = '/widget/' + widgetId + '/config' +
      (previewToken ? '?preview_token=' + encodeURIComponent(previewToken) : '');
    apiFetch(configPath, 'GET')
      .then(function (data) {
        if (data) config = data;
        applyLauncherLayout();
        applyIframeLayout();
        applyPosition();
        applyMobileLayout();
        applyTheme();
        setupTriggers();
        if (iframeReady) sendInitToIframe();
      })
      .catch(function () { /* keep defaults -- launcher still works */ });
    ensureSession().catch(function () { /* retried lazily on first send-message */ });

    return instance;
  }

  var activeInstance = null;
  window.OneAIWidget = {
    init: function (opts) {
      // One widget per page: re-initializing (SPA remounts, hot reloads)
      // replaces the previous instance instead of stacking launchers.
      if (activeInstance) activeInstance.destroy();
      activeInstance = OneAIWidgetInstance(opts);
      return activeInstance;
    },
    destroy: function () {
      if (activeInstance) {
        activeInstance.destroy();
        activeInstance = null;
      }
    },
  };
})(window, document);
