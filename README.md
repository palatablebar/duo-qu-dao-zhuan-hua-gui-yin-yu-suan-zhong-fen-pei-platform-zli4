# 多渠道转化归因与预算重分配台（`mixcredit`）

> 数据工程 · 数据分析与数据应用（多触点归因 + 预算优化）。原生 HTML/CSS/JS 前端 + FastAPI + Celery + MySQL 8.0 + Redis，5 容器一键起。

## 1. 场景

- **模拟客户**：清野日化（DTC 家清品牌）增长组 6 人，月投放 80 万，5 个渠道：品牌搜索、效果信息流、内容种草、私域社群、达人直播。
- **现有工作流**：各平台后台导出投放/埋点明细 → Excel 里按 last-click 拆账 → 周会上拍脑袋调预算。
- **三个痛点**：① 低估种草渠道（内容大多首触、末跳很少）；② 渠道重叠无法去重；③ 预算分配没有可解释依据。
- **上下游**：投放平台/埋点导出（触点、订单）→ 本系统（路径构建 → 马尔可夫归因 → ROI → 预算建议）→ 增长组与代理公司复核、导出 CSV。
- **一天的工作剧本**：09:40 分析师导入 10 月触点与订单（2,400 用户 / 8,600 触点 / 640 转化）→ 发起归因运行 → 总览看到整体转化率 26.67% 与路径长度分布 → 渠道对比发现内容种草 last-click 11.72% / 马尔可夫 23.05% → 预算建议页看到内容 +18.17%、品牌搜索 +30%（触顶）、达人直播 −30%（触底）→ 复核 5 条归因 → 管理员导出 `attributions.csv` → 审计里回查谁改过预算。

## 2. 角色与权限

| 角色 | 账号 | 权限 | 典型动作 |
|---|---|---|---|
| 增长管理员 `admin` | `admin@mixcredit.io` | 渠道写 + 运行 + 复核 + 导出 + 审计 | 改渠道预算、导出归因 CSV、查看审计 |
| 归因分析师 `analyst` | `analyst@mixcredit.io` | 运行 + 复核 + 读 | 发起归因、提交复核结论 |
| 渠道只读 `viewer` | `viewer@mixcredit.io` | 只读结果（成本明细隐藏） | 看总览/渠道对比/预算建议，不能复核与导出 |

密码统一 `Demo@2026`。低权角色调用高权接口返回 **403**（真实 HTTP 状态）；无 token 返回 **401**；非法参数 **422**；重复渠道编码 **409**。viewer 的成本、ROI、建议预算字段由后端置空（`costs_hidden: true`），不是前端隐藏。

## 3. 功能模块（串成链路）

1. **渠道与预算**（`/api/channels`）：5 个渠道的月度成本/预算/负责人维护，admin 可改，viewer 成本字段隐藏。
2. **归因运行**（`/api/attribution-runs`）：选择期间与口径，服务端重建路径并计算马尔可夫移除效应 + 精确 Shapley，落 5 条 Attribution；`/api/attribution-runs/{id}/plan` 返回预算方案。
3. **渠道对比**（`/api/attributions`）：last-click / 马尔可夫 / Shapley 三口径并列；analyst 与 admin 复核（pending/confirmed/dismissed）。
4. **预算建议与导出**：当前预算 vs 建议预算、变动幅度、ROI；`/api/exports/attributions.csv` 导出（UTF-8 BOM，5 行）。
5. **审计与心跳**：登录、改预算、发起运行、复核、导出全量审计；Celery beat 每 10s 写 worker 心跳，总览展示在岗状态。

## 4. 快速启动

```bash
cp .env.example .env
docker compose up -d --build          # 等 5/5 healthy
open http://localhost:18207
docker compose exec -T backend python -m scripts.seed_demo   # 幂等，可重复执行
docker compose exec -T backend python -m pytest tests -q
```

## 5. 访问地址

| 服务 | 地址 |
|---|---|
| 前端 | http://localhost:18207 |
| 后端 API 文档 | http://localhost:19207/docs |
| 健康检查 | http://localhost:19207/api/health |
| 数据库映射 | localhost:17707 |

## 6. 技术栈

| 层 | 选型 |
|---|---|
| 前端 | 原生 HTML5 + CSS（oklch 令牌 / 杂志排版）+ ES Modules；无框架、无打包 |
| 后端 | Python 3.11、FastAPI 0.115、SQLAlchemy 2.0、PyJWT、passlib(bcrypt) |
| 异步 | Celery 5.4 + Redis（worker 心跳、每日 07:40 复盘任务） |
| 数据库 | MySQL 8.0（utf8mb4） |
| 部署 | Docker Compose，恰好 5 服务 |

## 7. 核心算法与口径

算法位于 `backend/src/services/algorithms.py`（纯函数、无 IO、确定性；单测 `backend/tests/test_algorithms.py`）。

### 算法 A｜路径 + 马尔可夫移除效应

1. 触点按 `user_id` 聚合、按 `touched_at` 升序排成渠道序列；是否有 `conversion` 决定路径终点。
2. 全量路径聚合成一阶转移矩阵，状态 = `START` + 5 渠道 + `CONVERSION` + `NULL`；`CONVERSION` / `NULL` 为吸收态。
3. 从 `START` 出发的吸收概率即基准转化率（种子数据 26.67%，与 640/2400 一致）。
4. **移除效应** = `(基准转化率 − 移除该渠道后的转化率) / 基准转化率`；移除时该渠道所有入边改投 `NULL`（流量流失），出边丢弃。
5. 移除效应归一化即马尔可夫贡献占比；同时输出 last-click 占比做对照。

### 算法 B｜精确 Shapley + 预算重分配

1. 枚举 5 渠道的全部 2⁵ = 32 个组合 `S`，`v(S)` = 仅保留 `S` 时的马尔可夫吸收转化概率，`v(∅)=0`。
2. 精确 Shapley：`φ_i = Σ_{S⊆N\{i}} |S|!(n−|S|−1)!/n! · (v(S∪{i}) − v(S))`；`Σφ_i = v(N)`，单测校验。
3. ROI = Shapley 贡献额（`φ_i/Σφ × 期间营收`）/ 月度成本；预算依据用 Shapley，运营展示用马尔可夫，两者并列可对照。
4. 新预算：`权重 = 当前预算 × (ROI/平均ROI)^0.7`，目标 = 总预算 × 权重占比；品牌搜索保底 12%；单渠道变动 ≤ ±30%；水位法迭代锁定触边渠道，残差补到最大渠道，保证合计恒等于总预算。
5. 失败态：无渠道/无触点 → 运行 `failed`/`partial` 并写日志；空路径 `v=0`，占比全 0，不抛错。

## 8. 共享枚举出现位置

| 枚举 | 后端 | 前端 |
|---|---|---|
| 角色 `admin/analyst/viewer` | `backend/src/constants/{roles,enums}.py` | `frontend/site/js/config.js` |
| 渠道类型 `search/feed/content/community/live` | `backend/src/constants/enums.py` | `frontend/site/js/config.js`（`ENUMS.channelType`） |
| 归因口径 `markov/last_click/shapley` | `backend/src/constants/enums.py` | `frontend/site/js/config.js`（`ENUMS.model`） |
| 复核状态 `pending/confirmed/dismissed` | `backend/src/constants/enums.py` | `frontend/site/js/config.js`（`ENUMS.review`） |
| 运行状态 `queued/running/success/partial/failed` | `backend/src/constants/enums.py` | `frontend/site/js/config.js`（`ENUMS.runStatus`） |

## 9. 目录

```text
backend/
  src/{config,constants,controllers,middlewares,models,routes,schemas,services,utils}
      services/algorithms.py        # 两个纯函数算法
      services/attribution_service.py  # 编排/落库/预算方案
  scripts/{business_seed.py,seed_demo.py,demo_config.py,worker_healthcheck.sh}
  migrations/001_core_tables.sql
  tests/{test_algorithms.py,test_security.py}
frontend/
  site/{index.html,css/{tokens,app}.css,js/{config,api,store,ui,app}.js,js/pages/*.js}
```

## 10. 环境变量

见 `.env.example`：`COMPOSE_PROJECT_NAME`、`FRONTEND_PORT=18207`、`BACKEND_PORT=19207`、`DB_PORT=17707`、`DB_*`、`JWT_SECRET`、`REDIS_URL`、`SEED_DEMO`、`RATE_LIMIT_*`、`APP_TIMEZONE_OFFSET_MINUTES`。

## 11. Docker 说明

- 5 个服务：`frontend`(Nginx 静态站) / `backend`(uvicorn) / `worker`(Celery) / `db`(MySQL 8.0) / `redis`，全部带 healthcheck。
- 命名卷 `db_data`、`redis_data`；`depends_on` 使用 `service_healthy`。
- Nginx：`location /api/ { proxy_pass http://backend:8000/; }` + SPA 回落。
- seed 幂等：用户按 email、渠道按 code、触点/转化按唯一 seed_key、运行按 seed_key；已存在即复用，不覆盖复核状态。

## License

内部演示项目，仅用于评测与教学。
