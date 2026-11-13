import { api } from '../api.js';
import { session } from '../store.js';
import { BRAND } from '../config.js';
import { errorMessage, esc, toast } from '../ui.js';

export const loginPage = {
  async render(root, ctx) {
    root.className = 'login-host';
    root.innerHTML = `
      <div class="login">
        <section class="login-brief">
          <div class="eyebrow">${esc(BRAND.edition)} · 清野日化增长组</div>
          <h1>谁拿走了转化？<br />把预算从<em>说法</em>挪到<em>证据</em>上。</h1>
          <div class="login-figure">
            <b class="coral">12%</b>
            <b>→ 23%</b>
            <span>内容种草的 last-click 占比与马尔可夫归因占比，中间差的 11 个百分点就是被低估的种草预算。</span>
          </div>
          <p class="tagline">${esc(BRAND.loginLead)}</p>
          <div class="brief-points">
            ${BRAND.loginPoints.map(([no, text]) => `<div class="brief-point"><i>${esc(no)}</i><span>${esc(text)}</span></div>`).join('')}
          </div>
          <div class="eyebrow">2,400 用户 · 8,600 触点 · 640 转化 · 5 渠道</div>
        </section>
        <section class="login-form-wrap">
          <form class="login-card" id="login-form" novalidate>
            <div>
              <div class="brand">mixcredit</div>
              <div class="sub">内部账号登录。管理员改预算、分析师跑归因、只读角色看不到成本明细。</div>
            </div>
            <div class="field">
              <label for="email">邮箱</label>
              <input id="email" name="email" type="email" autocomplete="username" value="admin@${esc(BRAND.short)}.io" required />
            </div>
            <div class="field">
              <label for="password">密码</label>
              <input id="password" name="password" type="password" autocomplete="current-password" value="Demo@2026" required />
            </div>
            <div class="form-error" id="login-error" role="alert"></div>
            <button class="btn accent" id="login-submit" type="submit">进入归因台</button>
            <div class="login-hint">
              演示账号（密码 <code>Demo@2026</code>）：<br />
              <code>admin@${esc(BRAND.short)}.io</code> 管理员 · <code>analyst@${esc(BRAND.short)}.io</code> 分析师 ·
              <code>viewer@${esc(BRAND.short)}.io</code> 只读
            </div>
          </form>
        </section>
      </div>`;

    const form = root.querySelector('#login-form');
    const errorNode = root.querySelector('#login-error');
    const submit = root.querySelector('#login-submit');
    form.addEventListener('submit', async (event) => {
      event.preventDefault();
      errorNode.textContent = '';
      submit.disabled = true;
      submit.textContent = '正在验证…';
      try {
        const result = await api.post('/api/auth/login', {
          email: form.email.value.trim(),
          password: form.password.value,
        });
        session.set(result.access_token, result.user);
        toast(`欢迎回来，${result.user.display_name}`);
        location.hash = '#/overview';
        await ctx.reload();
      } catch (err) {
        errorNode.textContent = err.code === 'AUTH_INVALID' ? '账号或密码不正确' : errorMessage(err);
      } finally {
        submit.disabled = false;
        submit.textContent = '进入归因台';
      }
    });
  },
};

export default loginPage;
