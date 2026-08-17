# YumeBox-IconKit

一个单体 Cloudflare Worker：Vue 前端由 Worker Assets 提供；浏览器裁剪图片并生成 Android mipmap ZIP，Worker 把 ZIP 临时存入 R2 后触发本仓库的 GitHub Actions。Action 只读检出 YumeBox，构建并上传两个 APK 工件，不会向 YumeBox 推送任何内容。

## 部署

1. `npm install`，之后使用 `npm run dev`、`npm run build` 或 `npm run check`。这些命令由项目本地的 Vite+ (`vp`) 执行。
2. 登录 Cloudflare：`npx wrangler login`，然后创建 R2 Bucket：

   ```bash
   npx wrangler r2 bucket create yumebox-iconkit-jobs
   ```

   R2 bucket 名称需要与 `wrangler.toml` 保持一致。Job 状态与 ZIP 都存放在此 Bucket，不需要 KV Namespace、账户 ID 或额外的部署环境变量。

3. 设置 Worker secret：`npx wrangler secret put GITHUB_TOKEN`。PAT 需要此仓库的 Actions workflow 写入权限；它只保存在 Cloudflare，不会下发到浏览器或 Actions。
4. 执行 `npm run build && npm run worker:deploy`。`dist` 会作为 Worker Assets 一并部署，不需要 Cloudflare Pages。部署后记录 Worker 的 HTTPS 域名，例如 `https://yumebox-iconkit.<account>.workers.dev`。
5. 在本仓库的 GitHub Actions Variables 设置 `ICON_WORKER_URL` 为该 Worker 域名（不带结尾 `/`）；在 Actions Secrets 设置签名变量：`SIGNING_KEYSTORE_BASE64`、`SIGNING_STORE_PASSWORD`、`SIGNING_KEY_ALIAS`、`SIGNING_KEY_PASSWORD`。

> 该 API 会触发付费的 GitHub Actions，不能把 Worker 当作匿名公共接口。部署到公开域名前，请在 Cloudflare 为该域名启用 Access，或在 Worker 前接入 Turnstile 与速率限制；`ALLOWED_ORIGINS` 只限制浏览器 CORS，不能阻止 `curl` 直接调用。

工作流 [build-icon.yml](.github/workflows/build-icon.yml) 固定只读检出 `YumeYucca/YumeBox` 的 `Yume` 分支，不会推送任何变更。它只上传 builtin 和 external 两个 APK，保留 7 天。若目标仓库改为私有仓库，请为 `actions/checkout` 增加一个仅有 Contents Read 权限的仓库访问 token。

Worker 调度成功后，前端先显示工作流列表链接。Action 一启动就以随机回调令牌通知 Worker，前端轮询 `/v1/jobs/:jobId` 后将链接更新为这一次的 `actions/runs/:runId` 直达链接；构建完成或失败也会回写状态。ZIP 下载令牌 15 分钟后失效，R2 对象在 Action 成功下载后立即删除；Job 状态仅保留 24 小时。建议额外在 R2 为 `jobs/` 前缀设置 1 天生命周期规则，处理因 Action 未启动而遗留的 ZIP。

图标 ZIP 和下载令牌会在 Action 下载成功后删除；未使用的对象由 R2 生命周期规则删除，建议设置 `jobs/` 前缀 1 天过期。

## 图标包格式

ZIP 遵循 [Android Asset Studio Launcher Icon](https://github.com/romannurik/AndroidAssetStudio) 的目录和资源命名：

- `res/mipmap-{mdpi,hdpi,xhdpi,xxhdpi,xxxhdpi}/ic_launcher.png`：legacy launcher 图标，边长依次为 `48/72/96/144/192 px`。
- 同一目录的 `ic_launcher_adaptive_back.png` 与 `ic_launcher_adaptive_fore.png`：Adaptive Icon 背景和前景层，边长依次为 `108/162/216/324/432 px`。
- `res/mipmap-anydpi-v26/ic_launcher.xml`：标准 Adaptive Icon 定义。
- `play_store_512.png`、`1024.png`：商店和高分辨率预览图。

构建工作流将标准 Adaptive 层映射到 YumeBox 当前使用的 `ic_launcher_background.png` 与 `ic_launcher_foreground.png`，并用 Asset Studio XML 覆盖原定义。新的 XML 不含 Android 13 `monochrome` 层，因此不会启用 themed/Monet 图标适配。
