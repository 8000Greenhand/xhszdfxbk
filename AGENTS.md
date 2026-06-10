# AGENTS.md — 小羊森林内容工作台项目上下文

## 项目定位

这个仓库是「小羊森林内容样本与合作复盘工作台」，不是普通爆款库。

核心目标：把小红书内容样本、达人合作笔记、官号发布笔记、产品资料、用户原声沉淀成一个可长期复盘和转译的工作台，帮助小羊森林做更稳定的小红书内容选题、拆解、复刻和转化。

用户是小羊森林小红书内容运营，主要关注：

- 市场参考样本是否值得拆；
- 达人合作笔记是否值得复投；
- 官号发布笔记哪里影响点击、商品点击和成交；
- 产品资料如何辅助 GPT 分析；
- 用户评论/原声如何转成选题和文案依据。

请不要把这个项目理解成单纯的爬虫工具、收藏夹或通用 CRM。

---

## 当前工作台模块

### 1. 市场参考样本

用途：记录外部爆款、竞品、跨领域参考内容。

重点分析：

- 为什么吸引点击；
- 为什么有人收藏；
- 评论区暴露了什么需求；
- 结构能不能转成小羊森林官号内容；
- 哪些地方不能照抄；
- 适合承接哪个产品；
- 是否值得继续拆解。

市场参考样本右侧应该展示公开互动数据：

- 点赞；
- 收藏；
- 评论。

不要给市场参考样本展示「曝光/播放、商品点击、订单/GMV」作为主要指标，因为这些不是公开市场样本能稳定获得的数据。

### 2. 达人合作笔记

用途：记录达人合作内容。

重点分析：

- 达人人群是否匹配；
- 种草是否自然；
- 评论区是否有购买/需求信号；
- 数据追踪是否完整；
- 花费与性价比；
- 是否值得复投；
- 下次 brief 怎么改。

达人合作右侧可以展示：

- 曝光/播放；
- 商品点击；
- 订单/GMV。

前提是用户补充了平台数据或后台截图数据。

### 3. 官号发布笔记

用途：复盘小羊森林自己发布的官号内容。

重点分析：

- 封面标题是否有点击力；
- 第一页是否承接标题；
- 产品出现位置是否合适；
- 商品点击和成交链路；
- 是否值得系列化；
- 下一篇怎么改。

官号发布右侧可以展示：

- 曝光/播放；
- 商品点击；
- 订单/GMV。

### 4. 产品资料库

用途：上传或粘贴产品资料，生成产品卡，辅助后续 GPT 分析内容承接方向和合规边界。

当前支持：

- PDF；
- docx；
- pptx；
- xlsx；
- txt / md / csv / json / html。

注意：

- 扫描版 PDF 可能无法提取文字；
- .doc / .ppt 老格式暂不支持，建议转换为 .docx / .pptx；
- 上传文件只是本地浏览器提取文字，用户仍需点击「生成产品卡」。

### 5. 用户原声库

用途：沉淀评论、私信、客服、达人评论中的真实用户表达。

用户原声后续可用于：

- 找选题；
- 找封面钩子；
- 找购买顾虑；
- 找产品卖点表达；
- 判断内容是否贴近真实需求。

---

## 当前重要文件

```txt
workbench/server.py
workbench/static/index.html
workbench/static/app.js
workbench/static/styles.css
workbench/static/sample-card-overrides.js
启动小羊森林内容工作台.bat
data/workbench_v2.json
analysis_inbox/
analysis_results/
outputs/
```

### 不要轻易删除或绕过 `sample-card-overrides.js`

当前样本卡片展示逻辑有一部分通过：

```txt
workbench/static/sample-card-overrides.js
```

覆盖原 `app.js` 中的卡片渲染。

这样做是为了快速修复卡片展示，不大改已有 `app.js`，也避免缓存和大文件覆盖问题。

当前 `index.html` 底部应加载：

```html
<script src="/app.js?v=20260610-card-title"></script>
<script src="/sample-card-overrides.js?v=20260610-card-title"></script>
```

后续如果继续改卡片结构，优先改 `sample-card-overrides.js`。

---

## 缓存问题固定处理规则

这个项目之前反复遇到：GitHub 已更新，但桌面入口打开还是旧页面。

根因：浏览器缓存了旧的 `app.js` / `index.html`。

已经把启动器改成动态版本号：

```bat
for /f %%i in ('powershell -NoProfile -Command "Get-Date -Format yyyyMMddHHmmss"') do set "CACHE_BUST=%%i"
set "WORKBENCH_URL=http://127.0.0.1:8765/?v=%CACHE_BUST%"
```

因此以后修改前端后，不要再让用户手动换固定 `?v=xxx`。正常流程是：

```bat
cd /d C:\Users\Yunxi\Documents\自动拆解视频
git pull --ff-only origin main
```

然后关闭旧黑窗口和旧网页，重新双击桌面入口。

检查启动器是否正确：

```bat
findstr /n "CACHE_BUST WORKBENCH_URL" 启动小羊森林内容工作台.bat
```

如果桌面入口仍打开旧页面，优先检查桌面快捷方式是否指向了正确的 bat 文件：

```txt
C:\Users\Yunxi\Documents\自动拆解视频\启动小羊森林内容工作台.bat
```

不要轻易判断成“数据源没有返回”。如果截图里字段或布局没有变，首先怀疑：

- 本地没有 pull；
- 旧服务还在跑；
- 浏览器缓存；
- 桌面快捷方式指向旧文件。

---

## 当前已修复状态

### 市场参考右侧指标

已从：

```txt
曝光/播放
商品点击
订单/GMV
```

改为：

```txt
点赞
收藏
评论
```

当前测试样本显示：

```txt
110 点赞
75 收藏
17 评论
```

### 链接不再作为主标题

之前市场参考样本主标题显示完整链接：

```txt
https://www.xiaohongshu.com/explore/...
```

现在应优先显示笔记标题：

```txt
就喜欢好吃又健康的零食
```

作者显示：

```txt
墩妈JINA
```

链接只保留在右侧按钮：

```txt
打开原笔记
```

---

## 当前还未完成的新需求

用户刚提出：卡片主视觉应该是「博主名称」，不是「笔记标题」。

当前显示大概是：

```txt
市场参考 · 不确定 · 完整分析
就喜欢好吃又健康的零食
墩妈JINA
```

用户希望改成：

```txt
墩妈JINA
市场参考 ｜ 图文/视频 ｜ 上传日期

就喜欢好吃又健康的零食
```

也就是：

1. 博主/账号名放大，作为主标题；
2. 第二行显示：样本类型 + 内容类型 + 上传日期；
3. 笔记标题变成小一号的辅助标题；
4. 原始链接仍只放右侧「打开原笔记」按钮；
5. 右侧点赞/收藏/评论保持不变。

优先修改文件：

```txt
workbench/static/sample-card-overrides.js
```

建议加入日期裁剪函数，避免显示具体时分秒：

```js
function dateOnlyOverride(value) {
  const text = String(value || "").trim();
  const match = text.match(/\d{4}-\d{2}-\d{2}/);
  return match ? match[0] : "";
}
```

建议卡片结构改为：

```js
const author = item.creator || analysisMeta.author || "账号未知";
const title = readableSampleTitleOverride(item, analysisMeta);
const dateText = dateOnlyOverride(item.publishDate || item.createdAt || result?.status?.created_at || "");
const metaLine = [item.sampleType, item.contentForm || "未识别", dateText].filter(Boolean).join(" ｜ ");

<h3>${esc(author)}</h3>
<p class="muted">${esc(metaLine)}</p>
<p class="note-title">${esc(title)}</p>
```

如果新增 `.note-title` 样式，可以改 `workbench/static/styles.css`，但不要大改视觉体系。

---

## 当前测试样本

```txt
URL:
https://www.xiaohongshu.com/explore/6a17b0e100000000080313c3

标题：
就喜欢好吃又健康的零食

作者：
墩妈JINA

点赞：110
收藏：75
评论：17
```

分析包：

```txt
analysis_inbox/20260609-155404_6a17b0e100000000080313c3
```

分析结果：

```txt
analysis_results/20260609-155404_6a17b0e100000000080313c3/analysis_result.md
```

---

## 用户偏好与协作方式

用户希望直接、准确、可执行。

不要：

- 泛泛解释；
- 把未生效的前端改动解释成数据源问题；
- 每次都让用户手动换 URL；
- 重复犯缓存问题；
- 在没有确认本地文件更新前断言“已经好了”。

要：

- 先判断真实问题；
- 改完后说明用户只需要 `git pull`；
- 涉及前端展示时，检查动态版本号和桌面入口；
- 给用户明确的 Windows 命令；
- 用截图反馈快速判断字段是否真的变了。

用户常用本地命令：

```bat
cd /d C:\Users\Yunxi\Documents\自动拆解视频
git pull --ff-only origin main
```

检查文件：

```bat
findstr /n "关键词" 文件路径
```

---

## 后续修改建议

下一步直接做：

```txt
把市场参考样本卡片主标题改成博主名称；
第二行显示样本类型 + 内容形式 + 日期；
笔记标题降级为小标题。
```

优先改：

```txt
workbench/static/sample-card-overrides.js
```

改完后检查：

```bat
findstr /n "dateOnlyOverride note-title readableSampleTitleOverride" workbench\static\sample-card-overrides.js
findstr /n "CACHE_BUST WORKBENCH_URL" 启动小羊森林内容工作台.bat
```
