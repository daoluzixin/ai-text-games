# AI 文游游戏厅 — Agent 导引

> 本文件只做导航，不承载项目说明和规则细节。

## 当前仓库定位

这是 **ai-text-games** 的部署仓库（非 monorepo），包含前后端全部代码和运维配置。
线上服务运行在阿里云 ECS `39.106.187.120`，端口 8080。

## 首读顺序

拿到任何任务时，如果对本项目还不熟悉，按以下顺序阅读：

1. `docs/agents/目元信息.md` — 项目背景、阶段、核心概念
2. `docs/agents/核心架构.md` — 目录结构、模块职责、技术栈
3. `docs/agents/工程约束.md` — 命名风格、代码规范、不可违反的红线
4. `docs/agents/自反馈工作流.md` — 代码写完之后怎么验证

## 按场景查文档

| 场景 | 文档 |
|------|------|
| 要做一个新功能 | 先在 `docs/exec-plans/active/` 写执行计划 |
| 想了解当前进行中的任务 | 查 `docs/exec-plans/active/` |
| 想看历史完成的任务 | 查 `docs/exec-plans/completed/` |
| 需要查执行日志 | 查 `docs/exec-plans/activeLog/` |
| 部署/运维相关 | 查 `docs/agents/目元信息.md` 的部署章节 |
| 自反馈验证流程 | 查 `docs/agents/自反馈工作流.md` |

## 自动化守卫

提交代码前必须通过 lint 检查：

```bash
bash scripts/harness-lint.sh
```

0 FAIL 才允许 push。
