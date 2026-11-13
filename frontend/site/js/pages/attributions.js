import { api } from '../api.js';
import { ENUMS, can, reviewTone } from '../config.js';
import { compareRows, drawer, errorBox, errorMessage, esc, field, fmtMoney, fmtPct, kv, table, toast } from '../ui.js';

const state = { runId: '', status: '' };

function openAttribution(view, ctx, item) {
  const canReview = can(ctx.user.role, 'attribution:review');
  const { root, close } = drawer({
    title: item.channel_name,
    subtitle: `${item.channel_type_label} · 运行 ${item.run_no}`,
    body: `${kv([
      ['马尔可夫占比', `<b>${fmtPct(item.share)}</b>`],
      ['last-click 占比', fmtPct(item.last_click_share)],
      ['Shapley 占比', fmtPct(item.shapley_share)],
      ['移除效应', fmtPct(item.removal_effect)],
      ['贡献额', item.credit_amount === null ? '隐藏' : fmtMoney(item.credit_amount)],
      ['成本 / ROI', item.cost === null ? '隐藏' : `${fmtMoney(item.cost)} · ${Number(item.roi).toFixed(3)}`],
      ['建议预算', item.suggested_budget === null ? '隐藏' : `${fmtMoney(item.budget)} → ${fmtMoney(item.suggested_budget)}（${item.delta_pct >= 0 ? '+' : ''}${item.delta_pct.toFixed(2)}%）`],
      ['复核状态', `<span class="badge ${reviewTone(item.status)}">${esc(item.status_label)}</span>`],
      ['复核人', esc(item.reviewer || '—')],
      ['复核备注', esc(item.review_note || '—')],
    ])}
    <div class="section-title" style="margin-top:12px"><h2 style="font-size:0.95rem">三种口径</h2><span class="meta">后端计算</span></div>
    ${compareRows([
      { channel_code: item.channel_code, channel_name: item.channel_name, channel_type_label: item.channel_type_label, share: item.share, last_click_share: item.last_click_share, roi: item.roi },
    ], { showCost: item.roi !== null })}`,
    footer: canReview
      ? `<form id="review-form" style="display:grid;gap:10px">
          ${field({ label: '复核结论', name: 'status', value: item.status, options: Object.entries(ENUMS.review).map(([value, label]) => ({ value, label })) })}
          ${field({ label: '备注', name: 'note', value: item.review_note || '', placeholder: '例如：认可马尔可夫口径，内容加预算' })}
          <button class="btn accent" type="submit">提交复核</button>
        </form>`
      : '<span class="mono muted">只读角色可以查看，但不能复核</span>',
  });
  root.querySelector('#review-form')?.addEventListener('submit', async (event) => {
    event.preventDefault();
    const form = event.target;
    try {
      await api.patch(`/api/attributions/${item.id}/review`, {
        status: form.status.value,
        note: form.note.value.trim() || null,
      });
      toast('复核结论已保存');
      close();
      await attributionsPage.render(view, ctx);
    } catch (err) {
      toast(errorMessage(err), 'err');
    }
  });
}

export const attributionsPage = {
  async render(view, ctx) {
    state.runId = ctx.query.run_id || state.runId;
    let runs;
    let data;
    try {
      runs = await api.get('/api/attribution-runs', { limit: 20 });
      if (!state.runId && runs.items.length) state.runId = String(runs.items[0].id);
      data = await api.get('/api/attributions', { run_id: state.runId || undefined, status: state.status, limit: 50 });
    } catch (err) {
      view.innerHTML = errorBox(errorMessage(err));
      view.querySelector('#retry-btn')?.addEventListener('click', () => attributionsPage.render(view, ctx));
      return;
    }
    const rows = data.items.map((item) => ({
      ...item,
      roi: item.roi,
    }));
    view.innerHTML = `
      <section class="spread">
        <div>
          <div class="section-title"><h2>渠道对比</h2><span class="meta">${esc(state.runId ? `运行 #${state.runId}` : '全部')} · ${data.total} 条</span></div>
          <div class="filter-bar" id="attribution-filters">
            ${field({ label: '运行', name: 'run_id', value: state.runId, options: runs.items.map((run) => ({ value: run.id, label: `${run.run_no} · ${run.period}` })) })}
            ${field({ label: '复核状态', name: 'status', value: state.status, options: [{ value: '', label: '全部' }, ...Object.entries(ENUMS.review).map(([value, label]) => ({ value, label }))] })}
          </div>
          ${table({
            rows,
            columns: [
              { key: 'channel_name', label: '渠道', render: (row) => `<b>${esc(row.channel_name)}</b><div class="mono muted">${esc(row.channel_type_label)}</div>` },
              { key: 'share', label: '马尔可夫', className: 'num', render: (row) => `<b>${fmtPct(row.share)}</b>` },
              { key: 'last_click_share', label: 'last-click', className: 'num', render: (row) => fmtPct(row.last_click_share) },
              { key: 'shapley_share', label: 'Shapley', className: 'num', render: (row) => fmtPct(row.shapley_share) },
              { key: 'roi', label: 'ROI', className: 'num', render: (row) => (row.roi === null ? '<span class="muted">隐藏</span>' : Number(row.roi).toFixed(2)) },
              { key: 'suggested_budget', label: '建议预算', className: 'num', render: (row) => (row.suggested_budget === null ? '<span class="muted">隐藏</span>' : `${fmtMoney(row.suggested_budget)}<div class="delta ${row.delta_pct >= 0 ? 'up' : 'down'}">${row.delta_pct >= 0 ? '+' : ''}${row.delta_pct.toFixed(1)}%</div>`) },
              { key: 'status', label: '复核', render: (row) => `<span class="badge ${reviewTone(row.status)}">${esc(row.status_label)}</span>` },
            ],
            empty: { title: '这个筛选下没有归因结果', hint: '换一次运行或先发起归因。' },
          })}
        </div>
        <aside>
          <div class="section-title"><h2>口径走势</h2><span class="meta">markov vs last-click</span></div>
          ${rows.length ? compareRows([...rows].sort((a, b) => b.share - a.share), { showCost: rows[0].roi !== null }) : '<p class="muted">暂无数据</p>'}
          <p class="policy-note" style="margin-top:18px">马尔可夫占比 = 移除该渠道后转化率下降比例归一化；last-click 只认最后一跳。两者差额越大，说明该渠道的种草/辅助作用越被低估。</p>
        </aside>
      </section>`;
    const filters = view.querySelector('#attribution-filters');
    filters?.addEventListener('change', () => {
      state.runId = filters.querySelector('[name=run_id]').value;
      state.status = filters.querySelector('[name=status]').value;
      attributionsPage.render(view, ctx);
    });
    view.querySelectorAll('table.data tbody tr').forEach((row) => {
      row.addEventListener('click', () => {
        const item = rows.find((entry) => String(entry.id) === row.dataset.id);
        if (item) openAttribution(view, ctx, item);
      });
    });
  },
};

export default attributionsPage;
