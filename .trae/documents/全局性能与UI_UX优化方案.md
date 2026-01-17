## 总览
- 范围：网络抓取性能、并发与速率控制、解析与缓存、错误与反爬应对、UI信息架构与视觉样式、线程与主线程阻塞、可观测性与配置化。
- 目标：缩短单次检索时间、提升批量更新吞吐、减少误封禁与无效重试、降低UI布局开销并提升可用性与美观度。

## 抓取与并发优化
1. 统一并发入口
- 在 UI 线程中改为一次性调用 `UpdateChecker.check_all_bookmarks()` 收敛并发，避免当前 `UpdateCheckThread.run` 中逐个调用导致总体串行（ui/qt_main_window.py:35-76）。
- 在 `UpdateChecker` 中保留进度回调现有机制（services/update_checker.py:19-22, 57-60），驱动 UI 进度条。

2. 线程安全的会话管理
- 现有 `WebScraper` 持有一个 `requests.Session` 且被 `ThreadPoolExecutor` 多线程共享，存在线程安全隐患（services/update_checker.py:11-16, 13）。
- 方案：为抓取器引入线程本地会话，或在执行体内按需创建短生命周期 `Session`；或“每 worker 一个 `WebScraper`”。

3. 域名级并发与节流
- 在 `RequestManager` 增加“域名并发上限”，例如每域名并发≤2；在 `should_wait` 中综合 `domain_current_concurrency` 判断（services/request_manager.py:54-93）。
- `UpdateChecker` 按域名分桶将任务打散，优先跨域并发、域内串行或限流，减少单域热点导致的封禁。

4. 重试与退避联动
- 已有指数退避与抖动（services/request_manager.py:127-142），将其上限与步进纳入配置；当检测到 Cloudflare/429 时乘以系数放大（web_scraper.py:198-207）。
- 将“软失败计数”与全局封禁联动，避免短页面直接加速封禁（已修）。

## 解析与准确性
1. 域名感知有效性
- 保持 `is_valid_html_for_domain` 的结构特征判断以替代长度阈值（services/web_scraper.py:150），在站点更新时仅扩展特征列表即可。

2. 选择器与解析缓存
- 将解析用的选择器编译/缓存，减少重复正则与查询开销（web_scraper.py:351-369 附近选择器集）。
- 对大页面使用分区解析：先粗选容器，再细解析视频项。

## 缓存与网络往返
1. 页面缓存策略
- `PageCache` 支持内存+磁盘缓存（utils/page_cache.py:30-35, 71-97）。为批量更新开放“新鲜度优先”策略：
  - UI 勾选“启用缓存优先”，先读缓存快速渲染；后台异步验证是否过期后差量更新。
  - 支持按域名/URL设置 TTL（默认 300s，可在 config 中配置）。

2. 条件请求
- 如果站点支持，添加 `If-Modified-Since`/`ETag` 验证，返回 304 时直接用缓存，减少带宽与封禁概率。
- 不支持时可用“首屏轻载”策略：先抓短超时的 HEAD 或小资源探测，命中后再发完整 GET。

## 反爬与鲁棒性
- 保持 Cloudflare/429/403 分支处理（web_scraper.py:223-274）。
- 引入付费代理池接口与健康度评分，优先路由到高成功率代理；失败快速降权与替换。
- 为挑战页提供可选 Playwright/Selenium 降级通道，仅在连续软失败≥N时触发。

## UI 信息架构
1. 列表虚拟化与模型化
- 用 `QListView + QAbstractListModel` 重构书签与更新列表，替代 `QScrollArea` + 动态 QWidget/Frame（ui/qt_main_window.py:301-308, 339-345），降低大量 item 布局开销。
- ItemDelegate 定制渲染，异步图片绑定、占位骨架屏，显著提升滚动与渲染性能。

2. 非阻塞 UI
- 所有抓取与解析在工作线程；主线程只收增量结果与更新 UI。
- 图片加载统一限流（并发≤4），仅加载可见项；滚动触发懒加载。

3. 操作入口与反馈
- 顶部工具栏分组：刷新、设置、统计、清空维持（ui/qt_main_window.py:315-336），补充“日志查看”“代理状态”入口。
- 清晰的进度区与状态栏：显示当前并发、速率限制命中、失败/封禁域名计数（services/request_manager.get_statistics 用于 UI 显示）。

4. 细节交互
- 可筛选与搜索：书签快速搜索、更新列表过滤（时间范围、已看/未看）。
- 右键菜单统一：打开、复制链接、标记已看、移除书签等。

## 视觉样式与一致性
- 现有暗色 QSS 较完整（ui/style.qss），优化方向：
  - 提升对比与层次：卡片阴影、悬浮态统一；减少过度渐变造成“旧感”。
  - 统一尺寸与间距：8/12/16 的 spacing 体系，统一按钮最小尺寸。
  - 图标与字体：引入矢量图标集（Feather/Material），主字体使用 `Microsoft Yahei UI` 或 `Inter`。
  - 动画节制：交互动画 150–200ms，避免拖沓。

## 可观测性与日志
- 为短内容与挑战页保留诊断日志，但将详细片段仅在 debug 模式记录，避免噪音（web_scraper.py:326）。
- UI 增加“日志查看器”面板：分类显示 WARNING/ERROR，支持复制与导出。
- 统计面板展示 `RequestManager.get_statistics()` 返回的数据（services/request_manager.py:144-156）。

## 配置与可调参数
- 在 `config/settings.py`/`anti_ban_config.py` 增加：
  - `MAX_WORKERS`、每域并发与速率阈值、缓存 TTL、软失败阈值、代理池配置、降级触发阈值。
- 设置页（SettingsDialog）添加这些开关与范围（ui/qt_main_window.py:133-215），并做即时校验。

## 代码整洁与结构
- 分层清晰：UI（视图/交互）、服务（抓取/解析/调度）、模型（数据库）、工具（缓存/图片）。
- 明确线程边界与数据流：线程安全的集合/会话、不可变 DTO 在跨线程传递。
- 单元测试：解析器选择器与 `is_valid_html_for_domain` 的正反例；请求管理器封禁与退避策略的边界测试。

## 交付与渐进改造
1. 第一阶段（性能基线）
- UI 调用收敛至 `check_all_bookmarks` 并打通进度回调；线程安全会话与域名并发限制；图片加载限流与懒加载。
2. 第二阶段（UX 重构）
- 列表模型化 + ItemDelegate；新增状态栏与日志面板；设置加开关与范围控制。
3. 第三阶段（网络与反爬）
- 代理池健康度与降级策略；条件请求/首屏轻载；更细致的域名适配校验。

## 预计收益
- 批量更新时间明显缩短（跨域并发与列表虚拟化）；
- 封禁率下降（软失败与域名限流、会话隔离）；
- UI 流畅度与美观度提升（模型化渲染与统一样式）。

请确认以上方案，我将按阶段逐步实施并提供可视化验证与对比数据。