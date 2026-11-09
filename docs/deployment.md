# 部署到 GitHub Pages

部署由 `.github/workflows/pages.yml` 完成：推送到 `main` 后，从已提交的 `data/` 现场导出页面数据、构建，并发布到 GitHub Pages。页面数据不入库。

> 已发布：<https://sigangluo.github.io/hot-repos/>。`pages.yml` 与 `trending.yml` 都已在 GitHub 上手动运行成功；`trending.yml` 的定时触发尚待观察。

## 第一次发布

1. **确认提交身份**：本仓库已在本地配置为 GitHub 用户名与 noreply 邮箱，不影响全局配置。推送前建议到 GitHub 设置的 Emails 页核对 noreply 地址：
   ```bash
   git config user.name && git config user.email
   ```
2. **准备数据**：确认 `data/` 是想发布的快照，并通过校验：
   ```bash
   uv run hot-repos validate
   ```
3. **在 GitHub 上新建空仓库**（不要勾选自动生成 README、`.gitignore`、LICENSE），然后：
   ```bash
   git add -A
   git status            # 提交前确认没有 .cache/、.venv/、web/node_modules/、web/dist/、web/public/data/
   git commit -m "初始提交"
   git remote add origin git@github.com:<用户名>/hot-repos.git
   git push -u origin main
   ```
4. **启用 Pages**：免费账号只有公开仓库能用 Pages（私有仓库需要 Pro 或 Team 套餐）。仓库 Settings → Pages → Build and deployment → Source 选 **GitHub Actions**。随后重新运行一次 `Deploy to GitHub Pages` 工作流（Actions 页 → Run workflow）。
5. 部署成功后，地址形如 `https://<用户名>.github.io/hot-repos/`。构建使用相对路径，仓库改名不需要改配置。

## 更新数据

```bash
uv run hot-repos fetch --top 5000      # 采集；可中断，重跑续上
uv run hot-repos validate
git add data && git commit -m "数据更新：$(date +%F)"
git push
```

推送后 Pages 自动重新部署。

- **仓库体积**：每次更新会让 git 历史增加约 4MB（`data/` 中的 Parquet 无法增量压缩）。每天更新一年约 1.5GB，GitHub 建议仓库保持在 1GB 以下。可以降低更新频率（例如每周），或之后把历史快照挪到 GitHub Release。
- **首次完整采集约需 1 小时以上**：GitHub REST 每小时只有 5000 次额度，采集会在额度用完后自动等待重置，之后的更新命中缓存或只补抓缺口时会快得多。见 [operations.md](operations.md)。

## Trending 每日快照

`.github/workflows/trending.yml` 每天 01:30（UTC）运行 `hot-repos trending` 和 `hot-repos validate`，有新文件时用 `github-actions[bot]` 提交并推送到 `data/trending/`；也可以在 Actions 页面手动触发。抓取失败（页面结构变了、网络错误）时不产生文件，也不提交，Actions 里会显示失败。

- **需要的设置**：仓库 Settings → Actions → General → Workflow permissions 允许读写（工作流里已声明 `contents: write`，但仓库级设置更严格时会覆盖）。如果 `main` 开了分支保护，需要允许这个提交通过。
- **历史只能从第一次运行起积累**：页面不保留过去的榜单，所以越早启用越好。
- **仓库体积**：每天约 50 KB，一年约 18 MB，比总榜数据更新的增长慢得多。
- **自动部署**：用 `GITHUB_TOKEN` 推送的提交不会触发其他工作流，所以 `trending.yml` 在推送后用 `gh workflow run pages.yml` 显式触发 Pages 部署（工作流已声明 `actions: write`）。没有新快照时不推送，也不会部署。
- **定时任务可能延后**，长期没有仓库活动时 GitHub 可能停用定时任务；首次启用后的几天要确认它确实在运行。

## 持续集成

`.github/workflows/ci.yml` 在每次推送和 PR 上运行：

- Python：`ruff check`、`ruff format --check`、`pytest`（含对已提交 `data/` 的校验）、`hot-repos validate`。
- 前端：导出页面数据，再做类型检查、单元测试和构建。

提交前可在本地跑同样的检查：

```bash
uv run ruff check . && uv run ruff format --check . && uv run pytest -q
cd web && npm run typecheck && npm test && npm run build
```

## 发布前检查清单

- [x] `uv run hot-repos validate` 通过
- [x] 本地检查命令全部通过
- [x] `git status` 中没有缓存、虚拟环境、依赖目录和构建产物
- [x] LICENSE（MIT）已添加，`pyproject.toml` 与 `web/package.json` 的协议字段已填
- [x] Pages 来源已设为 GitHub Actions
- [x] 手动触发一次 Trending 工作流，确认能抓取、校验并推送、触发部署
- [ ] 确认 Trending 的定时任务（每天 01:30 UTC）真的在自动运行
