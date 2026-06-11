const state = {
  samples: [],
  products: [],
  voices: [],
  analysisResults: {},
  typeMeta: {},
  productTags: {},
  taskTimer: null,
};

const $ = (selector) => document.querySelector(selector);
const $$ = (selector) => Array.from(document.querySelectorAll(selector));

function esc(value) {
  return String(value ?? "").replace(/[&<>"']/g, (ch) => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#39;",
  }[ch]));
}

async function api(path, options = {}) {
  const res = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  return res.json();
}

function badge(text, kind = "") {
  return `<span class="badge ${kind}">${esc(text || "待判断")}</span>`;
}

function md(text) {
  return esc(text || "").replace(/\n/g, "<br>");
}

function firstMatch(text, patterns) {
  for (const pattern of patterns) {
    const match = String(text || "").match(pattern);
    if (match && match[1]) return match[1].trim();
  }
  return "";
}

function parseAnalysisMeta(text) {
  const source = String(text || "");
  const dataLine = firstMatch(source, [/数据[:：]\s*([^\n]+)/]);
  return {
    title: firstMatch(source, [/笔记标题[:：]\s*([^\n]+)/, /标题[:：]\s*([^\n]+)/]),
    author: firstMatch(source, [/作者[:：]\s*([^\n]+)/, /博主[:：]\s*([^\n]+)/]),
    likes: firstMatch(dataLine, [/点赞\s*([\d,]+)/]) || firstMatch(source, [/点赞[:：]?\s*([\d,]+)/]),
    collects: firstMatch(dataLine, [/收藏\s*([\d,]+)/]) || firstMatch(source, [/收藏[:：]?\s*([\d,]+)/]),
    comments: firstMatch(dataLine, [/评论\s*([\d,]+)/]) || firstMatch(source, [/评论[:：]?\s*([\d,]+)/]),
  };
}

async function load() {
  const data = await api("/api/bootstrap");
  state.samples = data.samples || [];
  state.products = data.products || [];
  state.voices = data.voices || [];
  state.analysisResults = data.analysisResults || {};
  state.typeMeta = data.typeMeta || {};
  state.productTags = data.productTags || {};
  renderAll();
}

function switchView(view) {
  $$(".nav-button").forEach((btn) => btn.classList.toggle("active", btn.dataset.view === view));
  $$(".view").forEach((section) => section.classList.toggle("active", section.id === `view-${view}`));
  const active = document.querySelector(`.nav-button[data-view="${view}"] span`);
  $("#viewTitle").textContent = active ? active.textContent : "工作台";
  if (window.lucide) lucide.createIcons();
}

function renderAll() {
  renderProductOptions();
  renderSampleTables();
  renderMissing();
  renderResults();
  renderProducts();
  renderVoices();
  toggleTypeFields();
  if (window.lucide) lucide.createIcons();
}

function renderProductOptions() {
  const el = $("#productOptions");
  if (!el) return;
  el.innerHTML = state.products.map((item) => `<option value="${esc(item.name)}"></option>`).join("");
}

function matches(item, query) {
  return !query || JSON.stringify(item).includes(query);
}

function renderSampleTables() {
  renderTable("市场参考", "#marketTable", "#marketSearch");
  renderTable("达人合作", "#kolTable", "#kolSearch");
  renderTable("官号发布", "#officialTable", "#officialSearch");
}

function renderTable(type, target, searchTarget) {
  const query = ($(searchTarget)?.value || "").trim();
  const rows = state.samples.filter((item) => item.sampleType === type && matches(item, query));
  $(target).innerHTML = rows.map(sampleCard).join("") || `<div class="empty">还没有${esc(type)}样本。</div>`;
}

function cardMetrics(item, result, analysisMeta) {
  const metrics = item.metrics || {};
  if (item.sampleType === "市场参考") {
    return [
      { label: "点赞", value: metrics.likes || item.likes || analysisMeta.likes || "-" },
      { label: "收藏", value: metrics.collects || item.collects || analysisMeta.collects || "-" },
      { label: "评论", value: metrics.comments || item.comments || analysisMeta.comments || "-" },
    ];
  }
  return [
    { label: "曝光/播放", value: metrics.impressions || item.impressions || "-" },
    { label: "商品点击", value: metrics.itemClicks || item.itemClicks || "-" },
    { label: "订单/GMV", value: metrics.orders || item.orders || "-" },
  ];
}

function sampleCard(item) {
  const gpt = item.gpt || {};
  const result = gpt.result || null;
  const analysisMeta = parseAnalysisMeta(result?.analysisText || "");
  const missing = item.missing || [];
  const title = item.title || analysisMeta.title || item.url || item.id;
  const author = item.creator || analysisMeta.author || "账号未知";
  const metrics = cardMetrics(item, result, analysisMeta);
  const kind = missing.length ? "risk" : result ? "" : "warn";
  return `
    <article class="sample-card">
      <div class="sample-main">
        <p class="eyebrow">${esc(item.sampleType)} · ${esc(item.contentForm || "未识别")} · ${esc(item.processMode || "未设置")}</p>
        <h3>${esc(title)}</h3>
        <p class="muted">${esc(author)} ${item.product ? `｜${esc(item.product)}` : ""} ${item.publishDate ? `｜${esc(item.publishDate)}` : ""}</p>
        ${item.url && title !== item.url ? `<p class="link-line">${esc(item.url)}</p>` : ""}
        ${item.note ? `<p>${esc(item.note)}</p>` : ""}
        <div class="row wrap">
          ${badge(item.status || gpt.status || "只登记", kind)}
          ${item.recordReason ? badge(item.recordReason, "info") : ""}
          ${item.tracking ? badge(item.tracking, "info") : ""}
          ${item.cost ? badge(`花费 ${item.cost}`, "warn") : ""}
          ${result ? badge("GPT 已分析") : ""}
          ${missing.length ? badge(`待补 ${missing.length} 项`, "risk") : ""}
        </div>
      </div>
      <div class="sample-side">
        <div class="mini-metrics">
          ${metrics.map((m) => `<div><strong>${esc(m.value)}</strong><span>${esc(m.label)}</span></div>`).join("")}
        </div>
        <div class="actions">
          ${item.url ? `<a href="${esc(item.url)}" target="_blank">打开链接</a>` : ""}
          ${gpt.inbox?.relativePath ? `<span>${esc(gpt.inbox.relativePath)}</span>` : ""}
          ${result?.relativePath ? `<button data-result="${esc(result.id)}" class="text-button">查看分析</button>` : ""}
        </div>
      </div>
    </article>
  `;
}

function renderMissing() {
  const rows = state.samples.filter((item) => (item.missing || []).length);
  $("#missingList").innerHTML = rows.map((item) => `
    <article class="missing-card">
      <div>
        <p class="eyebrow">${esc(item.sampleType)} · ${esc(item.title || item.url || item.id)}</p>
        <h3>GPT 需要你补充</h3>
        <ul>${(item.missing || []).map((x) => `<li>${esc(x)}</li>`).join("")}</ul>
        ${item.note ? `<p class="muted">备注：${esc(item.note)}</p>` : ""}
      </div>
      <div class="row wrap">
        ${item.url ? `<a class="secondary" href="${esc(item.url)}" target="_blank">打开笔记</a>` : ""}
        ${badge(item.status, "risk")}
      </div>
    </article>
  `).join("") || `<div class="empty">暂无待补资料。资料越完整，GPT 判断越少瞎猜。</div>`;
}

function resultSummary(result) {
  const s = result.status || {};
  return [
    s.decision && `判断：${s.decision}`,
    s.replicate_priority && `优先级：${s.replicate_priority}`,
    s.recommended_direction && `方向：${s.recommended_direction}`,
    s.recommended_title && `标题：${s.recommended_title}`,
  ].filter(Boolean);
}

function resultCard(result, item = null) {
  const summary = resultSummary(result);
  const analysisMeta = parseAnalysisMeta(result?.analysisText || "");
  return `
    <article class="result-card" id="result-${esc(result.id)}">
      <div class="result-head">
        <div>
          <p class="eyebrow">${esc(item?.sampleType || "GPT 分析结果")} · ${esc(item?.contentForm || "")}</p>
          <h3>${esc(item?.title || item?.url || analysisMeta.title || result.id)}</h3>
          ${analysisMeta.author ? `<p class="muted">${esc(analysisMeta.author)}</p>` : ""}
        </div>
        ${badge(item?.gpt?.status || result.status?.status || "已完成分析")}
      </div>
      ${summary.length ? `<div class="summary-grid">${summary.map((x) => `<div>${esc(x)}</div>`).join("")}</div>` : ""}
      <details open>
        <summary>查看 GPT 分析全文</summary>
        <div class="markdown-box">${md(result.analysisText || "暂无分析正文。")}</div>
      </details>
      <p class="muted">结果路径：${esc(result.relativePath)}</p>
      ${item && !result.finalized ? `<button class="primary finalize-button" data-finalize-sample="${esc(item.id)}" data-finalize-package="${esc(result.id)}">确认最终版并清理 GitHub 中转文件</button>` : ""}
      ${result.finalized ? `<p class="muted">已确认最终版，当前结果保存在本地。</p>` : ""}
    </article>
  `;
}

function renderResults() {
  const linked = state.samples.filter((item) => item.gpt?.result);
  const linkedIds = new Set(linked.map((item) => item.gpt.result.id));
  const orphanResults = Object.values(state.analysisResults || {}).filter((result) => !linkedIds.has(result.id));
  const html = [
    ...linked.map((item) => resultCard(item.gpt.result, item)),
    ...orphanResults.map((result) => resultCard(result, null)),
  ].join("");
  $("#resultList").innerHTML = html || `<div class="empty">还没有 GPT 分析结果。完整分析后，结果会出现在这里。</div>`;
}

function renderProducts() {
  $("#productCount").textContent = `${state.products.length} 个`;
  $("#productList").innerHTML = state.products.map((item) => `
    <article class="card">
      <h3>${esc(item.name)}</h3>
      <p>${esc(item.category || "未分类")} ${item.age ? `｜${esc(item.age)}` : ""} ${item.taste ? `｜${esc(item.taste)}` : ""}</p>
      <div class="row wrap">
        ${(item.forms || []).map((x) => badge(x, "info")).join("")}
        ${(item.needs || []).map((x) => badge(x)).join("")}
        ${(item.timing || []).map((x) => badge(x, "warn")).join("")}
        ${(item.contentTags || []).map((x) => badge(x, "info")).join("")}
      </div>
      ${item.scenes ? `<p><strong>场景：</strong>${esc(item.scenes)}</p>` : ""}
      ${item.raw ? `<details><summary>查看原始资料</summary><p class="markdown-box">${md(item.raw)}</p></details>` : ""}
    </article>
  `).join("") || `<div class="empty">还没有产品卡。后续分析会用产品卡判断承接方向和禁区。</div>`;
}

function renderVoices() {
  $("#voiceCount").textContent = `${state.voices.length} 条`;
  $("#voiceList").innerHTML = state.voices.map((item) => `
    <article class="card">
      <h3>${esc(item.text)}</h3>
      <p class="muted">${esc(item.source || "未标注来源")} ${item.product ? `｜${esc(item.product)}` : ""}</p>
    </article>
  `).join("") || `<div class="empty">还没有用户原声。</div>`;
}

function collectPayload() {
  const sampleType = $("#sampleType").value;
  const product = sampleType === "达人合作" ? $("#kolProduct").value : sampleType === "官号发布" ? $("#officialProduct").value : $("#marketProduct").value;
  return {
    url: $("#urlInput").value.trim(),
    title: $("#titleInput").value.trim(),
    sampleType,
    contentForm: $("#contentForm").value,
    processMode: $("#processMode").value,
    note: $("#noteInput").value.trim(),
    recordReason: $("#recordReason").value,
    product,
    creator: $("#creatorInput").value.trim(),
    cost: $("#costInput").value.trim(),
    collabType: $("#collabType").value,
    tracking: $("#tracking").value,
    initialJudgement: $("#initialJudgement").value,
    hasCart: $("#hasCart").value,
    objective: $("#objective").value,
    publishDate: $("#publishDate").value.trim(),
  };
}

function resetForm() {
  ["#urlInput", "#titleInput", "#noteInput", "#marketProduct", "#creatorInput", "#kolProduct", "#costInput", "#officialProduct", "#publishDate"].forEach((s) => { const el = $(s); if (el) el.value = ""; });
  $("#processMode").value = "只登记";
  $("#contentForm").value = "图文";
  $("#recordReason").value = "";
  $("#collabType").value = "";
  $("#tracking").value = "";
  $("#initialJudgement").value = "不确定";
  $("#hasCart").value = "";
  $("#objective").value = "";
}

function pollTask(taskId) {
  if (!taskId) return;
  clearInterval(state.taskTimer);
  state.taskTimer = setInterval(async () => {
    const task = await api(`/api/task?id=${encodeURIComponent(taskId)}`);
    $("#taskLog").textContent = `${task.status || "处理中"}\n${task.message || task.error || ""}\n${task.packageId ? `分析包：${task.packageId}` : ""}`;
    if (["失败", "待 GPT 分析", "分析包生成成功，GitHub 上传失败"].includes(task.status) || task.packageId) {
      clearInterval(state.taskTimer);
      await load();
    }
  }, 2500);
}

function toggleTypeFields() {
  const type = $("#sampleType")?.value || "市场参考";
  $$(".conditional").forEach((el) => el.classList.toggle("hidden", el.dataset.for !== type));
}

function readAsText(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result || ""));
    reader.onerror = () => reject(reader.error);
    reader.readAsText(file, "utf-8");
  });
}

function readAsArrayBuffer(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(reader.result);
    reader.onerror = () => reject(reader.error);
    reader.readAsArrayBuffer(file);
  });
}

function cleanXmlText(xml) {
  return String(xml || "")
    .replace(/<[^>]+>/g, "\n")
    .replace(/&amp;/g, "&")
    .replace(/&lt;/g, "<")
    .replace(/&gt;/g, ">")
    .replace(/&quot;/g, '"')
    .replace(/&apos;/g, "'")
    .replace(/\n{3,}/g, "\n\n")
    .trim();
}

async function extractOfficeText(file, ext) {
  if (!window.JSZip) throw new Error("JSZip 未加载，无法解析 Office 文件");
  const zip = await JSZip.loadAsync(await readAsArrayBuffer(file));
  let paths = [];
  if (ext === "docx") paths = Object.keys(zip.files).filter((p) => p === "word/document.xml" || p.startsWith("word/header") || p.startsWith("word/footer"));
  if (ext === "pptx") paths = Object.keys(zip.files).filter((p) => p.startsWith("ppt/slides/slide") && p.endsWith(".xml"));
  if (ext === "xlsx") paths = Object.keys(zip.files).filter((p) => ["xl/sharedStrings.xml", "xl/workbook.xml"].includes(p) || (p.startsWith("xl/worksheets/sheet") && p.endsWith(".xml")));
  const parts = [];
  for (const path of paths) {
    const xml = await zip.files[path].async("text");
    const text = cleanXmlText(xml);
    if (text) parts.push(`【${path}】\n${text}`);
  }
  return parts.join("\n\n") || "未能从 Office 文件中提取到文字。";
}

async function extractPdfText(file) {
  if (!window.pdfjsLib) throw new Error("PDF.js 未加载，无法解析 PDF");
  pdfjsLib.GlobalWorkerOptions.workerSrc = "https://cdnjs.cloudflare.com/ajax/libs/pdf.js/3.11.174/pdf.worker.min.js";
  const pdf = await pdfjsLib.getDocument({ data: await readAsArrayBuffer(file) }).promise;
  const pages = [];
  for (let pageNo = 1; pageNo <= pdf.numPages; pageNo += 1) {
    const page = await pdf.getPage(pageNo);
    const content = await page.getTextContent();
    const text = content.items.map((item) => item.str).join(" ").replace(/\s+/g, " ").trim();
    if (text) pages.push(`【PDF 第 ${pageNo} 页】\n${text}`);
  }
  return pages.join("\n\n") || "未能从 PDF 中提取到可复制文字，可能是扫描图片版。";
}

async function extractFileText(file) {
  const ext = (file.name.split(".").pop() || "").toLowerCase();
  if (["txt", "md", "csv", "json", "html", "htm"].includes(ext)) return await readAsText(file);
  if (["docx", "pptx", "xlsx"].includes(ext)) return await extractOfficeText(file, ext);
  if (ext === "pdf") return await extractPdfText(file);
  return `暂不支持自动提取该文件类型：${file.name}`;
}

async function handleProductFiles(event) {
  const files = Array.from(event.target.files || []);
  if (!files.length) return;
  const log = $("#productFileLog");
  const raw = $("#productRaw");
  const outputs = [];
  for (const file of files) {
    try {
      log.textContent = `正在读取：${file.name}`;
      const text = await extractFileText(file);
      outputs.push(`\n\n===== 上传文件：${file.name} =====\n${text}`);
    } catch (err) {
      outputs.push(`\n\n===== 上传文件：${file.name} =====\n提取失败：${err.message || err}`);
    }
  }
  raw.value = `${raw.value || ""}${outputs.join("\n")}`.trim();
  log.textContent = `已处理 ${files.length} 个文件，文字已追加到资料框。请检查后点“生成产品卡”。`;
}

function bindEvents() {
  $$(".nav-button").forEach((btn) => btn.addEventListener("click", () => switchView(btn.dataset.view)));
  ["#marketSearch", "#kolSearch", "#officialSearch"].forEach((s) => $(s)?.addEventListener("input", renderSampleTables));
  $("#sampleType").addEventListener("change", toggleTypeFields);
  $("#productFiles")?.addEventListener("change", handleProductFiles);
  $("#submitSample").addEventListener("click", async () => {
    const payload = collectPayload();
    if (!payload.url && !payload.title) {
      $("#taskLog").textContent = "至少填写链接或标题。";
      return;
    }
    $("#taskLog").textContent = "正在保存样本...";
    const res = await api("/api/sample", { method: "POST", body: JSON.stringify(payload) });
    if (res.taskId) {
      $("#taskLog").textContent = `已保存，正在后台抓取并生成分析包。任务：${res.taskId}`;
      pollTask(res.taskId);
    } else {
      $("#taskLog").textContent = "已保存。";
      await load();
    }
    resetForm();
  });
  $("#addProduct").addEventListener("click", async () => {
    const payload = {
      name: $("#productName").value.trim(),
      category: $("#productCategory").value.trim(),
      age: $("#productAge").value.trim(),
      taste: $("#productTaste").value.trim(),
      scenes: $("#productScenes").value.trim(),
      raw: $("#productRaw").value.trim(),
    };
    if (!payload.name && !payload.raw) return;
    await api("/api/product", { method: "POST", body: JSON.stringify(payload) });
    ["#productName", "#productCategory", "#productAge", "#productTaste", "#productScenes", "#productRaw"].forEach((s) => $(s).value = "");
    const files = $("#productFiles");
    if (files) files.value = "";
    const log = $("#productFileLog");
    if (log) log.textContent = "还未上传文件";
    await load();
  });
  $("#addVoice").addEventListener("click", async () => {
    const payload = { text: $("#voiceText").value.trim(), source: $("#voiceSource").value.trim(), product: $("#voiceProduct").value.trim() };
    if (!payload.text) return;
    await api("/api/voice", { method: "POST", body: JSON.stringify(payload) });
    ["#voiceText", "#voiceSource", "#voiceProduct"].forEach((s) => $(s).value = "");
    await load();
  });
  document.addEventListener("click", (event) => {
    const finalizeBtn = event.target.closest("[data-finalize-sample]");
    if (finalizeBtn) {
      const ok = window.confirm("确认这版就是最终版？确认后会把结果保存在本地，并删除 GitHub 上这个链接的中转分析包。");
      if (!ok) return;
      api("/api/analysis/finalize", {
        method: "POST",
        body: JSON.stringify({
          sampleId: finalizeBtn.dataset.finalizeSample,
          packageId: finalizeBtn.dataset.finalizePackage,
        }),
      }).then(async (result) => {
        if (!result.ok) {
          alert(result.error || "确认失败");
          return;
        }
        alert(result.message || "已确认最终版");
        await load();
      }).catch((error) => alert(error.message || "确认失败"));
      return;
    }
    const btn = event.target.closest("[data-result]");
    if (!btn) return;
    switchView("results");
    setTimeout(() => document.getElementById(`result-${btn.dataset.result}`)?.scrollIntoView({ behavior: "smooth", block: "start" }), 80);
  });
}

bindEvents();
load();
