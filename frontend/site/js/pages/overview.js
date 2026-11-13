import { api } from '../api.js';
import { pct } from '../config.js';
import { compareRows, emptyState, errorBox, errorMessage, esc, fmtMoney, fmtPct, fmtTime, figureBlock, trendChart } from '../ui.js';

function pathChart(buckets) {
  if (!buckets || !buckets.length) return emptyState({ title: '暂无路径分布', hint: '先在归因运行页跑一次归因。' });
  const max = Math.max(1, ...buckets.map((item) => item.count));
  return `<div class="trend" style="height:140px;align-items:flex-end">${buckets
    .map(
      (item) => `<div class="col" title="${esc(item.label)} · ${item.count} 条 · 转化率 ${(item.rate * 100).toFixed(1)}%">
        <div class="stem" style="height:${Math.max(3, Math.round((item.count / max) * 96))}px;background:${item.rate > 0.35 ? 'var(--accent)' : 'var(--ink-faint)'}"></div>
        <span class="lbl">${esc(item.key)}</span>
        <span class="lbl">${(item.rate * 100).toFixed(0)}%</span>
      </div>`,
    )
    .join('')}</div>`;
}

export const overviewPage = {
  async render(view, ctx) {
    view.innerHTML = '<div class="empty"><div class="mark">读取总览…</div></div>';
    let data;
    try {
      data = await api.get('/api/overview');
    } catch (err) {
      view.innerHTML = errorBox(errorMessage(err));
      view.querySelector('#retry-btn')?.addEventListener('click', () => overviewPage.render(view, ctx));
      return;
    }
    const totals = data.totals || {};
    const gap = data.biggest_gap;
    const latest = data.latest_run;
    view.innerHTML = `
      <section class="spread">
        <div>
          <div class="kicker">${esc(data.period || '2026-10')} · 归因口径：马尔可夫移除效应</div>
          ${figureBlock({
            label: '整体转化率 / conversion rate',
            value: pct(totals.conversion_rate || 0, 2),
            note: `${totals.conversions || 0} 笔转化 ÷ ${totals.users || 0} 条用户路径，平均路径 ${Number(totals.avg_path_length || 0).toFixed(2)} 个触点。`,
            coral: true,
          })}
          <div class="stat-strip" style="margin-top:18px">
            <div class="stat"><span class="k">触点</span><span class="v">${(totals.touchpoints || 0).toLocaleString('zh-CN')}</span><span class="hint">跨 ${data.channels_total} 个渠道</span></div>
            <div class="stat"><span class="k">转化数</span><span class="v">${totals.conversions || 0}</span><span class="hint">订单口径</span></div>
            <div class="stat"><span class="k">营收</span><span class="v">${totals.revenue === null ? '隐藏' : fmtMoney(totals.revenue)}</span><span class="hint">${data.costs_hidden ? '只读角色隐藏成本' : '期间累计'}</span></div>
            <div class="stat"><span class="k">待复核</span><span class="v">${data.pending_total}</span><span class="hint">${data.worker_alive ? 'worker 在岗' : 'worker 心跳超时'}</span></div>
          </div>
          <div style="margin-top:22px">
            <div class="section-title"><h2>路径长度分布</h2><span class="meta">柱下为转化率</span></div>
            ${pathChart(data.path_length)}
          </div>
        </div>
        <aside>
          <div class="section-title"><h2>口径差</h2><span class="meta">last-click vs markov</span></div>
          ${
            gap
              ? `<div class="figure-block" style="border-bottom-color:var(--accent)">
                  <div class="figure-label">被低估最多的渠道</div>
                  <div class="figure" style="font-size:2.6rem">${esc(gap.channel_name)}</div>
                  <div class="figure-note">last-click ${fmtPct(gap.last_click_share)} → 马尔可夫 ${fmtPct(gap.share)}，
                  相差 ${((gap.share - gap.last_click_share) * 100).toFixed(1)} 个百分点；建议预算 ${gap.delta_pct === null ? '隐藏' : `${gap.delta_pct >= 0 ? '+' : ''}${gap.delta_pct.toFixed(2)}%`}。</div>
                </div>`
              : emptyState({ title: '还没有归因结果', hint: '去「归因运行」发起一次计算。' })
          }
          <div style="margin-top:16px">
            <div class="section-title"><h2>复核进度</h2><span class="meta">attributions</span></div>
            ${(data.review || [])
              .map((item) => `<div class="pair" style="grid-template-columns:70px 1fr 32px"><span>${esc(item.label)}</span><div class="pair-track"><div class="pair-fill markov" style="width:${Math.min(100, item.count * 20)}%"></div></div><b>${item.count}</b></div>`)
              .join('') || '<p class="muted">暂无</p>'}
          </div>
          <div style="margin-top:16px">
            <div class="section-title"><h2>近 7 天运行</h2><span class="meta">runs / day</span></div>
            ${trendChart(data.trend)}
          </div>
        </aside>
      </section>

      <section>
        <div class="section-title"><h2>渠道口径对照</h2><span class="meta">${esc(latest ? latest.run_no : '—')} · 点击行可看明细</span></div>
        ${
          (data.comparison || []).length
            ? compareRows(data.comparison, { showCost: !data.costs_hidden })
            : emptyState({ title: '暂无渠道结果', hint: '完成一次归因运行后自动出现。' })
        }
      </section>

      <section class="grid-2">
        <div>
          <div class="section-title"><h2>最近一次运行</h2><span class="meta">latest</span></div>
          ${
            latest
              ? `<div class="kv">
                  <dt>运行号</dt><dd class="mono">${esc(latest.run_no)}</dd>
                  <dt>状态</dt><dd><span class="badge ${latest.status === 'success' ? 'ok' : 'warn'}">${esc(latest.status_label)}</span></dd>
                  <dt>口径</dt><dd>${esc(latest.model_label)}</dd>
                  <dt>输入</dt><dd>${latest.users_count} 用户 / ${latest.touchpoints_count} 触点</dd>
                  <dt>开始</dt><dd>${fmtTime(latest.started_at)}</dd>
                  <dt>耗时</dt><dd>${latest.finished_at ? Math.max(1, Math.round((new Date(latest.finished_at) - new Date(latest.started_at)) / 1000)) + ' 秒' : '—'}</dd>
                  <dt>日志</dt><dd><pre class="code">${esc(latest.log_text || '（无）')}</pre></dd>
                </div>`
              : emptyState({ title: '还没有运行记录', hint: '去「归因运行」发起一次。' })
          }
        </div>
        <div>
          <div class="section-title"><h2>渠道台账</h2><span class="meta">channels</span></div>
          <div class="ledger">${(data.channels || [])
            .map(
              (channel) => `<div class="ledger-row" style="grid-template-columns:1fr auto">
                <div class="ledger-name"><b>${esc(channel.name)}</b><span>${esc(channel.type_label)} · ${esc(channel.owner)}</span></div>
                <div class="ledger-delta">${channel.budget === null ? '<span class="mono muted">成本隐藏</span>' : `<div>${fmtMoney(channel.monthly_cost)}</div><div class="mono muted">预算 ${fmtMoney(channel.budget)}</div>`}</div>
              </div>`,
            )
            .join('')}</div>
        </div>
      </section>`;
  },
};

export default overviewPage;
