/**
 * hypn0.js — Основной клиентский скрипт для hypn0.xyz
 * Обеспечивает интеграцию HTMX, работу с Declarative Shadow DOM
 * и ленивую асинхронную подгрузку SVG-халфтонов через Alpine.js.
 */

// Автоматическая передача CSRF-токена в AJAX-запросах HTMX
document.addEventListener('htmx:configRequest', function(evt) {
  var csrfInput = document.querySelector('[name=csrfmiddlewaretoken]');
  var token = csrfInput ? csrfInput.value : null;
  if (!token) {
    var match = document.cookie.match(/csrftoken=([^;]+)/);
    if (match) token = match[1];
  }
  if (token) {
    evt.detail.headers['X-CSRFToken'] = token;
  }
});

// Полифилл / обработка Declarative Shadow DOM для старых браузеров и динамических вставок
function attachShadowRoots(root) {
  (root || document).querySelectorAll('template[shadowrootmode]').forEach(function(tmpl) {
    if (!tmpl.parentElement.shadowRoot) {
      var mode = tmpl.getAttribute('shadowrootmode') || 'open';
      var shadow = tmpl.parentElement.attachShadow({ mode: mode });
      shadow.appendChild(tmpl.content.cloneNode(true));
      tmpl.remove();
    }
  });
}

document.addEventListener('DOMContentLoaded', function() {
  attachShadowRoots(document);
});

// Обработка HTMX swap: инициализация теневого корня и Alpine.js компонентов в новом DOM-фрагменте
document.addEventListener('htmx:afterSwap', function(evt) {
  attachShadowRoots(evt.detail.target);
  if (window.Alpine && evt.detail && evt.detail.target) {
    window.Alpine.initTree(evt.detail.target);
  }
});

/**
 * hypn0LazySvg — Alpine-компонент ленивой асинхронной загрузки SVG в Shadow DOM.
 * Защищает от лагов быстрого скролла (AbortController + debounce),
 * размазывает пиковые сетевые всплески (джиттер) и изолирует стили/ID.
 */
function hypn0LazySvg(svgUrl) {
  return {
    svgUrl: svgUrl || '',
    loaded: false,
    error: false,
    _observer: null,
    _controller: null,
    _timer: null,

    init() {
      if (!this.svgUrl) return;
      var el = this.$el;

      if (!('IntersectionObserver' in window)) {
        this.fetchSvg(el);
        return;
      }

      var self = this;
      this._observer = new IntersectionObserver(function(entries) {
        entries.forEach(function(entry) {
          if (entry.isIntersecting) {
            var jitter = Math.floor(Math.random() * 60);
            self._timer = setTimeout(function() {
              self.fetchSvg(el);
            }, 120 + jitter);
          } else {
            if (self._timer) {
              clearTimeout(self._timer);
              self._timer = null;
            }
            if (self._controller) {
              self._controller.abort();
              self._controller = null;
            }
          }
        });
      }, {
        rootMargin: '120px 0px 120px 0px',
        threshold: 0.01
      });

      this._observer.observe(el);
    },

    fetchSvg(el) {
      if (this.loaded) return;
      if (this._controller) this._controller.abort();
      this._controller = new AbortController();

      var self = this;
      fetch(this.svgUrl, { signal: this._controller.signal })
        .then(function(resp) {
          if (!resp.ok) throw new Error('HTTP ' + resp.status);
          return resp.text();
        })
        .then(function(svgText) {
          if (!svgText) return;

          var shadow = el.shadowRoot;
          if (!shadow) {
            shadow = el.attachShadow({ mode: 'open' });
          }

          var style = document.createElement('style');
          style.textContent = [
            ':host {',
            '  display: flex;',
            '  width: 100%;',
            '  height: 100%;',
            '  align-items: center;',
            '  justify-content: center;',
            '  pointer-events: auto;',
            '  opacity: 0;',
            '  transition: opacity 0.35s ease-out;',
            '}',
            ':host(.is-loaded), :host([data-loaded]) {',
            '  opacity: 1;',
            '}',
            'svg {',
            '  width: 100%;',
            '  height: 100%;',
            '  object-fit: contain;',
            '}',
            ':host(:hover) svg, svg:hover {',
            '  --hypn0-play: running !important;',
            '}'
          ].join('\n');

          var parser = new DOMParser();
          var doc = parser.parseFromString(svgText, 'image/svg+xml');
          var svgEl = doc.querySelector('svg');

          shadow.innerHTML = '';
          shadow.appendChild(style);
          if (svgEl) {
            shadow.appendChild(svgEl);
          } else {
            var container = document.createElement('div');
            container.innerHTML = svgText;
            var innerSvg = container.querySelector('svg');
            if (innerSvg) shadow.appendChild(innerSvg);
          }

          self.loaded = true;
          self.error = false;
          el.setAttribute('data-loaded', 'true');
          el.classList.add('is-loaded');

          if (self._observer) {
            self._observer.disconnect();
            self._observer = null;
          }
        })
        .catch(function(err) {
          if (err.name === 'AbortError') return;
          self.error = true;
        });
    },

    destroy() {
      if (this._timer) clearTimeout(this._timer);
      if (this._controller) this._controller.abort();
      if (this._observer) this._observer.disconnect();
    }
  };
}
