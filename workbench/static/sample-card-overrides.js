function isUrlLikeOverride(value) {
  const text = String(value || "").trim();
  return /^https?:\/\//i.test(text) || text.includes("xiaohongshu.com/explore/");
}

function noteIdFromUrlOverride(url) {
  const match = String(url || "").match(/explore\/([^/?#]+)/);
  return match ? match[1] : "";
}

function dateOnlyOverride(value) {
  const text = String(value || "").trim();
  const match = text.match(/\d{4}-\d{2}-\d{2}/);
  return match ? match[0] : "";
}

function readableSampleTitleOverride(item, analysisMeta = {}) {
  const manualTitle = String(item.title || "").trim();
  if (manualTitle && !isUrlLikeOverride(manualTitle)) return manualTitle;

  const analyzedTitle = String(analysisMeta.title || "").trim();
  if (analyzedTitle && !isUrlLikeOverride(analyzedTitle)) return analyzedTitle;

  const noteId = noteIdFromUrlOverride(item.url || manualTitle);
  return noteId ? `小红书笔记 ${noteId}` : (item.id || "未命名样本");
}

function readableAuthorOverride(item, analysisMeta = {}) {
  const manualAuthor = String(item.creator || "").trim();
  if (manualAuthor) return manualAuthor;

  const analyzedAuthor = String(analysisMeta.author || "").trim();
  if (analyzedAuthor) return analyzedAuthor;

  return "账号未知";
}

function readableContentFormOverride(item, result = null) {
  const raw = String(item.contentForm || "").trim();
  if (["图文", "视频"].includes(raw)) return raw;

  const analysisText = String(result?.analysisText || "");
  if (/视频里|视频中|口播|镜头|画面|字幕|剪辑/.test(analysisText)) return "视频";
  if (/图文|封面|内页|第\s*1\s*页|第一页|多页|图片/.test(analysisText)) return "图文";

  return "";
}

function sampleHeadlinePartsOverride(item, result = null, analysisMeta = {}) {
  const author = readableAuthorOverride(item, analysisMeta);
  const contentForm = readableContentFormOverride(item, result);
  const dateText = dateOnlyOverride(item.publishDate || item.createdAt || result?.status?.created_at || "");
  return [author, contentForm, dateText].filter(Boolean);
}

function sampleCard(item) {
  const gpt = item.gpt || {};
  const result = gpt.result || null;
  const analysisMeta = parseAnalysisMeta(result?.analysisText || "");
  const missing = item.missing || [];
  const title = readableSampleTitleOverride(item, analysisMeta);
  const metrics = cardMetrics(item, result, analysisMeta);
  const kind = missing.length ? "risk" : result ? "" : "warn";
  const reasonText = item.note || item.recordReason || "";
  const headlineParts = sampleHeadlinePartsOverride(item, result, analysisMeta);

  return `
    <article class="sample-card">
      <div class="sample-main">
        <h3>${headlineParts.map((x) => esc(x)).join(" ｜ ")}</h3>
        <p class="muted note-title">${esc(title)}</p>
        ${reasonText ? `<p>${esc(reasonText)}</p>` : ""}
        <div class="row wrap">
          ${badge(item.sampleType || "样本")}
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
          ${item.url ? `<a href="${esc(item.url)}" target="_blank">打开原笔记</a>` : ""}
          ${gpt.inbox?.relativePath ? `<span>${esc(gpt.inbox.relativePath)}</span>` : ""}
          ${result?.relativePath ? `<button data-result="${esc(result.id)}" class="text-button">查看分析</button>` : ""}
        </div>
      </div>
    </article>
  `;
}

function renderMissing() {
  const rows = state.samples.filter((item) => (item.missing || []).length);
  $("#missingList").innerHTML = rows.map((item) => {
    const gpt = item.gpt || {};
    const result = gpt.result || null;
    const analysisMeta = parseAnalysisMeta(result?.analysisText || "");
    const title = readableSampleTitleOverride(item, analysisMeta);
    const headlineParts = sampleHeadlinePartsOverride(item, result, analysisMeta);
    const kind = (item.missing || []).length ? "risk" : "";

    return `
      <article class="missing-card">
        <div>
          <h3>${headlineParts.map((x) => esc(x)).join(" ｜ ")}</h3>
          <p class="muted note-title">${esc(title)}</p>
          <p class="eyebrow">GPT 需要你补充</p>
          <ul>${(item.missing || []).map((x) => `<li>${esc(x)}</li>`).join("")}</ul>
          ${item.note ? `<p class="muted">备注：${esc(item.note)}</p>` : ""}
          <div class="row wrap">
            ${badge(item.sampleType || "样本")}
            ${item.recordReason ? badge(item.recordReason, "info") : ""}
          </div>
        </div>
        <div class="row wrap">
          ${item.url ? `<a class="secondary" href="${esc(item.url)}" target="_blank">打开笔记</a>` : ""}
          ${badge(item.status || gpt.status || "待补资料", kind)}
        </div>
      </article>
    `;
  }).join("") || `<div class="empty">暂无待补资料。资料越完整，GPT 判断越少瞎猜。</div>`;
}

function resultCard(result, item = null) {
  const summary = resultSummary(result);
  const analysisMeta = parseAnalysisMeta(result?.analysisText || "");
  const title = item ? readableSampleTitleOverride(item, analysisMeta) : (analysisMeta.title || result.id);
  return `
    <article class="result-card" id="result-${esc(result.id)}">
      <div class="result-head">
        <div>
          <p class="eyebrow">${esc(item?.sampleType || "GPT 分析结果")} · ${esc(item?.contentForm || "")}</p>
          <h3>${esc(title)}</h3>
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
    </article>
  `;
}

load();