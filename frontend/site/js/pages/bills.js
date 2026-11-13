import { api } from '../api.js';
import { adjustTone, batchTone, can } from '../config.js';
import { badge, drawer, errorBox, errorMessage, esc, field, fmtMoney, fmtTime, statStrip, table, toast } from '../ui.js';

const state = {
  batchNo: '',
  draftKey: '',
  lastResult: null, // 最近一次入账结果（成功或失败），重渲染后仍然保留
};

function newKey() {
  if (window.crypto && crypto.randomUUID) return crypto.randomUUID();
  return `key-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 10)}`;
}

function suggestBatchNo(base) {
  const now = new Date();
  const ymd = `${now.getFullYear()}${String(now.getMonth() + 1).padStart(2, '0')}${String(now.getDate()).padStart(2, '0')}`;
  const rand = Math.random().toString(36).slice(2, 6).toUpperCase();
  if (!base) return `BILL-${ymd}-${rand}`;
  const match = base.match(/^(.*?)(?:-R(\d+))?$/);
  const next = (Number(match[2]) || 1) + 1;
  return `${match[1]}-R${next}`;
}

function signedMoney(value) {
  const num = Number(value) || 0;
  const sign = num >= 0 ? '+' : '−';
  return `<span class="delta ${num >= 0 ? 'up' : 'down'}">${sign}${fmtMoney(Math.abs(num))}</span>`;
}

function availableCell(value) {
  const num = Number(value) || 0;
  return num < 0 ? `<span class="delta down">${fmtMoney(num)}</span>` : `<b>${fmtMoney(num)}</b>`;
}

// ---------- 抽屉：批次详情（含冲正入口） ----------

function bindReverseButtons(root, view, ctx, close) {
  root.querySelectorAll('[data-reverse]').forEach((btn) => {
    btn.addEventListener('click', async () => {
      btn.disabled = true;
      try {
        await api.post(`/api/billing/entries/${btn.dataset.reverse}/reverse`);
        toast('已生成冲正分录，原记录保留');
        close();
        await billsPage.render(view, ctx);
      } catch (err) {
        toast(errorMessage(err), 'err');
        btn.disabled = false;
      }
    });
  });
}

function entryTable(entries, writable) {
  return table({
    rows: entries,
    empty: { title: '没有分录', hint: '失败的批次不会写入任何分录。' },
    columns: [
      { key: 'row_no', label: '行', className: 'mono' },
      { key: 'channel_name', label: '渠道', render: (row) => esc(row.channel_name || row.channel_code || '—') },
      {
        key: 'kind_label',
        label: '类型',
        render: (row) => badge(row.kind === 'reversal' ? 'warn' : row.kind === 'refund' ? 'info' : '', row.kind_label),
      },
      { key: 'amount', label: '金额', className: 'num', render: (row) => signedMoney(row.amount) },
      { key: 'memo', label: '备注', render: (row) => esc(row.memo || '—') },
      {
        key: 'id',
        label: '冲正',
        render: (row) => {
          if (row.kind === 'reversal') return `<span class="mono muted">冲正单</span>`;
          if (row.reversed_by) return '<span class="badge">已冲正</span>';
          return writable ? `<button class="btn sm ghost" data-reverse="${row.id}">冲正</button>` : '<span class="mono muted">—</span>';
        },
      },
    ],
  });
}

async function openBatchDrawer(view, ctx, batchId, writable) {
  let detail;
  try {
    detail = await api.get(`/api/billing/batches/${batchId}`);
  } catch (err) {
    toast(errorMessage(err), 'err');
    return;
  }
  const { root, close } = drawer({
    title: `批次 ${detail.batch_no}`,
    subtitle: `${detail.period} · ${detail.kind_label} · ${detail.status_label} · ${detail.created_by}`,
    body: `
      ${detail.error ? `<div class="error-box" style="margin-bottom:12px"><span>整批失败：${esc(detail.error)}</span></div>` : ''}
      ${statStrip([
        { label: '行数', value: String(detail.row_count) },
        { label: '消耗合计', value: fmtMoney(detail.spend_total) },
        { label: '退款合计', value: fmtMoney(detail.refund_total) },
        { label: '净额', value: fmtMoney(detail.net_total) },
      ])}
      <div style="margin-top:12px">${entryTable(detail.entries || [], writable)}</div>`,
  });
  bindReverseButtons(root, view, ctx, close);
}

// ---------- 抽屉：渠道台账 ----------

async function openChannelLedger(view, ctx, item, writable) {
  let entries;
  try {
    entries = await api.get('/api/billing/entries', { channel_id: item.channel_id, limit: 50 });
  } catch (err) {
    toast(errorMessage(err), 'err');
    return;
  }
  const { root, close } = drawer({
    title: `${item.name} · 台账`,
    subtitle: `预算 ${fmtMoney(item.budget)} · 净消耗 ${fmtMoney(item.net_spend)} · 在途 ${fmtMoney(item.held)} · 可用 ${fmtMoney(item.available)}`,
    body: entryTable(entries.items, writable),
  });
  bindReverseButtons(root, view, ctx, close);
}

// ---------- 入账表单行 ----------

function billRowHtml(channels) {
  return `<div class="bill-row" style="display:grid;grid-template-columns:1.3fr 0.8fr 0.9fr 1.6fr auto;gap:8px;align-items:end">
    <div class="field"><label>渠道</label><select name="row-channel">${channels
      .map((ch) => `<option value="${esc(ch.code)}">${esc(ch.name)}</option>`)
      .join('')}</select></div>
    <div class="field"><label>类型</label><select name="row-kind">
      <option value="spend">消耗</option><option value="refund">退款</option>
    </select></div>
    <div class="field"><label>金额（元）</label><input name="row-amount" type="number" min="0.01" step="0.01" placeholder="0.00" /></div>
    <div class="field"><label>备注</label><input name="row-memo" type="text" maxlength="200" placeholder="平台结算单号等" /></div>
    <button type="button" class="btn sm ghost" data-remove-row title="删除该行">删</button>
  </div>`;
}

// ---------- 页面 ----------

export const billsPage = {
  async render(view, ctx) {
    const writable = can(ctx.user.role, 'billing:write');
    const canExport = can(ctx.user.role, 'export:read');
    if (!state.batchNo) state.batchNo = suggestBatchNo('');
    if (!state.draftKey) state.draftKey = newKey();

    let overview;
    let batches;
    let adjustments;
    try {
      [overview, batches, adjustments] = await Promise.all([
        api.get('/api/billing/overview'),
        api.get('/api/billing/batches', { limit: 30 }),
        api.get('/api/billing/adjustments', { limit: 30 }),
      ]);
    } catch (err) {
      view.innerHTML = errorBox(errorMessage(err));
      view.querySelector('#retry-btn')?.addEventListener('click', () => billsPage.render(view, ctx));
      return;
    }

    const totals = overview.totals;
    const balanceRows = overview.items.map((item) => ({ ...item, id: item.channel_id }));
    const resultBox = state.lastResult
      ? state.lastResult.ok
        ? `<div class="error-box" style="border-color:var(--ok)"><span>批次 ${esc(state.lastResult.batchNo)} 已入账：${state.lastResult.rows} 行，净额 ${fmtMoney(state.lastResult.net)}。</span></div>`
        : `<div class="error-box"><span>批次 ${esc(state.lastResult.batchNo)} 整批失败：${esc(state.lastResult.error)}（已换新批次号，修正后可直接重新提交）</span></div>`
      : '';

    view.innerHTML = `
      <section>
        <div class="section-title">
          <h2>余额总览</h2>
          <span class="meta">可用余额 = 月度预算 − 净消耗 − 在途占用</span>
        </div>
        ${statStrip([
          { label: '合计预算', value: fmtMoney(totals.budget) },
          { label: '净消耗', value: fmtMoney(totals.net_spend), hint: '消耗 − 退款（含冲正）' },
          { label: '在途占用', value: fmtMoney(totals.held), hint: '待批准的预算调整' },
          { label: '可用余额', value: fmtMoney(totals.available) },
        ])}
        <div style="margin-top:12px" id="balance-table">
        ${table({
          rows: balanceRows,
          columns: [
            { key: 'name', label: '渠道', render: (row) => `<b>${esc(row.name)}</b><div class="mono muted">${esc(row.code)}</div>` },
            { key: 'budget', label: '月度预算', className: 'num', render: (row) => fmtMoney(row.budget) },
            { key: 'net_spend', label: '净消耗', className: 'num', render: (row) => fmtMoney(row.net_spend) },
            { key: 'held', label: '在途占用', className: 'num', render: (row) => (row.held ? `<span class="delta down">${fmtMoney(row.held)}</span>` : fmtMoney(0)) },
            { key: 'available', label: '可用余额', className: 'num', render: (row) => availableCell(row.available) },
          ],
          empty: { title: '还没有渠道', hint: '先在「渠道与预算」登记渠道。' },
        })}
        </div>
        ${
          canExport
            ? `<div style="display:flex;gap:10px;margin-top:12px">
                <button class="btn sm" id="export-balances">导出余额 CSV</button>
                <button class="btn sm ghost" id="export-entries">导出台账 CSV</button>
                <span class="mono muted" style="align-self:center">导出与页面同源计算，口径一致</span>
              </div>`
            : ''
        }
      </section>

      <section>
        <div class="section-title">
          <h2>预算调整</h2>
          <span class="meta">先占用 · 再批准 · 两人同时提交不会占用同一笔余额</span>
        </div>
        ${
          writable
            ? `<form id="adjust-form" class="filter-bar">
                ${field({ label: '渠道', name: 'channel_id', value: '', options: overview.items.map((item) => ({ value: String(item.channel_id), label: `${item.name}（可用 ${fmtMoney(item.available)}）` })) })}
                ${field({ label: '调整额（元，负数为挪出）', name: 'delta', type: 'number', value: '', placeholder: '-20000' })}
                ${field({ label: '原因', name: 'reason', value: '', placeholder: '挪给内容种草双11加投' })}
                <button class="btn sm accent" type="submit">提交占用</button>
              </form>`
            : '<p class="policy-note">预算调整由管理员提交占用并审批，当前角色只读。</p>'
        }
        ${table({
          rows: adjustments.items,
          columns: [
            { key: 'adjust_no', label: '单号', className: 'mono' },
            { key: 'channel_name', label: '渠道' },
            { key: 'delta', label: '调整额', className: 'num', render: (row) => signedMoney(row.delta) },
            { key: 'hold_amount', label: '占用', className: 'num', render: (row) => (row.hold_amount ? fmtMoney(row.hold_amount) : '—') },
            { key: 'status', label: '状态', render: (row) => badge(adjustTone(row.status), row.status_label) },
            { key: 'created_by', label: '提交人', className: 'mono' },
            { key: 'decided_by', label: '审批', render: (row) => (row.decided_by ? `<span class="mono">${esc(row.decided_by)}</span><div class="mono muted">${fmtTime(row.decided_at)}</div>` : '—') },
            {
              key: 'id',
              label: '操作',
              render: (row) =>
                row.status === 'held' && writable
                  ? `<button class="btn sm accent" data-decide="approve" data-id="${row.id}">批准</button>
                     <button class="btn sm ghost" data-decide="reject" data-id="${row.id}">驳回</button>`
                  : '',
            },
          ],
          empty: { title: '没有预算调整', hint: '提交一笔负数调整即可看到在途占用。' },
        })}
      </section>

      ${
        writable
          ? `<section>
              <div class="section-title">
                <h2>账单入账</h2>
                <span class="meta">整批成功或整批失败 · 台账只追加不覆盖</span>
              </div>
              <form id="batch-form" style="display:grid;gap:12px">
                <div class="filter-bar" style="border-bottom:none;padding:0">
                  ${field({ label: '批次号（财务单号，幂等键）', name: 'batch_no', value: state.batchNo })}
                  ${field({ label: '账期', name: 'period', type: 'month', value: new Date().toISOString().slice(0, 7) })}
                  <button type="button" class="btn sm ghost" id="new-batch-no">换批次号</button>
                </div>
                <div id="bill-rows" style="display:grid;gap:8px">
                  ${billRowHtml(overview.items)}${billRowHtml(overview.items)}${billRowHtml(overview.items)}
                </div>
                <div style="display:flex;gap:10px">
                  <button type="button" class="btn sm ghost" id="add-row">+ 添加行</button>
                  <button class="btn accent" type="submit">提交入账</button>
                </div>
                ${resultBox}
              </form>
            </section>`
          : ''
      }

      <section>
        <div class="section-title">
          <h2>批次记录</h2>
          <span class="meta">${batches.total} 个批次 · 点击行查看分录</span>
        </div>
        <div id="batch-table">
        ${table({
          rows: batches.items,
          columns: [
            { key: 'batch_no', label: '批次号', className: 'mono' },
            { key: 'period', label: '账期' },
            { key: 'kind_label', label: '类型', render: (row) => badge(row.kind === 'reversal' ? 'warn' : '', row.kind_label) },
            { key: 'status', label: '结果', render: (row) => badge(batchTone(row.status), row.status_label) },
            { key: 'row_count', label: '行数', className: 'num' },
            { key: 'spend_total', label: '消耗', className: 'num', render: (row) => fmtMoney(row.spend_total) },
            { key: 'refund_total', label: '退款', className: 'num', render: (row) => fmtMoney(row.refund_total) },
            { key: 'net_total', label: '净额', className: 'num', render: (row) => signedMoney(row.net_total) },
            { key: 'created_by', label: '入账人', className: 'mono' },
            { key: 'created_at', label: '时间', render: (row) => fmtTime(row.created_at) },
          ],
          empty: { title: '还没有账单批次', hint: '财务合并账单后，在上方表单整批入账。' },
        })}
        </div>
      </section>`;

    // ---- 事件：余额表行点击 → 渠道台账抽屉 ----
    view.querySelectorAll('#balance-table tbody tr').forEach((row) => {
      row.addEventListener('click', () => {
        const item = overview.items.find((entry) => String(entry.channel_id) === row.dataset.id);
        if (item) openChannelLedger(view, ctx, item, writable);
      });
    });

    // ---- 事件：导出 ----
    view.querySelector('#export-balances')?.addEventListener('click', async () => {
      try {
        await api.download('/api/exports/balances.csv', 'balances.csv');
        toast('已开始下载余额 CSV');
      } catch (err) {
        toast(errorMessage(err), 'err');
      }
    });
    view.querySelector('#export-entries')?.addEventListener('click', async () => {
      try {
        await api.download('/api/exports/bill-entries.csv', 'bill-entries.csv');
        toast('已开始下载台账 CSV');
      } catch (err) {
        toast(errorMessage(err), 'err');
      }
    });

    // ---- 事件：预算调整 ----
    const adjustForm = view.querySelector('#adjust-form');
    adjustForm?.addEventListener('submit', async (event) => {
      event.preventDefault();
      const form = event.target;
      const submitBtn = form.querySelector('[type=submit]');
      submitBtn.disabled = true;
      try {
        const adjustment = await api.post('/api/billing/adjustments', {
          channel_id: Number(form.channel_id.value),
          delta: Number(form.delta.value),
          reason: form.reason.value.trim(),
          request_key: state.draftKey,
        });
        state.draftKey = newKey();
        toast(`已占用 ${fmtMoney(adjustment.hold_amount)}，待批准（${adjustment.adjust_no}）`);
        await billsPage.render(view, ctx);
      } catch (err) {
        toast(errorMessage(err), 'err');
        submitBtn.disabled = false;
      }
    });
    view.querySelectorAll('[data-decide]').forEach((btn) => {
      btn.addEventListener('click', async () => {
        btn.disabled = true;
        const action = btn.dataset.decide;
        try {
          await api.post(`/api/billing/adjustments/${btn.dataset.id}/${action}`);
          toast(action === 'approve' ? '已批准，预算已生效' : '已驳回，占用已释放');
          await billsPage.render(view, ctx);
        } catch (err) {
          toast(errorMessage(err), 'err');
          await billsPage.render(view, ctx);
        }
      });
    });

    // ---- 事件：账单入账 ----
    const batchForm = view.querySelector('#batch-form');
    if (batchForm) {
      const rowsBox = batchForm.querySelector('#bill-rows');
      batchForm.querySelector('#add-row').addEventListener('click', () => {
        rowsBox.insertAdjacentHTML('beforeend', billRowHtml(overview.items));
      });
      rowsBox.addEventListener('click', (event) => {
        const btn = event.target.closest('[data-remove-row]');
        if (!btn) return;
        if (rowsBox.querySelectorAll('.bill-row').length <= 1) {
          toast('至少保留一行', 'err');
          return;
        }
        btn.closest('.bill-row').remove();
      });
      batchForm.querySelector('#new-batch-no').addEventListener('click', () => {
        state.batchNo = suggestBatchNo('');
        batchForm.batch_no.value = state.batchNo;
      });
      batchForm.addEventListener('submit', async (event) => {
        event.preventDefault();
        const submitBtn = batchForm.querySelector('[type=submit]');
        const rows = [...rowsBox.querySelectorAll('.bill-row')].map((node) => ({
          channel_code: node.querySelector('[name=row-channel]').value,
          kind: node.querySelector('[name=row-kind]').value,
          amount: Number(node.querySelector('[name=row-amount]').value),
          memo: node.querySelector('[name=row-memo]').value.trim() || null,
        }));
        if (!rows.length || rows.some((row) => !(row.amount > 0))) {
          toast('每行金额都必须大于 0', 'err');
          return;
        }
        state.batchNo = batchForm.batch_no.value.trim();
        submitBtn.disabled = true;
        try {
          const batch = await api.post('/api/billing/batches', {
            batch_no: state.batchNo,
            period: batchForm.period.value,
            rows,
          });
          state.lastResult = { ok: true, batchNo: batch.batch_no, rows: batch.row_count, net: batch.net_total };
          state.batchNo = suggestBatchNo('');
          toast(`批次 ${batch.batch_no} 已整批入账`);
          await billsPage.render(view, ctx);
        } catch (err) {
          if (err.code === 'BATCH_FAILED') {
            state.lastResult = { ok: false, batchNo: err.detail?.batch_no || state.batchNo, error: err.detail?.error || err.message };
            state.batchNo = suggestBatchNo(state.batchNo);
            await billsPage.render(view, ctx);
          } else {
            toast(errorMessage(err), 'err');
            submitBtn.disabled = false;
          }
        }
      });
    }

    // ---- 事件：批次行点击 → 批次详情抽屉 ----
    view.querySelectorAll('#batch-table tbody tr').forEach((row) => {
      row.addEventListener('click', () => openBatchDrawer(view, ctx, row.dataset.id, writable));
    });
  },
};

export default billsPage;
