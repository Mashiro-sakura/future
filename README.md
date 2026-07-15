# 期现分析推送系统

这是一个从零搭建的三端项目，用于每日推送 PTA、PVC、LLDPE、PP、沪铅、棕榈油、丙烯、PX、沪铜、辛醇的行情分析、持仓变化和采购建议。期货价格展示口径按主力合约处理，并在页面中显示当前主力合约代码；辛醇按现货品种跟踪，不纳入期货主力合约分析。日报分析包含价格行为、基本面、宏观面、政策面四个维度。

## 项目结构

- `backend/`：FastAPI + SQLite 后端，含公开客户 API、后台管理 API、行情同步、日报生成、企业微信和微信小程序订阅消息推送。
- `admin-web/`：Vue3 + Vite + Element Plus 后台管理端。
- `customer-miniapp/`：uni-app Vue3 微信小程序客户面，同时包含 `index.html` H5 预览页。

## 后端启动

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

默认后台账号为 `admin / admin123`。生产环境请在 `backend/.env` 或系统环境变量中修改 `JWT_SECRET`、`ADMIN_PASSWORD` 和 `WECHAT_WORK_WEBHOOK_URL`。

## 后台管理端

```powershell
cd admin-web
pnpm install
pnpm dev
```

访问 `http://127.0.0.1:5173`。后台可同步行情、生成日报、编辑采购建议、发布到客户面并推送企业微信。

## 客户端小程序

```powershell
cd customer-miniapp
pnpm install
pnpm dev:h5
pnpm build:mp-weixin
```

H5 预览访问 `http://localhost:5174`。微信小程序构建产物在 `customer-miniapp/dist/build/mp-weixin`，可导入微信开发者工具。

如果只是想快速看客户面效果，可以直接打开 `customer-miniapp/index.html`；它会优先请求 `http://127.0.0.1:8000`，后端未启动时显示兜底演示数据。

## 数据和推送

- 期货公开数据会先批量请求新浪 `nf_合约代码` 实时行情，并按持仓量/成交量动态识别各期货品种主力合约；首页期货栏显示该主力合约最新价，历史趋势用日线或演示数据补齐，且真实价与演示历史不混算涨跌幅/持仓变化。辛醇为现货品种，只同步现货报价、库存、开工率和产业链分析，不生成期货主力合约价格。
- 需要启用 AKShare 时额外执行 `pip install -r backend/requirements-akshare.txt`。
- 现货数据支持公开接口尝试和后台 CSV 导入兜底；系统按华东、华南、西南三地区保存每日现货报价，首页和趋势图默认以华东为主报价口径，基本面分析展示三地区报价和区域价差。
- 基本面分析同时结合开工率、社会库存、工厂库存和四个库存周期，判断是否出现供需失衡。
- 政策面每日按品种更新安全生产、环保、检修三类消息；若出现影响整体供需平衡的突发大事件，可在后台“政策事件”录入，选择影响品种并勾选立即推送，系统会生成“突发快讯”并在客户面和企业微信中置顶展示重大供需事件。
- 库存数据按社会库存、工厂库存两类保存到 `inventory_snapshots`；当前保留演示/估算序列作为兜底，基本面分析会结合总库存变化识别主动补库存、被动去库存、主动去库存、被动补库存四个库存周期。
- CSV 格式：

```csv
product_code,trade_date,price,region
PTA,2026-07-09,5910,华东
PVC,2026-07-09,5580,华东
```

- 每个工作日 `08:30` 和 `17:30` 自动同步、生成、发布并推送。
- 企业微信推送配置环境变量：

```powershell
$env:WECHAT_WORK_WEBHOOK_URL="https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=..."
```

## 微信小程序订阅消息

订阅消息已经接入客户面首页的“订阅日报”按钮。用户授权后，后端只保存 `openid`、订阅模板和可发送次数；日报发布或后台点击推送时，会同时尝试企业微信和小程序订阅消息。订阅消息不依赖企业微信。

1. 在微信公众平台的小程序后台开通订阅消息，选择一个适合日报提醒的模板，复制模板 ID 和模板字段 ID（例如 `thing1`、`time2`）。
2. 在 [customer-miniapp/src/manifest.json](customer-miniapp/src/manifest.json) 与根目录 `customer-miniapp/manifest.json` 填入自己的小程序 AppID；不要把 AppSecret 放到小程序前端。
3. 将 `backend/.env.example` 中的 `WECHAT_MINIAPP_*` 和 `WECHAT_SUBSCRIBE_*` 配置复制到实际 `backend/.env`，填入 AppID、AppSecret、模板 ID。`WECHAT_SUBSCRIBE_TEMPLATE_DATA` 的键必须与所选模板字段 ID 完全一致；可用的占位符为 `{title}`、`{report_date}`、`{published_at}`、`{session}`、`{summary}`、`{recommendation}`。
4. 配置 `customer-miniapp/.env` 的 `VITE_API_BASE` 为可从公网访问的 HTTPS 后端地址，并在微信公众平台的“开发管理/开发设置”登记该 HTTPS 地址的服务器域名。开发者工具调试时将 `WECHAT_MINIAPP_STATE=developer`，正式发布前改为 `formal`。
5. 执行 `pnpm build:mp-weixin`，将 `customer-miniapp/dist/build/mp-weixin` 导入微信开发者工具。用户点击“订阅日报”并同意授权后，下一次早报、晚报或后台手动推送即可发送通知并跳转到对应日报。

微信的一次性订阅消息通常一次授权只可发送一次，系统在发送成功后自动扣减一次授权。若要每天持续提醒，需要引导用户再次授权，或在小程序后台符合条件时申请长期订阅消息能力。

## 测试

```powershell
cd backend
pytest
```

前端构建检查：

```powershell
cd admin-web
pnpm build

cd ../customer-miniapp
pnpm build:h5
```
