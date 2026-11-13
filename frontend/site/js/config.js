/**
 * 项目品牌、导航、角色权限与枚举文案（前端唯一定义处）。
 * 后端对应：backend/src/constants/{roles,enums}.py；README 列出全部出现位置。
 */
export const BRAND = {
  short: 'mixcredit',
  title: '多渠道转化归因与预算重分配台',
  org: '清野日化 · 增长组',
  edition: 'MIXCREDIT · 2026.10',
  subtitle: '路径构建 → 马尔可夫归因 → Shapley 预算重分配',
  loginLead: 'last-click 把 60% 记给品牌搜索，内容种草只拿 12%。马尔可夫口径把这两件事同时纠正过来。',
  loginPoints: [
    ['01', '5 个渠道、2,400 条用户路径、8,600 个触点，按时间顺序重建旅程。'],
    ['02', '移除效应与精确 Shapley 双口径对照，拒绝拍脑袋调预算。'],
    ['03', '预算建议单渠道变动 ≤ ±30%，品牌搜索保底 12%。'],
  ],
};

export const NAV = [
  { to: '#/overview', no: '01', label: '总览', permission: 'overview:read' },
  { to: '#/channels', no: '02', label: '渠道与预算', permission: 'channel:read' },
  { to: '#/bills', no: '03', label: '账单与余额', permission: 'billing:read' },
  { to: '#/runs', no: '04', label: '归因运行', permission: 'run:read' },
  { to: '#/attributions', no: '05', label: '渠道对比', permission: 'attribution:read' },
  { to: '#/plan', no: '06', label: '预算建议', permission: 'plan:read' },
  { to: '#/audit', no: '07', label: '审计日志', permission: 'audit:read' },
];

export const ROLE_LABELS = {
  admin: '增长管理员',
  analyst: '归因分析师',
  viewer: '渠道只读',
};

export const PERMISSIONS = {
  admin: ['overview:read', 'channel:read', 'channel:write', 'run:read', 'run:create', 'attribution:read', 'attribution:review', 'plan:read', 'export:read', 'audit:read', 'billing:read', 'billing:write'],
  analyst: ['overview:read', 'channel:read', 'run:read', 'run:create', 'attribution:read', 'attribution:review', 'plan:read', 'billing:read'],
  viewer: ['overview:read', 'channel:read', 'run:read', 'attribution:read', 'plan:read'],
};

export const ENUMS = {
  channelType: { search: '搜索', feed: '信息流', content: '内容种草', community: '私域', live: '直播' },
  model: { markov: '马尔可夫移除效应', last_click: 'last-click 对照', shapley: '精确 Shapley' },
  runStatus: { queued: '排队中', running: '执行中', success: '成功', partial: '部分成功', failed: '失败' },
  review: { pending: '待复核', confirmed: '已确认', dismissed: '已驳回' },
  trigger: { manual: '手动', schedule: '定时', seed: '初始化' },
  billKind: { spend: '消耗', refund: '退款', reversal: '冲正' },
  batchKind: { entry: '入账', reversal: '冲正' },
  batchStatus: { posted: '已入账', failed: '入账失败' },
  adjustStatus: { held: '在途占用', approved: '已批准', rejected: '已驳回' },
};

export function can(role, permission) {
  return (PERMISSIONS[role] || []).includes(permission);
}

export function runTone(status) {
  return { success: 'ok', partial: 'warn', failed: 'danger', running: 'info', queued: '' }[status] || 'info';
}

export function reviewTone(status) {
  return { pending: 'pending warn', confirmed: 'ok', dismissed: 'danger' }[status] || 'info';
}

export function batchTone(status) {
  return status === 'posted' ? 'ok' : 'danger';
}

export function adjustTone(status) {
  return { held: 'pending warn', approved: 'ok', rejected: 'danger' }[status] || 'info';
}

export function pct(value, digits = 1) {
  if (value === null || value === undefined) return '—';
  return `${(Number(value) * 100).toFixed(digits)}%`;
}
