// 把 header 里的"⚙️ 设置"挪到"说明"按钮**左边**
// 用 CSS order 实现(React 重渲染不会覆盖 CSS 顺序)
(function () {
  function injectCSS() {
    if (document.getElementById('custom-header-style')) return;
    var style = document.createElement('style');
    style.id = 'custom-header-style';
    style.textContent = [
      // 找到包含 /settings 链接的 flex item,移到最左
      '#header button:has(> a[href="/settings"]) {',
      '  order: -1 !important;',
      '  margin-right: auto !important;',
      '}',
      // 容错:某些 React 渲染层级下 link 是直接 flex item
      '#header a[href="/settings"] {',
      '  order: -1 !important;',
      '}'
    ].join('\n');
    document.head.appendChild(style);
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', injectCSS);
  } else {
    injectCSS();
  }
  // SPA 路由切换后 #header 可能被替换,每 1.5s 补一次
  setInterval(injectCSS, 1500);
})();