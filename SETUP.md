# 部署说明（照抄即可）

## 0. 提交身份：用 GitHub 匿名邮箱，别用真实邮箱

贡献图的判定规则是：**提交邮箱必须和你的 GitHub 账号关联**。有两种选择：

| 方案 | 写法 | 结果 |
| --- | --- | --- |
| ✅ **推荐：GitHub 匿名邮箱** | `<数字ID>+<用户名>@users.noreply.github.com` | 自动绑定你的账号 → **贡献照算**，但公开提交历史里看不到你的真实邮箱 |
| 真实邮箱 | 你在 GitHub 加过并验证过的邮箱 | 也会算贡献，但**你的真实邮箱会出现在每一个公开提交里**，任何人都能爬 |

数字 ID 查法：登录后在 `https://api.github.com/users/<你的用户名>` 里看 `"id"` 字段，
或直接打开 https://github.com/settings/emails 看 *Keep my email addresses private* 下方给出的那串地址。

本仓库已按匿名邮箱配置好（默认值写在 `.github/workflows/daily.yml` 里），
也通过仓库变量 `GIT_NAME` / `GIT_EMAIL` 覆盖，一般不用改。

> **检查本地 git 用的是什么**：`git config user.email`。如果是真实邮箱，而且你要在这个仓库手动提交，
> 记得先执行 `git config user.email "<你的匿名邮箱>"`（不加 `--global` 就只对当前仓库生效）。

## 1. 建仓库并推上去

### 方式 A：命令行

```bash
cd daily-arxiv-digest
git init -b main
git add -A
git commit -m "feat: 每日 arXiv 论文雷达（Actions 自动日报）"
gh repo create daily-arxiv-digest --public --source . --remote origin --push
# 没有 gh 的话：先建空仓库，再
#   git remote add origin https://github.com/<你的用户名>/daily-arxiv-digest.git
#   git push -u origin main
```

### 方式 B：网页拖拽

1. 新建公开仓库（public 免费跑 Actions）。
2. `Add file` → `Upload files`，把本目录下所有文件拖进去，注意 `.github` 文件夹要一起（Windows 里需先勾选"显示隐藏文件"）。
3. Commit。

## 2. 给 Actions 写权限

仓库 → `Settings` → `Actions` → `General` → 最下方 **Workflow permissions**
选 **Read and write permissions** → Save。

不选的话，工作流最后那步 `git push` 会 403（报错 `remote: Permission denied`）。

## 3.（可选）用仓库变量传提交身份

`Settings` → `Secrets and variables` → `Actions` → `Variables` 新建：

| Name | Value |
| --- | --- |
| `GIT_NAME` | 你的用户名 |
| `GIT_EMAIL` | `<数字ID>+<用户名>@users.noreply.github.com` |

不建也行，`daily.yml` 里已经有默认值。

## 4. 立刻验证一遍

仓库 → `Actions` → 左侧选 **Daily arXiv Digest** → `Run workflow` → 跑完检查：

- 有没有出现 `digests/YYYY-MM-DD.md`
- README 下方索引表有没有多一行
- 提交作者是不是你
- 隔天看自己的 GitHub 首页贡献图有没有变绿

## 常见问题

| 现象 | 原因 / 解决 |
| --- | --- |
| 定时任务不触发 | 公开仓库 **60 天完全没有提交** 时 GitHub 会自动停用定时器。本工作流每天都提交，正常不会触发；万一停了，手动 Run 一次即复活 |
| 跑完没有新提交 | 当天内容与仓库里已有文件完全一致，脚本判定"无变化"跳过。当天有新论文时不会有这个问题 |
| 跑完日志报 `Rate exceeded` | 说明 RSS 被限流，脚本会自动退回 arXiv API 重试；两条源都挂时仍会写一份说明文件，不会断更 |
| 时间是半夜/早上 | `cron` 用 UTC。`17 22 * * *` = 北京 06:17。想改北京时间 X 点 → `17 X-8 * * *`（跨 0 点要自己绕） |
| 绿格子还是不亮 | 提交邮箱和账号没关联上，回第 0 步换用匿名邮箱 |
| 想加更多分类 | 改 `config.json` 的 `categories`，例如加 `cs.AI`、`stat.ML` |

## 想再加一层

- **个人主页 README**：建一个和用户名同名的仓库（如 `<用户名>/<用户名>`），放 `github-readme-stats`
  统计卡与 `github-readme-streak-stats` 连续提交卡。
- **刷题自动同步**：LeetHub 类浏览器插件，做一题自动提交一题（真实产出，面试有用）。
- **不推荐**：`bcanseco/github-contribution-graph-action`、`gitfiti` 这类空提交/回填历史的做法。
  技术上最快，但提交信息全是 `chore: empty commit`，点进去就露馅，收益是负的。
