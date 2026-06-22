// public/custom-header.js — v0.3.0 Day 11
// Day 11 改造:折叠从 width 切到 transform: translateX,豆包风格
// + 注入浮动折叠按钮(fixed 在 main 左上角),sidebar 滑出后仍可点
//
// 历史:
//   Day 9: SessionSidebar 钉左侧 280px + 主对话右移
//   Day 10: Bug 2 三轮(键盘/IME/search),1000ms 轮询
//   Day 11: 折叠改 transform 滑出 + FAB 浮动按钮

(function () {
  function injectCSS() {
    if (document.getElementById('custom-header-style')) return;
    var style = document.createElement('style');
    style.id = 'custom-header-style';
    style.textContent = [
      // 1. header 设置按钮左移(原 Day 7)
      '#header button:has(> a[href="/settings"]) {',
      '  order: -1 !important;',
      '  margin-right: auto !important;',
      '}',
      '#header a[href="/settings"] {',
      '  order: -1 !important;',
      '}',
      // 2. SessionSidebar 钉左侧 280px(防御 Chainlit flex 容器覆盖)
      //    Day 11 改:width 永远 280px,折叠用 transform 滑出
      '[data-sidebar="1"] {',
      '  position: fixed !important;',
      '  left: 0 !important;',
      '  top: 0 !important;',
      '  bottom: 0 !important;',
      '  width: 280px !important;',
      '  z-index: 50 !important;',
      '  display: flex !important;',
      '  flex-direction: column !important;',
      '  background: #f6f8fa !important;',
      '  border-right: 1px solid #d0d7de !important;',
      '  overflow: hidden !important;',
      '  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "PingFang SC", "Hiragino Sans GB", "Microsoft YaHei", sans-serif !important;',
      '  transform: translateX(0) !important;',
      '  transition: transform 200ms ease !important;',
      '}',
      // 3. 折叠态:transform 滑出 title 列(留 60px avatar 列在屏左)
      //    原 width: 60px 切会让 layout 重新计算导致抖动
      //    改 transform 后 sidebar DOM 不动,只是视觉滑出 220px(=280-60)
      //    Day 11 修:selector 加 [data-sidebar="1"] 限定,避免 body / 其他元素被误匹配
      //    (body 也有 data-sidebar-collapsed,旧 selector 会把整个 body 偏移 -220px → FAB 也被拖到屏外)
      '[data-sidebar="1"][data-sidebar-collapsed="1"] {',
      '  transform: translateX(-220px) !important;',
      '}',
      // 4. 主对话区右移 280px(避免被 sidebar 覆盖)— Day 11 改用 margin-left
      //    之前用 body padding-left,导致折叠时整个页面 content 跟着移动
      //    现在 main 元素用 margin-left 留位置,折叠时归 60(对齐 avatar 列)
      //    Day 11 hotfix 2:用 body.sidebar-collapsed class 替代 body[data-sidebar-collapsed] attribute
      //    class 不会被 CSS [attr] selector 误匹配(避免再次 body 被 transform 拖走)
      '.chainlit-container, #main, main, [class*="MuiBox-root"]:has(> [class*="Step"]) {',
      '  margin-left: 280px !important;',
      '  transition: margin-left 200ms ease !important;',
      '}',
      'body.sidebar-collapsed .chainlit-container,',
      'body.sidebar-collapsed #main,',
      'body.sidebar-collapsed main {',
      '  margin-left: 60px !important;',
      '}',
      // 5. Settings 弹层 / Header 按钮保持在 sidebar 上方(z-index > 50)
      '#header { z-index: 100 !important; position: relative !important; }',
      '.cl-modal { z-index: 200 !important; }',
      // 6. Day 11 新增:浮动折叠按钮(fixed 在 sidebar 右边)
      //    展开时贴在 sidebar 右边 12px (=280+12)
      //    折叠后 avatar 列 60px 还在屏左,按钮贴在 60px sidebar 右边 (=60+12)
      '#sidebar-toggle-fab {',
      '  position: fixed !important;',
      '  left: 292px !important;',
      '  top: 12px !important;',
      '  z-index: 150 !important;',  // Day 11 hotfix 3:必须 > #header z-index(100),否则 header 拦截 click
      '  width: 32px !important;',
      '  height: 32px !important;',
      '  border-radius: 8px !important;',
      '  background: #ffffff !important;',
      '  border: 1px solid #d0d7de !important;',
      '  cursor: pointer !important;',
      '  display: flex !important;',
      '  align-items: center !important;',
      '  justify-content: center !important;',
      '  font-size: 14px !important;',
      '  color: #57606a !important;',
      '  box-shadow: 0 1px 3px rgba(0,0,0,0.08) !important;',
      '  transition: left 200ms ease, background 0.15s ease !important;',
      '  padding: 0 !important;',
      '  font-family: inherit !important;',
      '}',
      '#sidebar-toggle-fab:hover { background: #f6f8fa !important; }',
      // 折叠后按钮移到 60px sidebar 右边
      // Day 11 hotfix 2: 用 body.sidebar-collapsed class
      'body.sidebar-collapsed #sidebar-toggle-fab {',
      '  left: 72px !important;',  // 60(avatar 列宽)+ 12 gap
      '}',
      // 折叠态按钮的 icon 旋转(☰ → ✕)
      '#sidebar-toggle-fab[data-collapsed="1"] {',
      '  transform: rotate(180deg) !important;',
      '}',
    ].join('\n');
    document.head.appendChild(style);
  }

  // 注入浮动折叠按钮(只在第一次调用时建)
  function injectFab() {
    if (document.getElementById('sidebar-toggle-fab')) return;
    var btn = document.createElement('button');
    btn.id = 'sidebar-toggle-fab';
    btn.type = 'button';
    btn.title = '收起/展开侧边栏 (Ctrl+B)';
    btn.setAttribute('aria-label', '收起/展开侧边栏');
    btn.textContent = '☰';
    // 点击 → 派发 window 事件(SessionSidebar 监听)
    btn.addEventListener('click', function () {
      window.dispatchEvent(new CustomEvent('sidebar:toggle'));
    });
    // 同步按钮状态(Day 11 hotfix 2:用 body.sidebar-collapsed class 而非 attribute)
    var syncFabState = function () {
      var collapsed = document.body.classList.contains('sidebar-collapsed');
      btn.setAttribute('data-collapsed', collapsed ? '1' : '0');
      btn.textContent = collapsed ? '✕' : '☰';
    };
    syncFabState();
    // 监听 body class 变化(1000ms 轮询会触发)
    var observer = new MutationObserver(syncFabState);
    observer.observe(document.body, { attributes: true, attributeFilter: ['class'] });
    btn._observer = observer;
    document.body.appendChild(btn);
  }

  function syncBodyPadding() {
    // Day 11 hotfix 2: 不再需要双向同步 collapsed state
    // SessionSidebar 改用 document.body.classList.toggle('sidebar-collapsed', collapsed)
    // 直接设 class,这里只做兜底检查(防御 React state 被外部 reset)
    var sidebarCollapsed = document.querySelector('[data-sidebar="1"][data-sidebar-collapsed="1"]') !== null;
    var bodyHasClass = document.body.classList.contains('sidebar-collapsed');
    if (sidebarCollapsed && !bodyHasClass) {
      document.body.classList.add('sidebar-collapsed');
    } else if (!sidebarCollapsed && bodyHasClass) {
      document.body.classList.remove('sidebar-collapsed');
    }
  }

  function init() {
    injectCSS();
    injectFab();
    syncBodyPadding();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }

  // v0.3.0 Day 10 修 Bug 2 三轮: 1000ms 轮询(从 200ms 降回)+ syncBodyPadding 早返回
  // Day 11 保留同样节奏,只是 CSS 改成 transform 后,layout invalidation 更少
  setInterval(init, 1000);

  // v0.3.0 Day 10: 监听 Chainlit window_message,转发为 sessions-updated DOM 事件
  // Day 11 保留
  (function () {
    window.addEventListener('message', function (ev) {
      var data = ev.data;
      if (!data || typeof data !== 'object') return;
      if (data.type === 'sessions_changed' || data.type === 'sessions_ready') {
        window.dispatchEvent(new CustomEvent('sessions-updated', { detail: data }));
      }
    });
  })();

  // Day 11 新增:Ctrl+B / Cmd+B 全局快捷键(对齐 VS Code)
  document.addEventListener('keydown', function (e) {
    var k = (e.key || '').toLowerCase();
    var modKey = e.ctrlKey || e.metaKey;
    if (!modKey) return;
    if (e.isComposing || e.keyCode === 229) return;
    if (k === 'b' && !e.shiftKey && !e.altKey) {
      var tag = (document.activeElement && document.activeElement.tagName) || '';
      // 输入框里不抢(允许正常 Ctrl+B 文字编辑)
      if (tag === 'INPUT' || tag === 'TEXTAREA') return;
      e.preventDefault();
      window.dispatchEvent(new CustomEvent('sidebar:toggle'));
    }
  });
})();