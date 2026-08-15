"""自定义右键菜单注入脚本：跳转到目标网页后由控制器通过 evaluate_js 注入页面。

脚本在 capture 阶段全局拦截 contextmenu 事件，替换目标网页自身的右键菜单，
渲染内置自定义菜单（刷新页面 / 复制 / 粘贴 / 打开配置页）。脚本幂等：
以 window.__wbdContextMenuInjected 标记防止整页刷新、导航后重复注入。

关键设计：右键弹出时快照焦点元素、光标位置与选区文本，菜单交互期间
pointerdown 阻止默认行为（防止输入框失焦、选区被清除），复制 / 粘贴均基于
快照执行，保证点击菜单项后仍能作用于正确的元素与位置。
"""

# 注入脚本：挂载点选 documentElement（框架重渲染不会清理该节点），
# 菜单渲染在 Shadow DOM 中，与目标页面样式完全隔离。
CONTEXT_MENU_SCRIPT = """
(function () {
  'use strict';
  // 幂等保护：整页刷新 / 导航后由 loaded 事件再次注入时直接跳过
  if (window.__wbdContextMenuInjected) { return; }
  window.__wbdContextMenuInjected = true;

  // 宿主节点 + Shadow DOM（菜单结构一次性构建，菜单项每次显示时重建）
  var host = document.createElement('div');
  host.setAttribute('data-wbd-context-menu', '1');
  var shadow = host.attachShadow({ mode: 'open' });
  shadow.innerHTML = '' +
    '<style>' +
    '  :host { all: initial; }' +
    '  .wrap { position: fixed; left: 0; top: 0; z-index: 2147483647; display: none; }' +
    '  .menu { min-width: 188px; padding: 6px; border-radius: 10px; background: #ffffff;' +
    '          border: 1px solid #e2e8f0; box-shadow: 0 12px 32px rgba(15, 23, 42, 0.18);' +
    '          font: 13px/1.6 "Segoe UI", "Microsoft YaHei", sans-serif; color: #1f2937; }' +
    '  .item { display: flex; align-items: center; gap: 10px; padding: 8px 10px;' +
    '          border-radius: 7px; cursor: pointer; user-select: none; white-space: nowrap; }' +
    '  .item:hover { background: #f1f5f9; color: #0f172a; }' +
    '  .icon { width: 18px; text-align: center; opacity: 0.85; }' +
    '  .sep { height: 1px; margin: 6px 8px; background: #e2e8f0; }' +
    '</style>' +
    '<div class="wrap"><div class="menu" role="menu"></div></div>';

  var wrap = shadow.querySelector('.wrap');
  var menu = shadow.querySelector('.menu');
  (document.body || document.documentElement).appendChild(host);

  // 强制启用文本选择：目标网页通常自带 user-select:none，放开后才可用「复制」菜单项；
  // 排除按钮、链接、表单控件等交互元素，避免误选
  var selectStyle = document.createElement('style');
  selectStyle.setAttribute('data-wbd-select-style', '1');
  selectStyle.textContent =
    '* { -webkit-user-select: text !important; user-select: text !important; }' +
    'button, a, input, textarea, select, label, summary, [role="button"], [data-wbd-context-menu]' +
    ' { -webkit-user-select: none !important; user-select: none !important; }';
  (document.head || document.documentElement).appendChild(selectStyle);

  var open = false;
  // 右键弹出时刻的状态快照（点击菜单项会破坏实时焦点与选区，动作必须基于快照）
  var snapshot = { editable: null, selectionText: '', range: null, selStart: 0, selEnd: 0 };

  function closeMenu() {
    if (!open) { return; }
    open = false;
    wrap.style.display = 'none';
  }

  // 判断元素是否为可粘贴文本的可编辑元素
  function isEditable(el) {
    if (!el) { return false; }
    var tag = el.tagName;
    if (tag === 'INPUT') {
      var type = (el.type || 'text').toLowerCase();
      return type !== 'checkbox' && type !== 'radio' && type !== 'button' &&
        type !== 'submit' && type !== 'file' && !el.disabled && !el.readOnly;
    }
    if (tag === 'TEXTAREA') { return !el.disabled && !el.readOnly; }
    return !!el.isContentEditable;
  }

  // 右键弹出时快照焦点元素、光标位置与选区文本
  function captureSnapshot() {
    var el = document.activeElement;
    snapshot.editable = isEditable(el) ? el : null;
    snapshot.range = null;
    snapshot.selStart = 0;
    snapshot.selEnd = 0;
    var sel = window.getSelection();
    snapshot.selectionText = sel ? String(sel) : '';
    if (!snapshot.editable) { return; }
    var tag = snapshot.editable.tagName;
    if (tag === 'INPUT' || tag === 'TEXTAREA') {
      snapshot.selStart = typeof snapshot.editable.selectionStart === 'number'
        ? snapshot.editable.selectionStart : 0;
      snapshot.selEnd = typeof snapshot.editable.selectionEnd === 'number'
        ? snapshot.editable.selectionEnd : snapshot.selStart;
    } else if (sel && sel.rangeCount > 0) {
      var range = sel.getRangeAt(0);
      // 仅保存位于该可编辑元素内部的选区，避免把无关选区带入粘贴
      if (snapshot.editable.contains(range.commonAncestorContainer)) {
        snapshot.range = range.cloneRange();
      }
    }
  }

  function hasSnapshotSelection() {
    return snapshot.selectionText.trim().length > 0;
  }

  // 剪贴板 API 不可用时的复制回退方案
  function fallbackCopy(text) {
    var ta = document.createElement('textarea');
    ta.value = text;
    ta.style.position = 'fixed';
    ta.style.left = '-9999px';
    document.body.appendChild(ta);
    ta.focus();
    ta.select();
    try { document.execCommand('copy'); } catch (e) { /* 忽略回退失败 */ }
    document.body.removeChild(ta);
  }

  // 复制：使用快照文本（点击菜单项后实时选区可能已被清除）
  function copySelection() {
    var text = snapshot.selectionText;
    if (!text) { return; }
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(text).catch(function () { fallbackCopy(text); });
    } else {
      fallbackCopy(text);
    }
  }

  // 使用原型上的原生 setter 赋值并派发 input 事件（兼容 React 受控组件）
  function setNativeValue(el, value) {
    var proto = el.tagName === 'TEXTAREA'
      ? window.HTMLTextAreaElement.prototype
      : window.HTMLInputElement.prototype;
    var setter = Object.getOwnPropertyDescriptor(proto, 'value').set;
    setter.call(el, value);
    el.dispatchEvent(new Event('input', { bubbles: true }));
  }

  // 恢复焦点与光标到快照位置（点击菜单项已使输入框失焦、选区丢失）
  function restoreCaret(el) {
    el.focus();
    var tag = el.tagName;
    if (tag === 'INPUT' || tag === 'TEXTAREA') {
      try { el.setSelectionRange(snapshot.selStart, snapshot.selEnd); } catch (e) { /* 忽略 */ }
    } else if (snapshot.range) {
      var sel = window.getSelection();
      sel.removeAllRanges();
      sel.addRange(snapshot.range);
    }
  }

  // 向 input/textarea 的快照光标位置插入文本
  function insertIntoField(el, text) {
    var start = snapshot.selStart;
    var end = snapshot.selEnd;
    setNativeValue(el, el.value.slice(0, start) + text + el.value.slice(end));
    try { el.setSelectionRange(start + text.length, start + text.length); } catch (e) { /* 忽略 */ }
  }

  // 向 contenteditable 插入文本：Range API 直插文本节点（比 execCommand 可靠），
  // 插入后派发 input 事件让 React 等框架感知变化
  function insertIntoContentEditable(el, text) {
    var sel = window.getSelection();
    var range = null;
    if (sel && sel.rangeCount > 0) {
      var current = sel.getRangeAt(0);
      if (el.contains(current.commonAncestorContainer)) { range = current; }
    }
    if (!range) {
      // 无有效选区：光标置于元素末尾
      range = document.createRange();
      range.selectNodeContents(el);
      range.collapse(false);
    }
    range.deleteContents();
    var textNode = document.createTextNode(text);
    range.insertNode(textNode);
    // 光标移到插入文本之后
    range.setStartAfter(textNode);
    range.collapse(true);
    sel.removeAllRanges();
    sel.addRange(range);
    try {
      el.dispatchEvent(new InputEvent('input', {
        bubbles: true, composed: true, inputType: 'insertText', data: text
      }));
    } catch (e) {
      el.dispatchEvent(new Event('input', { bubbles: true }));
    }
  }

  // 页面顶部短暂显示提示（粘贴失败 / 剪贴板为空等异步结果反馈）
  function flashToast(text) {
    var toast = document.createElement('div');
    toast.setAttribute('data-wbd-toast', '1');
    var toastShadow = toast.attachShadow({ mode: 'open' });
    toastShadow.innerHTML = '' +
      '<style>' +
      '  :host { all: initial; }' +
      '  .toast { position: fixed; left: 50%; top: 24px; transform: translateX(-50%);' +
      '           z-index: 2147483647; background: #1f2937; color: #ffffff;' +
      '           padding: 8px 16px; border-radius: 8px;' +
      '           font: 13px/1.5 "Segoe UI", "Microsoft YaHei", sans-serif;' +
      '           box-shadow: 0 8px 24px rgba(15, 23, 42, 0.35); white-space: nowrap; }' +
      '</style>' +
      '<div class="toast"></div>';
    toastShadow.querySelector('.toast').textContent = text;
    (document.body || document.documentElement).appendChild(toast);
    setTimeout(function () {
      if (toast.parentNode) { toast.parentNode.removeChild(toast); }
    }, 1600);
  }

  // 经 Python 端读取剪贴板（规避 WebView2 的 Clipboard 读权限限制）
  function pasteClipboard() {
    var el = snapshot.editable;
    if (!el || !document.contains(el)) { return; }
    if (!window.pywebview || !window.pywebview.api || !window.pywebview.api.get_clipboard_text) {
      flashToast('粘贴不可用');
      return;
    }
    window.pywebview.api.get_clipboard_text().then(function (text) {
      if (typeof text !== 'string' || text.length === 0) {
        flashToast('剪贴板为空');
        return;
      }
      restoreCaret(el);
      var tag = el.tagName;
      if (tag === 'INPUT' || tag === 'TEXTAREA') {
        insertIntoField(el, text);
      } else if (el.isContentEditable) {
        try {
          insertIntoContentEditable(el, text);
        } catch (e) {
          // 兜底：Range API 失败时退回 execCommand
          try { document.execCommand('insertText', false, text); } catch (e2) { /* 忽略 */ }
        }
      }
    }).catch(function () {
      flashToast('粘贴失败');
    });
  }

  function openConfig() {
    if (window.pywebview && window.pywebview.api && window.pywebview.api.open_config_page) {
      window.pywebview.api.open_config_page('web');
    }
  }

  // 菜单项定义：always 恒显示；when 基于快照判断；group 相同的相邻项归为一组
  var ITEMS = [
    { id: 'reload', group: 0, icon: '🔄', label: '刷新页面', always: true,
      run: function () { window.location.reload(); } },
    { id: 'copy', group: 1, icon: '📄', label: '复制', when: hasSnapshotSelection, run: copySelection },
    { id: 'paste', group: 1, icon: '📋', label: '粘贴',
      when: function () { return snapshot.editable !== null; }, run: pasteClipboard },
    { id: 'config', group: 2, icon: '⚙️', label: '打开配置页', always: true, run: openConfig }
  ];

  // 按当前上下文重建菜单项（分组间插入分隔线）
  function buildMenu() {
    while (menu.firstChild) { menu.removeChild(menu.firstChild); }
    var lastGroup = null;
    ITEMS.forEach(function (item) {
      if (!(item.always || item.when())) { return; }
      if (item.group !== lastGroup) {
        if (menu.firstChild) {
          var sep = document.createElement('div');
          sep.className = 'sep';
          menu.appendChild(sep);
        }
        lastGroup = item.group;
      }
      var row = document.createElement('div');
      row.className = 'item';
      row.setAttribute('role', 'menuitem');
      row.setAttribute('data-wbd-menu-item', item.id);
      // 阻止默认行为：防止点击菜单项导致输入框失焦、选区被清除
      row.addEventListener('pointerdown', function (event) { event.preventDefault(); });
      var icon = document.createElement('span');
      icon.className = 'icon';
      icon.textContent = item.icon;
      var label = document.createElement('span');
      label.textContent = item.label;
      row.appendChild(icon);
      row.appendChild(label);
      row.addEventListener('click', function () {
        closeMenu();
        try { item.run(); } catch (e) { /* 动作异常不阻塞后续使用 */ }
      });
      menu.appendChild(row);
    });
  }

  // 定位并显示菜单（先隐藏测量尺寸，修正位置后展示，防止溢出视口边缘）
  function showMenu(x, y) {
    captureSnapshot();
    buildMenu();
    if (!menu.firstChild) { closeMenu(); return; }
    wrap.style.display = 'block';
    wrap.style.visibility = 'hidden';
    var rect = wrap.getBoundingClientRect();
    var left = Math.max(4, Math.min(x, window.innerWidth - rect.width - 4));
    var top = Math.max(4, Math.min(y, window.innerHeight - rect.height - 4));
    wrap.style.left = left + 'px';
    wrap.style.top = top + 'px';
    wrap.style.visibility = 'visible';
    open = true;
  }

  // capture 阶段拦截，替换目标网页自身的右键菜单
  document.addEventListener('contextmenu', function (event) {
    event.preventDefault();
    event.stopPropagation();
    showMenu(event.clientX, event.clientY);
  }, true);

  // 点击菜单外部（含 Shadow DOM 穿透的 composedPath 判断）时关闭菜单
  document.addEventListener('pointerdown', function (event) {
    if (!open) { return; }
    var path = event.composedPath ? event.composedPath() : [];
    if (path.indexOf(host) === -1) { closeMenu(); }
  }, true);

  document.addEventListener('scroll', closeMenu, true);
  window.addEventListener('resize', closeMenu);
  window.addEventListener('blur', closeMenu);
  document.addEventListener('keydown', function (event) {
    if (event.key === 'Escape') { closeMenu(); }
  }, true);
})();
"""
