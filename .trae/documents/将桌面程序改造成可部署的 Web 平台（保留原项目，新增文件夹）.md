## 技术栈与总体思路
- 后端：Python + FastAPI（复用现有 `services/*`、`models/*`、`utils/*` 逻辑，提供 REST API 与实时进度通道）。
- 前端：React（Vite）或 Vue3（任选其一，默认 React），响应式设计适配手机/平板/PC。
- 实时进度：WebSocket（或 SSE），前端显示批量检查的进度与新增条目。
- 数据与缓存：沿用 SQLite 与现有缓存（页面缓存、图片缓存），统一放在后端。
- 部署：本地 `uvicorn` 开发、生产 `uvicorn + nginx`（或 Docker）；支持内网穿透（如 frp/ngrok）。
- 新建文件夹：`web-platform/`（保留原桌面端工程不变）。

## 目录结构（新增）
web-platform/
- backend/
  - app.py（FastAPI 入口）
  - api/（路由：书签、检查、日志、统计）
  - ws/（WebSocket 进度）
  - adapters/（将现有服务封装为可调用接口）
  - settings.py（后端配置，指向原有 DB 与缓存路径）
- frontend/
  - vite + React 项目（pages：Dashboard、Bookmarks、Updates、Logs、Settings）
- deploy/
  - docker-compose.yml、nginx.conf（可选）
  - scripts（一键启动/构建）

## 后端改造与 API
- 复用逻辑：直接 import 原项目 `check update/services/*`、`models/*`、`utils/*`；通过 `sys.path` 或将原项目视为模块（不复制代码，避免分叉）。
- API 路由
  - `GET /api/bookmarks`：列表
  - `POST /api/bookmarks`：新增
  - `DELETE /api/bookmarks/{id}`：删除
  - `POST /api/check`：批量检查（参数：`update_range_days`、是否使用缓存）
  - `GET /api/updates`：最近一次检查结果（分页）
  - `GET /api/stats`：综合统计（请求管理器、缓存、书签活跃度）
  - `GET /api/logs`：最近日志（支持等级过滤）
- 进度与实时（WebSocket `/ws/progress`）
  - 后端启动检查任务后，实时推送：当前、总数、速度、剩余时间；每发现新视频推送条目。
- 任务执行方式
  - FastAPI `BackgroundTasks` + `ThreadPoolExecutor`（复用原 `UpdateChecker` 并发）；或使用 `asyncio.to_thread`。
- 适配点
  - 将 `UpdateChecker` 的回调改为：发送到 WebSocket 与写入缓存；
  - `WebScraper` 与 `RequestManager` 保持原封装；注意不要使用桌面 UI 相关模块。

## 前端实现
- 首页 Dashboard：
  - 顶部操作：开始检查、选择时间范围。
  - 中部：进度条、剩余时间、提示；实时新增的更新卡片瀑布流（含缩略图、标题、时间、打开链接）。
- 书签管理：
  - 列表 + 搜索；新增/删除；导入 HTML（浏览器书签）
- 日志与统计：
  - 最近日志（分级过滤）
  - 请求统计、缓存大小、书签活跃度等图表（轻量组件）。
- 设置：
  - 并发数、域名并发、缓存 TTL、动效开关、主题切换。
- 移动端适配：
  - 响应式布局（栅格/卡片），大按钮与触控友好；侧滑菜单或底部导航条。

## 部署方案
- 开发：`uvicorn backend.app:app --reload` + `npm run dev`（Vite）；前端通过代理（`/api` 指向后端）。
- 生产：
  - 构建前端静态资源（`npm run build`）并由后端 `StaticFiles` 或 nginx 提供；
  - `uvicorn --workers N`；可选 Docker：`backend` + `frontend`（nginx serve）。
- 公网/内网穿透：提供 ngrok/frp 配置范例，手机与平板可直接访问。

## 数据与兼容
- 沿用原 `database.sqlite` 与缓存目录（`cache/*`、`logs/app.log`）；通过配置文件指向原项目路径。
- 保证新平台仅读取与调用原服务，不破坏现有桌面端功能。

## 安全与限流
- 简易令牌鉴权（Header `Authorization: Bearer <token>`）；
- 请求速率保护与域名并发保持，继续使用 `RequestManager`。
- CORS 配置允许手机/平板访问。

## 交付内容
- `web-platform/` 完整目录结构与代码；
- 一键启动脚本（Windows）：`scripts/dev.ps1`、`scripts/start.ps1`；
- README：运行与部署说明；
- 确保手机/平板通过局域网地址或穿透地址可用。

如确认，我将在新建 `web-platform/` 下搭好后端与前端的骨架，接入现有检查逻辑与实时进度，提供本地与生产运行脚本，并确保不修改原工程。