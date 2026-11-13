import { api } from '../api.js';
import { ENUMS, can } from '../config.js';
import { drawer, errorBox, errorMessage, esc, field, fmtMoney, fmtTime, kv, table, toast } from '../ui.js';

const state = { type: '' };

function shareOfBudget(item, total) {
  if (item.budget === null || !total) return '<span class="mono muted">隐藏</span>';
  return `${((item.budget / total) * 100).toFixed(1)}%`;
}

function openChannel(view, ctx, channel, total) {
  const editable = can(ctx.user.role, 'channel:write');
  const { root, close } = drawer({
    title: channel.name,
    subtitle: `${channel.code} · ${channel.type_label} · ${channel.owner}`,
    body: `${kv([
      ['月成本', channel.monthly_cost === null ? '隐藏（只读角色）' : fmtMoney(channel.monthly_cost)],
      ['月度预算', channel.budget === null ? '隐藏（只读角色）' : fmtMoney(channel.budget)],
      ['预算占比', shareOfBudget(channel, total)],
      ['状态', channel.enabled ? '启用' : '停用'],
      ['更新时间', fmtTime(channel.updated_at)],
      ['备注', esc(channel.note || '—')],
    ])}
    ${
      editable
        ? `<form id="channel-form" style="display:grid;gap:12px;margin-top:6px">
            ${field({ label: '渠道名称', name: 'name', value: channel.name })}
            ${field({ label: '负责人', name: 'owner', value: channel.owner })}
            ${field({ label: '月成本（元）', name: 'monthly_cost', type: 'number', value: channel.monthly_cost ?? 0 })}
            ${field({ label: '月度预算（元）', name: 'budget', type: 'number', value: channel.budget ?? 0 })}
            ${field({ label: '状态', name: 'enabled', value: String(channel.enabled), options: [{ value: 'true', label: '启用' }, { value: 'false', label: '停用' }] })}
            <button class="btn accent" type="submit">保存预算口径</button>
          </form>`
        : '<p class="policy-note">只读角色可以看渠道结构，但成本与预算字段由后端隐藏。</p>'
    }`,
  });
  root.querySelector('#channel-form')?.addEventListener('submit', async (event) => {
    event.preventDefault();
    const form = event.target;
    try {
      await api.patch(`/api/channels/${channel.id}`, {
        name: form.name.value.trim(),
        owner: form.owner.value.trim() || null,
        monthly_cost: Number(form.monthly_cost.value),
        budget: Number(form.budget.value),
        enabled: form.enabled.value === 'true',
      });
      toast('渠道预算已更新');
      close();
      await channelsPage.render(view, ctx);
    } catch (err) {
      toast(errorMessage(err), 'err');
    }
  });
}

function openCreate(view, ctx) {
  const { root, close } = drawer({
    title: '新增投放渠道',
    subtitle: '新渠道会进入下一次归因的候选集合',
    body: `<form id="channel-create" style="display:grid;gap:12px">
      ${field({ label: '编码（小写字母）', name: 'code', placeholder: 'douyin_koc' })}
      ${field({ label: '名称', name: 'name', placeholder: '抖音达人种草' })}
      ${field({ label: '类型', name: 'type', value: 'content', options: Object.entries(ENUMS.channelType).map(([value, label]) => ({ value, label })) })}
      ${field({ label: '月成本（元）', name: 'monthly_cost', type: 'number', value: 100000 })}
      ${field({ label: '月度预算（元）', name: 'budget', type: 'number', value: 100000 })}
      ${field({ label: '负责人', name: 'owner', value: '清野日化 · 增长组' })}
      <div class="form-error" id="channel-error"></div>
      <button class="btn accent" type="submit">保存渠道</button>
    </form>`,
  });
  root.querySelector('#channel-create').addEventListener('submit', async (event) => {
    event.preventDefault();
    const form = event.target;
    try {
      await api.post('/api/channels', {
        code: form.code.value.trim(),
        name: form.name.value.trim(),
        type: form.type.value,
        monthly_cost: Number(form.monthly_cost.value),
        budget: Number(form.budget.value),
        owner: form.owner.value.trim() || null,
        note: null,
      });
      toast('渠道已新增');
      close();
      await channelsPage.render(view, ctx);
    } catch (err) {
      root.querySelector('#channel-error').textContent =
        err.code === 'CONFLICT' ? '渠道编码已存在' : errorMessage(err);
    }
  });
}

export const channelsPage = {
  async render(view, ctx) {
    let data;
    try {
      data = await api.get('/api/channels', { type: state.type, limit: 50 });
    } catch (err) {
      view.innerHTML = errorBox(errorMessage(err));
      view.querySelector('#retry-btn')?.addEventListener('click', () => channelsPage.render(view, ctx));
      return;
    }
    const total = data.items.reduce((sum, item) => sum + (item.budget || 0), 0);
    view.innerHTML = `
      <section>
        <div class="section-title">
          <h2>渠道与预算</h2>
          <span class="meta">${data.total} 个渠道 · 合计预算 ${total ? fmtMoney(total) : '隐藏'}</span>
        </div>
        <div class="filter-bar" id="channel-filters">
          ${field({ label: '渠道类型', name: 'type', value: state.type, options: [{ value: '', label: '全部' }, ...Object.entries(ENUMS.channelType).map(([value, label]) => ({ value, label }))] })}
          <div class="spacer"></div>
          ${can(ctx.user.role, 'channel:write') ? '<button class="btn sm accent" id="new-channel">新增渠道</button>' : '<span class="mono muted">只读角色：成本字段后端隐藏</span>'}
        </div>
        ${table({
          rows: data.items,
          columns: [
            { key: 'name', label: '渠道', render: (row) => `<b>${esc(row.name)}</b><div class="mono muted">${esc(row.code)}</div>` },
            { key: 'type_label', label: '类型' },
            { key: 'owner', label: '负责人' },
            { key: 'monthly_cost', label: '月成本', className: 'num', render: (row) => (row.monthly_cost === null ? '<span class="muted">隐藏</span>' : fmtMoney(row.monthly_cost)) },
            { key: 'budget', label: '月度预算', className: 'num', render: (row) => (row.budget === null ? '<span class="muted">隐藏</span>' : fmtMoney(row.budget)) },
            { key: 'share', label: '预算占比', className: 'num', render: (row) => shareOfBudget(row, total) },
            { key: 'enabled', label: '状态', render: (row) => (row.enabled ? '<span class="badge ok">启用</span>' : '<span class="badge">停用</span>') },
          ],
          empty: { title: '还没有渠道', hint: '管理员先登记渠道与月度预算。' },
        })}
      </section>`;
    const filters = view.querySelector('#channel-filters');
    filters?.addEventListener('change', () => {
      state.type = filters.querySelector('[name=type]').value;
      channelsPage.render(view, ctx);
    });
    view.querySelectorAll('table.data tbody tr').forEach((row) => {
      row.addEventListener('click', () => {
        const item = data.items.find((entry) => String(entry.id) === row.dataset.id);
        if (item) openChannel(view, ctx, item, total);
      });
    });
    view.querySelector('#new-channel')?.addEventListener('click', () => openCreate(view, ctx));
  },
};

export default channelsPage;
