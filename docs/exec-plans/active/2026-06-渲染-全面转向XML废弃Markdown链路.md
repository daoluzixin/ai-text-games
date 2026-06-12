# 执行计划：全面转向 XML 结构化渲染，废弃 Markdown 链路

## 背景

前端 AI 消息渲染当前有两条链路（均在 `static/md-frame.html`）：

- **XML 链路**：`renderXml()` 用 `DOMParser` 解析 `<scene>` 下的 `narration/dialogue/status/choices`，结构化渲染成卡片。机器可解析，稳定。
- **Markdown 链路**：`sanitizeMarkdown` → `smartParagraph` → `marked.parse` → `postProcessChoices`，一整套靠正则猜测的"防御性补丁"（竖线转全角、反引号补全、`**` 配对修复、选项行正则识别）。LLM 输出格式稍有漂移就会渲染错乱。

排查发现"渲染不稳定"的真正根因有两层：

1. **format 信号断链（致命）**：后端流式结束会发 `[FORMAT:XML]`，前端把它存进局部变量 `contentFormat`，但流结束后 `addMessage('assistant', aiMessage)`（`index.html` 第1479行）**没有把 `contentFormat` 传进去**；`addMessage` 内发 `md-update`（第1528行）**也没带 `format` 字段**。md-frame 收到无 format 的更新，`currentFormat` 默认就是 `'MARKDOWN'`。
   → **结论：XML 渲染链路从未被真正触发过，全站消息一直走脆弱的 Markdown 链路。**
2. **fallback 太脆**：后端 `ET.fromstring` 校验，XML 只要有一处不合法（未转义的 `&`、未闭合标签等）就发 `[FORMAT:MARKDOWN]`，整段掉进 Markdown。

此外，历史回填（`loadSessionHistory` 第1362行）拿到的是存库原始文本，**根本没有 format 信号**——format 信号只在流式时发，读档时不发。

## 目标

1. **XML 成为唯一主渲染路径**，全站 AI 消息默认按结构化 XML 渲染。
2. **前端自主判断格式**：以内容是否为 `<scene` 开头作为判据，不再依赖后端的 `[FORMAT:*]` 信号（读档场景也能正确渲染）。
3. **XML 渲染容错**：半残/流式未闭合的 XML 也尽力结构化渲染，绝不掉回 Markdown 正则链路。
4. **Markdown 链路降级为纯文本兜底**：仅当内容完全不是 XML 时，做最小化的转义+换行展示，删除全部脆弱正则补丁。
5. 顺手把 `<status>` 卡片升级成截图效果（分组标题 + emoji 图标 + 好感度进度条）。

## 方案

### 改动文件
- `index.html`：修复 format 断链，让 `addMessage` / 历史回填正确传递格式。
- `static/md-frame.html`：加固 XML 渲染、升级 status 卡片、降级 Markdown 兜底。
- `server.py`：扩展 XML 格式约束（status 分组/数值字段），保持向后兼容。

### 1. 前端格式判定改为自主决策（index.html + md-frame.html）
- `addMessage('assistant', content)`：不再依赖外部 format，把原始 content 原样交给 iframe。
- md-frame `renderContent`：内容 `trim()` 后以 `<scene`（或去掉 ```xml 包裹后）开头 → 走 XML；否则走纯文本兜底。
- 保留后端 `[FORMAT:*]` 信号但不再作为渲染依据（向后兼容，前端忽略即可）。

### 2. XML 容错解析（md-frame.html `renderXml`）
- DOMParser 解析失败时，**不返回 null 掉回 Markdown**，改为：尝试用正则逐标签提取 `<narration>/<dialogue>/<status>/<choices>` 的内容做"宽松解析"，尽量结构化。
- 流式途中未闭合也能渲染已到达的部分。
- 实在无法识别任何标签时，才退到纯文本兜底。

### 3. status 卡片升级（md-frame.html）
- 支持分组：`<status title="主播状态">...</status>` 多个并列，渲染成带标题的分组卡片。
- 支持图标：`<item label="好感度" icon="❤️">` 可选 icon 属性。
- 支持进度条：`<item label="好感度" type="bar" max="100">85</item>` 渲染成进度条 + 百分比。
- 无新属性时回退到原有平铺渲染（向后兼容旧存档）。

### 4. Markdown 降级（md-frame.html）
- 删除 `sanitizeMarkdown` / `smartParagraph` / `postProcessChoices` 的脆弱逻辑（或保留函数但兜底路径不再调用 marked 的复杂解析）。
- 纯文本兜底：仅做 HTML 转义 + 换行转 `<br>` + 段落包裹。
- 可考虑后续移除 marked.js 依赖（本次先不删脚本引用，降低风险）。

### 5. 后端格式约束扩展（server.py）
- 在 XML 格式说明中补充 status 的分组/icon/进度条用法，引导 LLM 输出更丰富的状态结构。
- **向后兼容红线**：不删除/重命名既有标签与属性，全部为新增可选项；旧存档（扁平 status）仍能正常渲染。

## 不做的事
- 不改后端单文件架构、不引入前端构建。
- 不动头像随机分配逻辑。
- 不部署到生产服务器（本次仅本地开发验证）。

## 验证
1. `bash scripts/harness-lint.sh` 通过（0 FAIL）。
2. 本地启动 server，浏览器实测：
   - 正常 XML → 结构化卡片渲染。
   - 故意构造半残 XML（缺闭合标签、未转义 `&`）→ 仍结构化，不出现 Markdown 正则错乱。
   - 含分组 + 进度条的 status → 对齐截图效果。
   - 读档（历史回填）→ XML 正确渲染（验证 format 断链已修）。
   - 纯文本/非 XML → 纯文本兜底正常。
