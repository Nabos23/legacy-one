/**
 * @one-ai/widget — typed loader for the One-AI embeddable chatbot widget.
 *
 * This package deliberately contains NO widget logic. It injects the hosted
 * `widget.js` from your One-AI deployment (so every embed stays on the latest
 * loader automatically) and wraps `window.OneAIWidget` in a typed, promise-
 * based API that plays well with SPA lifecycles:
 *
 *   import { initWidget } from '@one-ai/widget'
 *
 *   const widget = await initWidget({
 *     widgetId: 'YOUR_WIDGET_ID',
 *     apiUrl: 'https://api.your-one-ai.com',
 *     chatUrl: 'https://app.your-one-ai.com',
 *   })
 *   widget.open()
 *   // on unmount:
 *   widget.destroy()
 */
const SCRIPT_ATTR = 'data-oneai-widget-loader';
let scriptPromise = null;
function loadScript(chatUrl) {
    if (typeof window === 'undefined') {
        return Promise.reject(new Error('@one-ai/widget can only run in a browser environment.'));
    }
    if (window.OneAIWidget)
        return Promise.resolve(window.OneAIWidget);
    if (scriptPromise)
        return scriptPromise;
    scriptPromise = new Promise((resolve, reject) => {
        const existing = document.querySelector(`script[${SCRIPT_ATTR}]`);
        const script = existing !== null && existing !== void 0 ? existing : document.createElement('script');
        const settle = () => {
            if (window.OneAIWidget)
                resolve(window.OneAIWidget);
            else
                reject(new Error('widget.js loaded but window.OneAIWidget is missing.'));
        };
        if (existing) {
            existing.addEventListener('load', settle, { once: true });
            existing.addEventListener('error', () => reject(new Error('Failed to load widget.js')), { once: true });
            return;
        }
        script.src = `${chatUrl.replace(/\/$/, '')}/widget.js`;
        script.defer = true;
        script.setAttribute(SCRIPT_ATTR, 'true');
        script.onload = settle;
        script.onerror = () => {
            scriptPromise = null; // allow a retry after a transient network failure
            script.remove();
            reject(new Error(`Failed to load ${script.src}`));
        };
        document.body.appendChild(script);
    });
    return scriptPromise;
}
/**
 * Load widget.js (once) and initialize the widget. Re-initializing replaces
 * any existing instance rather than stacking launchers, so calling this from
 * a remounting component is safe.
 */
async function initWidget(options) {
    if (!options.widgetId || !options.apiUrl || !options.chatUrl) {
        throw new Error('@one-ai/widget: widgetId, apiUrl, and chatUrl are all required.');
    }
    const global = await loadScript(options.chatUrl);
    return global.init(options);
}
/** Tear down the active widget instance, if any. Safe to call repeatedly. */
function destroyWidget() {
    var _a;
    if (typeof window !== 'undefined')
        (_a = window.OneAIWidget) === null || _a === void 0 ? void 0 : _a.destroy();
}

module.exports = { initWidget, destroyWidget };
