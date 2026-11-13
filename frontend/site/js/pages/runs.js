import { api } from '../api.js';
import { ENUMS, can, runTone } from '../config.js';
import { drawer, errorBox, errorMessage, esc, field, fmtMoney, fmtTime, kv, table, toast } from '../ui.js';

const state = { status: '' };

function openRun(view, ctx, run) {
  const metrics = run.metrics || {};
  const { root } = drawer({
    title: `归因运行 ${run.run_no}`,
    subtitle: `${run.period} · ${run.model_label} · ${run.trigger_label}`,
    body: `${kv([
      ['状态', `<span class="badge ${runTone(run.status)}">${esc(run.status_label)}</span>`],
      ['操作人', esc(run.operator_email)],
      ['用户 / 触点', `${run.users_count} / ${run.touchpoints_count}`],
      ['转化 / 营收', `${run.conversions_count} 笔 · ${fmtMoney(run.revenue)}`],
      ['开始', fmtTime(run.started_at)],
      ['结束', fmtTime(run.finished_at)],
      ['基准转化率', metrics.conversion_probability !== undefined ? `${(metrics.conversion_probability * 100).toFixed(2)}%` : '—'],
      ['平均路径', metrics.avg_path_length !== undefined ? Number(metrics.avg_path_length).toFixed(2) : '—'],
    ])}
    <div class="section-title" style="margin-top:12px"><h2 style="font-size:0.95rem">口径占比</h2><span class="meta">markov / last-click / shapley</span></div>
    <pre class="code">${esc(JSON.stringify({ markov: metrics.markov_share, last_click: metrics.last_click_share, shapley: metrics.shapley_share }, null, 2))}</pre>
    <div class="section-title" style="margin-top:12px"><h2 style="font-size:0.95rem">运行日志</h2><span class="meta">log</span></div>
    <pre class="code">${esc(run.log_text || '（无日志）')}</pre>`,
    footer: `<div style="display:flex;gap:8px">
      <button class="btn accent" data-attributions>查看渠道对比</button>
      <button class="btn ghost" data-plan>预算建议</button>
    </div>`,
  });
  root.querySelector('[data-attributions]')?.addEventListener('click', () => {
    location.hash = `#/attributions?run_id=${run.id}`;
  });
  root.querySelector('[data-plan]')?.addEventListener('click', () => {
    location.hash = `#/plan?run_id=${run.id}`;
  });
}

function openCreate(view, ctx) {
  const { root, close } = drawer({
    title: '发起归因运行',
    subtitle: '服务端重算路径、马尔可夫与精确 Shapley，前端只展示结果',
    body: `<form id="run-form" style="display:grid;gap:12px">
      ${field({ label: '统计期间', name: 'period', value: '2026-10', placeholder: '2026-10' })}
      ${field({ label: '归因口径', name: 'model', value: 'markov', options: Object.entries(ENUMS.model).map(([value, label]) => ({ value, label })) })}
      ${field({ label: '触发方式', name: 'trigger', value: 'manual', options: [{ value: 'manual', label: '手动' }, { value: 'schedule', label: '定时补偿' }] })}
      <div class="form-error" id="run-error"></div>
      <button class="btn accent" type="submit">开始计算</button>
    </form>`,
  });
  root.querySelector('#run-form').addEventListener('submit', async (event) => {
    event.preventDefault();
    const form = event.target;
    const button = form.querySelector('button[type=submit]');
    button.disabled = true;
    button.textContent = '计算中…';
    try {
      const run = await api.post('/api/attribution-runs', {
        period: form.period.value.trim(),
        model: form.model.value,
        trigger: form.trigger.value,
      });
      toast(`运行 ${run.run_no}：${run.status_label}，${run.conversions_count} 笔转化`);
      close();
      await runsPage.render(view, ctx);
    } catch (err) {
      root.querySelector('#run-error').textContent = errorMessage(err);
      button.disabled = false;
      button.textContent = '开始计算';
    }
  });
}

export const runsPage = {
  async render(view, ctx) {
    let data;
    try {
      data = await api.get('/api/attribution-runs', { status: state.status, limit: 50 });
    } catch (err) {
      view.innerHTML = errorBox(errorMessage(err));
      view.querySelector('#retry-btn')?.addEventListener('click', () => runsPage.render(view, ctx));
      return;
    }
    view.innerHTML = `
      <section>
        <div class="section-title">
          <h2>归因运行</h2>
          <span class="meta">${data.total} 次 · 每次都会重算 5 渠道</span>
        </div>
        <div class="filter-bar" id="run-filters">
          ${field({ label: '状态', name: 'status', value: state.status, options: [{ value: '', label: '全部' }, ...Object.entries(ENUMS.runStatus).map(([value, label]) => ({ value, label }))] })}
          <div class="spacer"></div>
          ${can(ctx.user.role, 'run:create') ? '<button class="btn sm accent" id="new-run">发起归因</button>' : '<span class="mono muted">只读角色不能发起运行</span>'}
        </div>
        ${table({
          rows: data.items,
          columns: [
            { key: 'run_no', label: '运行号', className: 'mono' },
            { key: 'period', label: '期间', className: 'mono' },
            { key: 'status', label: '状态', render: (row) => `<span class="badge ${runTone(row.status)}">${esc(row.status_label)}</span>` },
            { key: 'trigger_label', label: '触发' },
            { key: 'users_count', label: '用户', className: 'num' },
            { key: 'touchpoints_count', label: '触点', className: 'num' },
            { key: 'conversions_count', label: '转化', className: 'num' },
            { key: 'revenue', label: '营收', className: 'num', render: (row) => fmtMoney(row.revenue) },
            { key: 'started_at', label: '开始', render: (row) => fmtTime(row.started_at) },
          ],
          empty: { title: '还没有归因运行', hint: '分析师可以发起第一次运行。' },
        })}
      </section>`;
    const filters = view.querySelector('#run-filters');
    filters?.addEventListener('change', () => {
      state.status = filters.querySelector('[name=status]').value;
      runsPage.render(view, ctx);
    });
    view.querySelectorAll('table.data tbody tr').forEach((row) => {
      row.addEventListener('click', () => {
        const run = data.items.find((item) => String(item.id) === row.dataset.id);
        if (run) openRun(view, ctx, run);
      });
    });
    view.querySelector('#new-run')?.addEventListener('click', () => openCreate(view, ctx));
  },
};

export default runsPage;
