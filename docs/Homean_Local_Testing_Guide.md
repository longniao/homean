# Homean 本机测试指南

更新：2026-09-25。面向这台 Mac 上的日常开发与验收，不涉及 Mac mini 生产环境。

## 0. 前提

| 需要 | 本机现状 |
| --- | --- |
| Python 3.12 + uv，`backend/.venv` 已同步 | 已有 |
| Node 22，四个前端目录已 `npm ci` | 已有 |
| Docker（OrbStack） | 已有 |
| Xcode 26.5、Android SDK、Java 17、AVD `Medium_Phone_API_36.0` | 已有 |
| WeasyPrint 原生库 | `brew install pango`，运行后端时需要 `export DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib` |

一个已知坑：端口 55432 被另一个项目（kawu-playground）的 Postgres 占用，凭据不同。
后端测试和 e2e 默认连它会报"password authentication failed"。下面每一节都写了绕法。

## 1. 单元与集成测试（不需要真机、不花钱）

所有外部服务（S3、Deepgram、OpenAI、Anthropic、Stripe、Resend）在测试里都是假实现，不会产生费用。

### 后端

```sh
# 一次性起一个临时测试库，避开 55432
docker run -d --rm --name homean-test-pg -e POSTGRES_USER=homean -e POSTGRES_PASSWORD=homean \
  -e POSTGRES_DB=postgres -p 127.0.0.1:55499:5432 postgres:16-alpine

cd backend
export DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib
export TEST_DATABASE_ADMIN_URL=postgresql+asyncpg://homean:homean@127.0.0.1:55499/postgres
uv run ruff check . && uv run ruff format --check .
uv run pytest -q                      # 全量，约 2 分钟
uv run pytest -q tests/test_auth.py   # 单个文件

docker stop homean-test-pg            # 用完即删
```

每个 pytest 会话会自建一个随机名的数据库并跑完整 Alembic 迁移，所以迁移本身也被测到。

### dashboard / mobile / marketing

```sh
cd dashboard && npm run typecheck && npm run lint && npm test
cd mobile    && npm run typecheck && npm run lint && npm test
cd marketing && npm run typecheck && npm test
```

mobile 的 jest 用 `--runInBand`，约 2 秒；dashboard 的 vitest 约 3 秒。

### 端到端（Playwright，浏览器 → 代理 → 真实 API）

```sh
cd dashboard
TEST_DATABASE_ADMIN_URL=postgresql+asyncpg://homean:homean@127.0.0.1:55499/postgres npm run test:e2e
```

它会自己构建 dashboard、在 8001 端口起一个带假 AI 供应商的真实后端、在 3001 端口起 Next，跑完自动删库。
第一次运行前 `npx playwright install chromium`。

### 发布预检（构建镜像、校验 Compose 与迁移 head）

```sh
bash scripts/release_preflight.sh
```

## 2. 本地完整栈（手工点 App / dashboard 时用）

`scripts/local_stack.sh` 用生产用的 compose 文件起一套独立环境，项目名 `homean-local`，
端口 55433 / 6381 / 9010，API 在 8197，与开发用 compose 和其他项目互不干扰。

```sh
scripts/local_stack.sh up      # Postgres + Redis + MinIO，跑迁移，启动 API
scripts/local_stack.sh seed    # 建 homean-media 桶，创建测试账号
scripts/local_stack.sh status  # 看 /ready
scripts/local_stack.sh down    # 停掉并删除数据卷
```

测试账号：`drill@example.com` / `drill-password-1`。API 日志在 `.local/api.log`。
这套栈没有配 AI 密钥，上传后的带看会停在 Processing；要看真实报告生成，需要在
`.local/` 之外另行提供 `OPENAI_API_KEY` 并启动 worker，属于付费验收，另行安排。

### 让 dashboard 指向本地 API

```sh
cd dashboard
NEXT_PUBLIC_API_URL=http://127.0.0.1:8197 npm run dev   # http://localhost:3000
```

### 让手机 App 指向本地 API

| 目标 | 地址 |
| --- | --- |
| Android 模拟器 | `http://10.0.2.2:8197` |
| iOS 模拟器 | `http://127.0.0.1:8197` |
| 同一 Wi-Fi 下的真机 | `http://<这台 Mac 的局域网 IP>:8197` |

## 3. Android 模拟器

```sh
export PATH="$HOME/Library/Android/sdk/platform-tools:$HOME/Library/Android/sdk/emulator:$PATH"
emulator -avd Medium_Phone_API_36.0 &                 # 需要看画面就去掉 -no-window
adb wait-for-device

cd mobile
EXPO_PUBLIC_API_URL=http://10.0.2.2:8197 npx expo run:android
```

`expo run:android` 会做增量 gradle 编译、安装、启动 metro 并打开 App。首次全量编译约 5 分钟，之后几十秒。
只改 JS 时不用重新编译，App 会从 metro 热加载。

常用 adb：

```sh
adb shell pm grant com.homean.capture android.permission.RECORD_AUDIO
adb shell pm grant com.homean.capture android.permission.POST_NOTIFICATIONS
adb shell pm grant com.homean.capture android.permission.CAMERA
adb shell cmd uimode night yes        # 切深色模式（复现输入框文字变白那类问题）
adb shell cmd uimode night no
adb exec-out screencap -p > shot.png  # 截图
adb logcat | grep -E "ReactNativeJS|FATAL"
adb shell pm clear com.homean.capture # 清掉 App 数据，回到未登录状态
```

模拟器数据分区满了会报 `INSTALL_FAILED_INSUFFICIENT_STORAGE`，用 `emulator -avd Medium_Phone_API_36.0 -wipe-data` 重启一次即可。

## 4. iOS 模拟器与真机

```sh
cd mobile
EXPO_PUBLIC_API_URL=http://127.0.0.1:8197 npx expo run:ios            # 模拟器
EXPO_PUBLIC_API_URL=http://<Mac IP>:8197 npx expo run:ios --device    # 连线的 iPhone，需要 Apple 开发者签名
```

后台录音、飞行模式、强退恢复这些必须在真机上验收，模拟器不算数。步骤见 `mobile/README.md`。

## 5. 手工验收清单（每次改 App 后过一遍）

1. 注册新账号 → 进入主页显示 Signed in as。
2. Start Showing → 勾同意 → Begin recording → 计时走动。
3. 点 Voice Tag、Photo、Video：底部出现 toast，没有弹窗。
4. 开飞行模式 → End → 卡片显示 Offline；关飞行模式 → Sync now → 变为 Processing。
5. Sign out 再登录，未同步的带看还在。
6. Delete account：错密码提示、对密码后回到登录页，用旧密码登录返回 401。
7. dashboard 登录同一账号：Settings 能改名、改品牌、看到 Delete account 区块。

## 6. 备份与恢复演练（不碰生产）

```sh
BACKUP_AGE_IDENTITY=<age 私钥文件> bash infra/macmini/backup/restore_drill.sh --from-dir <本地快照目录>
```

它把快照恢复到隔离的 `homean-restore-drill` 项目里、核对 Alembic 版本和行数、起临时 API 要求 `/ready` 通过，结束后自动清理。

## 7. 不要在本机做的事

- 不要提交 expo.dev 云构建来调试，账号有额度限制；本机 `expo run:*` 或 `eas build --local` 足够。
- 不要在测试里接真实 AI、邮件、Stripe 密钥；真实验收单独安排并记录费用。
- 不要用 `ssh macmini` 跑测试，生产机只做部署。
