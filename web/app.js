'use strict';

const STATUSES = ['결제완료', '상품준비중', '해외배송중', '통관중', '국내배송중', '배송완료'];
const STATE_ZH = { open: '待处理', replied: '已回复', handoff: '转人工' };
const SOURCE_ZH = {
  template: '按话术生成，数据来自右侧已核实内容',
  llm: '大模型在话术和已核实数据基础上改写',
  holding: '安抚话术，等人工处理',
  ask_order: '缺订单号，先向买家索取',
  ask_product: '缺商品信息，先向买家索取',
};
const RULE_TYPE_ZH = {
  keyword: '关键词', order_not_found: '订单不存在', overdue: '超期未到',
  low_confidence: '匹配度低', manual_script: '话术类别',
};

const state = { inquiries: [], filter: 'all', current: null, statusZh: {}, scripts: [], rules: [] };
const $ = (sel) => document.querySelector(sel);

function esc(v) {
  return String(v ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
}

async function api(path, method = 'GET', body) {
  const res = await fetch(path, {
    method,
    headers: body ? { 'Content-Type': 'application/json' } : undefined,
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!res.ok) throw new Error(`${method} ${path} -> ${res.status}`);
  return res.json();
}

let toastTimer;
function toast(msg) {
  const el = $('#toast');
  el.textContent = msg;
  el.hidden = false;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => { el.hidden = true; }, 1800);
}

/* ---------------------------------------------------------------- tabs --- */
$('#tabs').addEventListener('click', (e) => {
  const tab = e.target.dataset.tab;
  if (!tab) return;
  document.querySelectorAll('#tabs button').forEach((b) => b.classList.toggle('on', b === e.target));
  document.querySelectorAll('main > section').forEach((s) => { s.hidden = s.id !== `tab-${tab}`; });
  if (tab === 'scripts') loadScripts();
  if (tab === 'rules') loadRules();
  if (tab === 'eval' && !$('#eval-body').children.length) runEval();
});

/* ------------------------------------------------------------ inquiries --- */
async function loadInquiries() {
  const data = await api('/api/inquiries');
  state.inquiries = data.items;
  renderFilters();
  renderList();
}

function renderFilters() {
  const count = (s) => state.inquiries.filter((q) => s === 'all' || q.state === s).length;
  $('#filters').innerHTML = ['all', 'open', 'handoff', 'replied'].map((s) =>
    `<button class="chip ${state.filter === s ? 'on' : ''}" data-filter="${s}">${s === 'all' ? '全部' : STATE_ZH[s]} ${count(s)}</button>`).join('');
}

function renderList() {
  const rows = state.inquiries.filter((q) => state.filter === 'all' || q.state === state.filter);
  $('#inq-list').innerHTML = rows.map((q) => `
    <li data-id="${q.id}" class="${state.current === q.id ? 'on' : ''}">
      <div class="inq-top"><span>${esc(q.buyer)} · ${esc(q.channel)} · ${esc(q.created_at.slice(11))}</span>
        <span class="badge ${q.state}">${STATE_ZH[q.state]}</span></div>
      <div class="inq-text">${esc(q.text_ko)}</div>
      <div class="inq-zh">${esc(q.text_zh)}</div>
    </li>`).join('') || '<li class="empty">没有符合条件的咨询</li>';
}

$('#filters').addEventListener('click', (e) => {
  if (!e.target.dataset.filter) return;
  state.filter = e.target.dataset.filter;
  renderFilters();
  renderList();
});

$('#inq-list').addEventListener('click', (e) => {
  const li = e.target.closest('li[data-id]');
  if (li) openInquiry(li.dataset.id);
});

async function openInquiry(id) {
  state.current = id;
  renderList();
  const q = state.inquiries.find((x) => x.id === id);
  $('#work').innerHTML = '<div class="empty">正在生成回复…</div>';
  const res = await api('/api/reply', 'POST', { inquiry_id: id });
  renderWork(q, res);
  renderSide(res.facts);
}

/* ---------------------------------------------------------------- work --- */
function renderWork(q, res) {
  const h = res.handoff;
  const alert = h.required
    ? `<div class="alert warn"><b>需要人工处理</b>建议回复已换成安抚话术，不由系统直接答复具体问题。
        <ul>${h.reasons.map((r) => `<li>${esc(r.name)}：${esc(r.detail)}</li>`).join('')}</ul></div>`
    : `<div class="alert ok"><b>可直接回复</b>没有命中转人工规则。发送前请核对下方回复和右侧数据。</div>`;
  const top = res.matches[0];
  const note = top && top.note_zh ? `<div class="note">处理提示：${esc(top.note_zh)}</div>` : '';
  const t = res.timings_ms;
  const isReal = Boolean(q.id);

  $('#work').innerHTML = `
    <div class="card">
      <div class="q-meta">
        ${isReal ? `<span>${esc(q.id)}</span><span>${esc(q.buyer)}</span><span>${esc(q.channel)}</span><span>${esc(q.created_at.replace('T', ' '))}</span>` : '<span>手动输入</span>'}
        ${q.order_no ? `<span class="badge info">后台关联订单 ${esc(q.order_no)}</span>` : ''}
        ${q.product_code ? `<span class="badge info">后台关联商品 ${esc(q.product_code)}</span>` : ''}
        ${isReal ? `<span class="badge ${q.state}">${STATE_ZH[q.state]}</span>` : ''}
      </div>
      <div class="q-ko">${esc(q.text_ko)}</div>
      ${q.text_zh ? `<div class="q-zh">${esc(q.text_zh)}</div>` : ''}
    </div>
    ${alert}
    <div class="card">
      <h3>建议回复</h3>
      <div class="reply-grid">
        <textarea id="reply-ko" rows="8" lang="ko">${esc(res.reply.ko)}</textarea>
        <div class="zh-box">${esc(res.reply.zh || '（无中文对照）')}</div>
      </div>
      <div class="actions">
        <span class="src">来源：${esc(SOURCE_ZH[res.reply.source] || res.reply.source)}</span>
        <span class="grow"></span>
        <button class="btn" data-act="copy">复制韩语回复</button>
        ${isReal ? `<button class="btn warn" data-act="handoff">转人工</button>
        <button class="btn primary" data-act="replied">标记已回复</button>` : ''}
      </div>
    </div>
    <div class="card">
      <h3>匹配到的话术</h3>
      ${res.matches.map((m) => `
        <div class="match">
          <span>${esc(m.title)}${m.manual_only ? ' <span class="badge handoff">人工</span>' : ''}</span>
          <span class="bar"><i style="width:${Math.round(m.score * 100)}%"></i></span>
          <span class="score">${m.score.toFixed(2)}</span>
        </div>`).join('')}
      ${note}
    </div>
    <div class="card">
      <h3>各环节耗时（毫秒）</h3>
      <div class="timings">
        <span>提取并补全数据 ${t.facts}</span><span>话术检索 ${t.retrieve}</span>
        <span>规则判断 ${t.rules}</span><span>生成 ${t.generate}</span><span>合计 ${t.total}</span>
      </div>
    </div>`;

  $('#work').onclick = async (e) => {
    const act = e.target.dataset.act;
    if (!act) return;
    const text = $('#reply-ko').value;
    if (act === 'copy') {
      try { await navigator.clipboard.writeText(text); toast('已复制'); } catch { toast('复制失败，请手动选择文本'); }
      return;
    }
    const updated = await api(`/api/inquiries/${q.id}/state`, 'POST', { state: act, reply: text });
    Object.assign(q, updated);
    renderFilters();
    renderList();
    renderWork(q, res);
    toast(act === 'replied' ? '已标记为已回复' : '已转入人工队列');
  };
}

/* ---------------------------------------------------------------- side --- */
function orderCard(o, overdueDays = 0) {
  const idx = STATUSES.indexOf(o.status);
  return `<div class="card flat">
    <h3>订单</h3>
    <dl class="kv">
      <dt>订单号</dt><dd>${esc(o.order_no)}</dd>
      <dt>买家</dt><dd>${esc(o.buyer)} · ${esc(o.channel)}</dd>
      <dt>状态</dt><dd>${esc(o.status)}（${esc(state.statusZh[o.status] || '')}）${overdueDays > 3 ? ` <span class="badge handoff">超期 ${overdueDays} 天</span>` : ''}</dd>
      <dt>下单</dt><dd>${esc(o.ordered_at)}</dd>
      <dt>预计到货</dt><dd>${esc(o.eta)}${o.delivered_at ? `（签收 ${esc(o.delivered_at)}）` : ''}</dd>
      <dt>运单</dt><dd>${o.tracking_no ? `${esc(o.carrier)} ${esc(o.tracking_no)}` : '未发货'}</dd>
      <dt>通关号</dt><dd>${esc(o.customs_no.slice(0, 5))}****${esc(o.customs_no.slice(-4))}</dd>
      <dt>商品</dt><dd>${esc(o.product_code)} × ${o.qty}，₩${o.amount_krw.toLocaleString()}</dd>
    </dl>
    <div class="steps ${overdueDays > 3 ? 'late' : ''}">${STATUSES.map((_, i) => `<i class="${i <= idx ? 'done' : ''}"></i>`).join('')}</div>
  </div>`;
}

function productCard(p, inv, arrivals) {
  const free = inv ? inv.on_hand - inv.reserved : null;
  return `<div class="card flat">
    <h3>商品与库存</h3>
    <dl class="kv">
      <dt>编码</dt><dd>${esc(p.code)}</dd>
      <dt>名称</dt><dd>${esc(p.name_ko)}（${esc(p.name_zh)}）</dd>
      ${inv ? `<dt>库存</dt><dd>在库 ${inv.on_hand}，已占用 ${inv.reserved}，可用 ${free} ${free > 0 ? '' : '<span class="badge handoff">缺货</span>'}</dd>
      <dt>下次到货</dt><dd>${inv.next_arrival_date ? `${esc(inv.next_arrival_date)}，${inv.next_arrival_qty} 件` : '无计划'}</dd>` : ''}
    </dl>
    ${arrivals && arrivals.length ? `<table class="mini">${arrivals.slice(0, 5).map((a) =>
      `<tr><td>${esc(a.date)}</td><td>${a.qty} 件</td><td>${esc(a.state)}</td></tr>`).join('')}</table>` : ''}
  </div>`;
}

function renderSide(f) {
  let html = '';
  if (f.missing_orders.length) {
    html += `<div class="card flat"><div class="alert warn" style="margin:0"><b>查不到订单</b>${f.missing_orders.map(esc).join('、')}</div></div>`;
  }
  if (f.order) html += orderCard(f.order, f.overdue_days);
  if (f.product) html += productCard(f.product, f.inventory, f.arrivals);
  $('#side-body').innerHTML = html || '<div class="empty">这条咨询没有关联到订单或商品。</div>';
}

$('#lookup-form').addEventListener('submit', async (e) => {
  e.preventDefault();
  const q = $('#lookup-q').value.trim();
  if (!q) return;
  const res = await api(`/api/lookup?q=${encodeURIComponent(q)}`);
  const html = res.orders.map((o) => orderCard(o)).join('') +
    res.products.map((p) => productCard(p, p.inventory, p.arrivals)).join('');
  $('#side-body').innerHTML = html || `<div class="empty">没有查到“${esc(q)}”。</div>`;
});

/* -------------------------------------------------------- manual input --- */
$('#btn-manual').addEventListener('click', () => {
  $('#dlg-form').innerHTML = `
    <h2>手动输入一条咨询</h2>
    <div class="field"><label>咨询内容（韩语）</label>
      <textarea name="text" rows="4" lang="ko" required placeholder="예: 주문번호 20261110-12345 배송 언제 되나요?"></textarea></div>
    <div class="row2">
      <div class="field"><label>关联订单号（可空）</label><input name="order_no"></div>
      <div class="field"><label>关联商品编码（可空）</label><input name="product_code"></div>
    </div>
    <div class="dlg-actions"><button class="btn" value="cancel" formnovalidate>取消</button><button class="btn primary" value="ok">生成回复</button></div>`;
  const dlg = $('#dlg');
  dlg.onclose = async () => {
    if (dlg.returnValue !== 'ok') return;
    const fd = new FormData($('#dlg-form'));
    const q = { text_ko: fd.get('text').trim(), order_no: fd.get('order_no').trim() || null, product_code: fd.get('product_code').trim() || null };
    if (!q.text_ko) return;
    state.current = null;
    renderList();
    const res = await api('/api/reply', 'POST', { text: q.text_ko, order_no: q.order_no, product_code: q.product_code });
    renderWork(q, res);
    renderSide(res.facts);
  };
  dlg.showModal();
});

/* -------------------------------------------------------------- scripts --- */
async function loadScripts() {
  state.scripts = (await api('/api/scripts')).items;
  $('#script-list').innerHTML = state.scripts.map((s) => `
    <div class="card ${s.enabled ? '' : 'off'}">
      <div class="card-top"><b>${esc(s.title)}</b>
        <span>${s.manual_only ? '<span class="badge handoff">人工</span> ' : ''}<span class="badge open">${esc(s.category_zh)}</span></span></div>
      <ul class="examples">${s.examples.slice(0, 3).map((x) => `<li lang="ko">${esc(x)}</li>`).join('')}</ul>
      <div class="reply-prev" lang="ko">${esc(s.reply_ko)}</div>
      <div class="card-top"><span class="src">${esc(s.id)} · 需要数据：${s.requires.length ? s.requires.map((r) => (r === 'order' ? '订单' : '商品')).join('、') : '无'}</span>
        <button class="btn small" data-edit="${s.id}">编辑</button></div>
    </div>`).join('');
}

function scriptDialog(s) {
  const isNew = !s;
  s = s || { category: '', category_zh: '', title: '', examples: [], keywords: [], requires: [], reply_ko: '', reply_zh: '', note_zh: '', manual_only: false, enabled: true };
  $('#dlg-form').innerHTML = `
    <h2>${isNew ? '新增话术' : `编辑话术 ${esc(s.id)}`}</h2>
    <div class="row2">
      <div class="field"><label>标题</label><input name="title" value="${esc(s.title)}" required></div>
      <div class="row2">
        <div class="field"><label>类别（中文）</label><input name="category_zh" value="${esc(s.category_zh)}" required></div>
        <div class="field"><label>类别代码</label><input name="category" value="${esc(s.category)}" required></div>
      </div>
    </div>
    <div class="row2">
      <div class="field"><label>示例问法（韩语，每行一条，用于检索）</label><textarea name="examples" rows="4" lang="ko">${esc(s.examples.join('\n'))}</textarea></div>
      <div class="field"><label>关键词（每行一个，命中有加分）</label><textarea name="keywords" rows="4" lang="ko">${esc(s.keywords.join('\n'))}</textarea></div>
    </div>
    <div class="row2">
      <div class="field"><label>韩语回复模板</label><textarea name="reply_ko" rows="6" lang="ko" required>${esc(s.reply_ko)}</textarea></div>
      <div class="field"><label>中文对照</label><textarea name="reply_zh" rows="6">${esc(s.reply_zh)}</textarea></div>
    </div>
    <p class="hint">可用占位符：{order_no} {progress_line} {eta_line} {tracking_line} {customs_line} {product_ref} {product_name} {stock_line}</p>
    <div class="field"><label>给客服的处理提示</label><input name="note_zh" value="${esc(s.note_zh)}"></div>
    <div class="checks">
      <label><input type="checkbox" name="req_order" ${s.requires.includes('order') ? 'checked' : ''}> 需要订单数据</label>
      <label><input type="checkbox" name="req_product" ${s.requires.includes('product') ? 'checked' : ''}> 需要商品数据</label>
      <label><input type="checkbox" name="manual_only" ${s.manual_only ? 'checked' : ''}> 只能人工处理</label>
      <label><input type="checkbox" name="enabled" ${s.enabled ? 'checked' : ''}> 启用</label>
    </div>
    <div class="dlg-actions">
      ${isNew ? '' : '<button class="btn warn" value="delete" formnovalidate>删除</button>'}
      <span class="grow" style="flex:1"></span>
      <button class="btn" value="cancel" formnovalidate>取消</button><button class="btn primary" value="ok">保存</button>
    </div>`;
  const dlg = $('#dlg');
  dlg.onclose = async () => {
    if (dlg.returnValue === 'delete') {
      await api(`/api/scripts/${s.id}`, 'DELETE');
      toast('已删除');
    } else if (dlg.returnValue === 'ok') {
      const fd = new FormData($('#dlg-form'));
      const lines = (k) => fd.get(k).split('\n').map((x) => x.trim()).filter(Boolean);
      const body = {
        title: fd.get('title').trim(), category: fd.get('category').trim(), category_zh: fd.get('category_zh').trim(),
        examples: lines('examples'), keywords: lines('keywords'),
        requires: [fd.get('req_order') ? 'order' : null, fd.get('req_product') ? 'product' : null].filter(Boolean),
        reply_ko: fd.get('reply_ko'), reply_zh: fd.get('reply_zh'), note_zh: fd.get('note_zh').trim(),
        manual_only: Boolean(fd.get('manual_only')), enabled: Boolean(fd.get('enabled')),
      };
      await api(isNew ? '/api/scripts' : `/api/scripts/${s.id}`, isNew ? 'POST' : 'PUT', body);
      toast('已保存，检索索引已更新');
    } else {
      return;
    }
    $('#eval-body').innerHTML = '';
    loadScripts();
  };
  dlg.showModal();
}

$('#btn-new-script').addEventListener('click', () => scriptDialog(null));
$('#script-list').addEventListener('click', (e) => {
  const id = e.target.dataset.edit;
  if (id) scriptDialog(state.scripts.find((s) => s.id === id));
});

/* ---------------------------------------------------------------- rules --- */
function ruleCondition(r) {
  if (r.type === 'keyword') {
    const all = (r.all || []).map((k) => `<span class="kw" lang="ko">${esc(k)}</span>`).join('');
    const any = (r.any || []).map((k) => `<span class="kw" lang="ko">${esc(k)}</span>`).join('');
    return `${all ? `同时包含 ${all}<br>` : ''}${any ? `包含任意一个 ${any}` : ''}`;
  }
  if (r.type === 'order_not_found') return '咨询里写了订单号，但数据里查不到';
  if (r.type === 'overdue') return `订单超过预计到货日 ${r.days} 天仍未签收`;
  if (r.type === 'low_confidence') return `最相近话术的相似度低于 ${r.threshold}`;
  if (r.type === 'manual_script') return '最相近的话术被标为“只能人工处理”';
  return '';
}

async function loadRules() {
  state.rules = (await api('/api/rules')).items;
  $('#rule-table').innerHTML = `<tr><th style="width:56px">编号</th><th style="width:160px">名称</th><th style="width:96px">类型</th><th>触发条件</th><th style="width:72px">启用</th></tr>` +
    state.rules.map((r) => `<tr>
      <td>${esc(r.id)}</td><td>${esc(r.name)}</td><td>${esc(RULE_TYPE_ZH[r.type] || r.type)}</td>
      <td>${ruleCondition(r)}</td>
      <td><input type="checkbox" data-rule="${r.id}" ${r.enabled ? 'checked' : ''}></td></tr>`).join('');
}

$('#rule-table').addEventListener('change', async (e) => {
  const id = e.target.dataset.rule;
  if (!id) return;
  await api(`/api/rules/${id}`, 'PATCH', { enabled: e.target.checked });
  $('#eval-body').innerHTML = '';
  toast(e.target.checked ? '规则已启用' : '规则已停用');
});

/* ----------------------------------------------------------------- eval --- */
const pct = (v) => `${(v * 100).toFixed(1)}%`;

async function runEval() {
  $('#eval-body').innerHTML = '<div class="empty">正在评测…</div>';
  const r = await api('/api/eval');
  const h = r.handoff;
  $('#eval-body').innerHTML = `
    <div class="stats">
      <div class="stat"><div class="n">${pct(r.retrieval_top1)}</div><div class="l">话术检索：第一条就是正确类别（共 ${r.count} 条）</div></div>
      <div class="stat"><div class="n">${pct(r.retrieval_top3)}</div><div class="l">话术检索：前三条包含正确类别</div></div>
      <div class="stat"><div class="n">${pct(h.recall)}</div><div class="l">转人工召回：该转的 ${h.tp + h.fn} 条里转了 ${h.tp} 条</div></div>
      <div class="stat"><div class="n">${pct(h.precision)}</div><div class="l">转人工准确：转了 ${h.tp + h.fp} 条，其中 ${h.fp} 条本可直接回复</div></div>
    </div>
    <h3>没有完全命中的咨询（${r.misses.length} 条）</h3>
    ${r.misses.length ? `<table class="table">
      <tr><th style="width:64px">编号</th><th>咨询</th><th style="width:150px">期望类别</th><th style="width:150px">实际第一条</th><th style="width:110px">转人工</th></tr>
      ${r.misses.map((m) => `<tr><td>${esc(m.id)}</td>
        <td><span lang="ko">${esc(m.text_ko)}</span><br><span class="src">${esc(m.text_zh)}</span></td>
        <td>${esc(m.expected_category)}</td><td>${esc(m.got_category)}</td>
        <td>${m.expected_handoff === m.got_handoff ? '一致' : `期望 ${m.expected_handoff ? '转' : '不转'}，实际 ${m.got_handoff ? '转' : '不转'}`}</td></tr>`).join('')}
    </table>` : '<div class="empty">全部命中。</div>'}`;
}
$('#btn-eval').addEventListener('click', runEval);

/* ----------------------------------------------------------------- boot --- */
(async function boot() {
  const h = await api('/api/health');
  state.statusZh = h.status_zh;
  $('#meta').textContent = `演示日期 ${h.demo_date} · 订单 ${h.counts.orders} · 话术 ${h.counts.scripts} · 生成方式：${h.generator === 'llm' ? `大模型（${h.model}）` : '模板'}`;
  await loadInquiries();
  const linked = decodeURIComponent(location.hash.slice(1));
  if (state.inquiries.some((q) => q.id === linked)) openInquiry(linked);
})();
