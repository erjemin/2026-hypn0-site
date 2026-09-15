// analytics.js — Аналитика и счетчики посещений для hypn0.xyz
// Версия: 1.2 | Дата: 2026-09-16
// Содержит: Google Tag Manager, Yandex.Metrika

(function() {
  'use strict';

  // ============================================================================
  // Google Tag Manager (GTM)
  // ID: GTM-5FVH3KMJ
  // ============================================================================
  (function(w, d, s, l, i) {
    w[l] = w[l] || [];
    w[l].push({
      'gtm.start': new Date().getTime(),
      event: 'gtm.js'
    });
    var f = d.getElementsByTagName(s)[0],
      j = d.createElement(s),
      dl = l != 'dataLayer' ? '&l=' + l : '';
    j.async = true;
    j.src = 'https://www.googletagmanager.com/gtm.js?id=' + i + dl;
    f.parentNode.insertBefore(j, f);
  })(window, document, 'script', 'dataLayer', 'GTM-5FVH3KMJ');

  // ============================================================================
  // Yandex.Metrika (Яндекс.Метрика)
  // ID: 12345678
  // ============================================================================
  (function() {
    window.ym = window.ym || function(){
      (window.ym.a = window.ym.a || []).push(arguments);
    };
    window.ym.l = 1 * new Date();

    // Загружаем скрипт Метрики
    var script = document.createElement('script');
    script.type = 'text/javascript';
    script.src = 'https://mc.yandex.ru/metrika/tag.js';
    document.head.appendChild(script);

    // Инициализируем Метрику
    window.ym(12345678, 'init', {
      trackHash: true,
      clickmap: true,
      referrer: document.referrer,
      url: location.href,
      accurateTrackBounce: true,
      trackLinks: true
    });
  })();

})();

// window.dataLayer доступна через глобальную переменную

