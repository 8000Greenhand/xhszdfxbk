function pendingAnalysisCard(item) {
  const gpt = item.gpt || {};
  const inbox = gpt.inbox || {};
  const title = typeof readableSampleTitleOverride === "function" ? readableSampleTitleOverride(item, {}) : (item.title || item.url || item.id);
  const headlineParts = typeof sampleHeadlinePartsOverride === "function" ? sampleHeadlinePartsOverride(item, null, {}) : [item.creator || "账号未知", item.contentForm || ""];
  const created = item.createdAt || inbox.createdAt || "";
  return `
    <article class="result-card pending-result-card" id="pending-${esc(item.id || inbox.id || inbox.folder)}">
      <div class="result-head">
        <div>
          <p class="eyebrow">${esc(item.sampleType || "样本")} · ${esc(item.processMode || "待分析")}</p>
          <h3>${esc(title)}</h3>
          <p class="muted">${esc(headlineParts.filter(Boolean).join(" ｜ "))}</p>
        </div>
        ${badge("待 GPT 分析", "warn")}
      </div>
      <div class="summary-grid">
        <div>状态：分析包已生成，还不是最终 GPT 分析结果</div>
        <div>处理方式：${esc(item.processMode || "未标注")}</div>
        <div>创建时间：${esc(created || "未记录")}</div>
        <div>分析包：${esc(inbox.relativePath || item.analysisPackageId || "未找到路径")}</div>
      </div>
      <details>
        <summary>这是什么意思？</summary>
        <div class="markdown-box">
          这张卡表示系统已经把笔记整理成 analysis_input.md，并且已经按“样本初筛 → 样本池分类 → 产品承接 → 创作出口”的新逻辑生成了给 GPT 的输入包。<br><br>
          但它还没有对应的 analysis_result.md，所以还不能算“已完成分析”。等 GPT 分析结果写回 analysis_results 后，这张卡会变成“已完成分析”。
        </div>
      </details>
      ${item.url ? `<p class="muted">原笔记：${esc(item.url)}</p>` : ""}
    </article>
  `;
}

function completedResultItemsOverride() {
  const linked = state.samples.filter((item) => item.gpt?.result);
  const linkedIds = new Set(linked.map((item) => item.gpt.result.id));
  const orphanResults = Object.values(state.analysisResults || {}).filter((result) => !linkedIds.has(result.id));
  return { linked, orphanResults };
}

function normalizeResultTextOverride(value) {
  return String(value || "").replace(/\s+/g, "").toLowerCase();
}

function isUnknownCreatorOverride(item) {
  const creator = normalizeResultTextOverride(item.creator || item.author || item.nickname || "");
  return !creator || creator.includes("账号未知") || creator.includes("未提取") || creator === "unknown";
}

function isStalePendingPackageOverride(item, completedCount) {
  if (!item?.gpt?.inbox || item?.gpt?.result || !completedCount) return false;
  const title = typeof readableSampleTitleOverride === "function" ? readableSampleTitleOverride(item, {}) : (item.title || "");
  const badTitle = typeof isBadTitleFallbackOverride === "function"
    ? isBadTitleFallbackOverride(title)
    : !String(title || "").trim() || String(title).includes("未提取");
  const unknownCreator = isUnknownCreatorOverride(item);
  const url = String(item.url || "");
  const packageId = String(item.analysisPackageId || item.gpt?.inbox?.folder || item.gpt?.inbox?.id || "");
  const shortLinkLike = /xhslink\.com/i.test(url);
  const oldTempPackageLike = /\d{8}-\d{6}_[a-f0-9]{6,10}$/i.test(packageId);
  return badTitle && unknownCreator && (shortLinkLike || oldTempPackageLike);
}

function splitPendingItemsOverride(pending, completedCount) {
  const active = [];
  const archived = [];
  for (const item of pending) {
    if (isStalePendingPackageOverride(item, completedCount)) archived.push(item);
    else active.push(item);
  }
  return { active, archived };
}

function archivedPendingSummaryOverride(items) {
  if (!items.length) return "";
  const rows = items.map((item) => {
    const inbox = item.gpt?.inbox || {};
    const path = inbox.relativePath || item.analysisPackageId || "未找到路径";
    const url = item.url || "";
    return `<li><code>${esc(path)}</code>${url ? `｜${esc(url)}` : ""}</li>`;
  }).join("");
  return `
    <details class="empty" style="margin-bottom:12px; text-align:left;">
      <summary>已隐藏历史待分析包：${items.length} 条</summary>
      <div class="markdown-box" style="margin-top:10px;">
        这些通常是旧短链/旧失败包，已经有后续完成版结果，不再默认展示，避免干扰判断。原始文件没有删除，需要排查时仍可在 GitHub 中查看。
        <ul>${rows}</ul>
      </div>
    </details>
  `;
}

function renderResults() {
  const pendingAll = state.samples.filter((item) => item.gpt?.inbox && !item.gpt?.result);
  const { linked, orphanResults } = completedResultItemsOverride();
  const completedCount = linked.length + orphanResults.length;
  const { active: pending, archived } = splitPendingItemsOverride(pendingAll, completedCount);
  const html = [
    archivedPendingSummaryOverride(archived),
    pending.length ? `<div class="empty" style="margin-bottom:12px; text-align:left;">待 GPT 分析：${pending.length} 条。它们已经生成分析包，但还没有写回最终分析结果。</div>` : "",
    ...pending.map(pendingAnalysisCard),
    completedCount ? `<div class="empty" style="margin:16px 0 12px; text-align:left;">已完成分析：${completedCount} 条</div>` : "",
    ...linked.map((item) => resultCard(item.gpt.result, item)),
    ...orphanResults.map((result) => resultCard(result, null)),
  ].join("");
  $("#resultList").innerHTML = html || `<div class="empty">还没有 GPT 分析包或分析结果。保存一条需要分析的样本后，会先出现在“待 GPT 分析”。</div>`;
}

load();