import { api } from '../api.js';
import { can } from '../config.js';
import { deltaPct, emptyState, errorBox, errorMessage, esc, fmtMoney, fmtPct, toast } from '../ui.js';

const state = { runId: '' };

function budgetBar(item) {
  const max = Math.max(item.current_budget || 0, item.suggested_budget || 0, 1);
  const cur = Math.round(((item.current_budget || 0) / max) * 100);
  const sug = Math.round(((item.suggested_budget || 0) / max) * 100);
  return `<div class="plan-track" title="当前 ${fmtMoney(item.current_budget)} → 建议 ${fmtMoney(item.suggested_budget)}">
    <div class="plan-current" style="width:${cur}%"></div>
    <div class="plan-suggested" style="width:${sug}%"></div>
  </div>`;
}

export const planPage = {
  async render(view, ctx) {
    let runs;
    try {
      runs = await api.get('/api/attribution-runs', { limit: 20 });
      if (!state.runId) {
        state.runId = String(ctx.query.run_id || (runs.items[0] && runs.items[0].id) || '');
      }
      if (!state.runId) {
        view.innerHTML = emptyState({ title: '还没有可用的归因结果', hint: '先在「归因运行」发起一次计算。' });
        return;
      }
    } catch (err) {
      view.innerHTML = errorBox(errorMessage(err));
      view.querySelector('#retry-btn')?.addEventListener('click', () => planPage.render(view, ctx));
      return;
    }
    let plan;
    try {
      plan = await api.get(`/api/attribution-runs/${state.runId}/plan`);
    } catch (err) {
      view.innerHTML = errorBox(errorMessage(err));
      view.querySelector('#retry-btn')?.addEventListener('click', () => planPage.render(view, ctx));
      return;
    }
    const items = plan.items || [];
    const totalCurrent = items.reduce((sum, item) => sum + (item.current_budget || 0), 0);
    const totalSuggested = items.reduce((sum, item) => sum + (item.suggested_budget || 0), 0);
    const content = items.find((item) => item.channel_code === 'content');
    const maxDelta = Math.max(0, ...items.map((item) => Math.abs(item.delta_pct || 0)));
    view.innerHTML = `
      <section class="spread">
        <div>
          <div class="kicker">${esc(plan.period)} · 预算重分配 / budget reallocation</div>
          ${
            plan.costs_hidden
              ? `<div class="figure-block"><div class="figure-label">成本明细</div><div class="figure" style="font-size:2.6rem">已隐藏</div><div class="figure-note">只读角色看不到成本、ROI 与建议预算，只保留归因占比。</div></div>`
              : `<div class="figure-block">
                  <div class="figure-label">总预算 / monthly budget</div>
                  <div class="figure coral">${fmtMoney(plan.total_budget)}</div>
                  <div class="figure-note">重分配后合计 ${fmtMoney(totalSuggested)}，与当前 ${fmtMoney(totalCurrent)} 一致；单渠道变动上限 ±${(plan.policy.max_delta * 100).toFixed(0)}%，品牌搜索保底 ${(plan.policy.brand_floor_share * 100).toFixed(0)}%。</div>
                </div>`
          }
          <div class="stat-strip" style="margin-top:18px">
            <div class="stat"><span class="k">内容种草建议</span><span class="v">${content && content.delta_pct !== null ? `${content.delta_pct >= 0 ? '+' : ''}${content.delta_pct.toFixed(2)}%` : '—'}</span><span class="hint">马尔可夫 ${content ? fmtPct(content.share) : '—'}</span></div>
            <div class="stat"><span class="k">最大变动</span><span class="v">${maxDelta.toFixed(1)}%</span><span class="hint">受 ±30% 闸门约束</span></div>
            <div class="stat"><span class="k">效率指数</span><span class="v">${plan.policy.efficiency_alpha}</span><span class="hint">预算 ∝ ROI^α</span></div>
            <div class="stat"><span class="k">归因口径</span><span class="v" style="font-size:1.1rem">马尔可夫 + Shapley</span><span class="hint">后端计算</span></div>
          </div>
          <p class="policy-note" style="margin-top:18px">算法：Shapley 精确枚举 2⁵ 个渠道组合得到 v(S)，ROI = Shapley 贡献额 / 月度成本；按 ROI 效率的 0.7 次幂提升/压缩预算，再用水位法锁定触边渠道，保证合计不变。</p>
        </div>
        <aside>
          <div class="section-title"><h2>运行</h2><span class="meta">choose a run</span></div>
          <div class="filter-bar" id="plan-filter">
            <div class="field" style="min-width:100%">
              <label for="run_id">归因运行</label>
              <select name="run_id" id="run_id">
                ${runs.items.map((run) => `<option value="${run.id}" ${String(run.id) === String(state.runId) ? 'selected' : ''}>${esc(run.run_no)} · ${esc(run.period)}</option>`).join('')}
              </select>
            </div>
          </div>
          ${can(ctx.user.role, 'export:read') ? '<button class="btn accent" id="export-attributions" style="margin-top:14px">导出归因与预算建议 CSV</button>' : '<p class="mono muted" style="margin-top:14px">导出仅管理员可见</p>'}
          <p class="muted" style="font-size:0.78rem;margin-top:10px">导出文件为 UTF-8 BOM，Excel 直接打开无乱码；包含 5 个渠道 × 三种口径与建议预算。</p>
        </aside>
      </section>

      <section>
        <div class="section-title"><h2>建议预算</h2><span class="meta">灰=当前 · 珊瑚=建议</span></div>
        ${
          items.length
            ? items
                .map(
                  (item) => `<div class="plan-row">
                    <div class="ledger-name"><b>${esc(item.channel_name)}</b><span>${esc(item.channel_type_label)}</span></div>
                    ${item.suggested_budget === null ? '<div class="plan-track"><div class="plan-current" style="width:100%"></div></div>' : budgetBar(item)}
                    <div class="plan-numbers">
                      ${item.suggested_budget === null ? '成本隐藏' : `${fmtMoney(item.current_budget)} → <b>${fmtMoney(item.suggested_budget)}</b><br />${deltaPct(item.delta_pct)} · ROI ${Number(item.roi).toFixed(2)}`}
                    </div>
                  </div>`,
                )
                .join('')
            : emptyState({ title: '这个运行没有结果', hint: '换一次运行或重新归因。' })
        }
      </section>`;
    const filter = view.querySelector('#plan-filter');
    filter?.addEventListener('change', () => {
      state.runId = filter.querySelector('[name=run_id]').value;
      planPage.render(view, ctx);
    });
    view.querySelector('#export-attributions')?.addEventListener('click', async () => {
      try {
        await api.download(`/api/exports/attributions.csv?run_id=${state.runId}`, 'attributions.csv');
        toast('已开始下载归因 CSV');
      } catch (err) {
        toast(errorMessage(err), 'err');
      }
    });
  },
};

export default planPage;
