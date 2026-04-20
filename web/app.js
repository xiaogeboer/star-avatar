const statusEl = document.getElementById("status");
const resultsEl = document.getElementById("results");
const submitBtn = document.getElementById("submit");
const pickDirBtn = document.getElementById("pick-dir");

const playersInput = document.getElementById("players");
const sizeInput = document.getElementById("size");
const sizeSelect = document.getElementById("size-select");
const sizeTrigger = document.getElementById("size-trigger");
const sizeLabel = document.getElementById("size-label");
const sizeMenu = document.getElementById("size-menu");
const sizeOptions = Array.from(document.querySelectorAll(".select-option"));
const delayInput = document.getElementById("delay");
const outputDirInput = document.getElementById("output-dir");
const outputDirMeta = document.getElementById("output-dir-meta");

const defaultPlayers = [
  "Novak Djokovic",
  "Rafael Nadal",
  "Roger Federer",
  "Carlos Alcaraz",
  "Jannik Sinner",
];

playersInput.value = defaultPlayers.join("\n");

function setStatus(text, isError = false) {
  statusEl.textContent = text;
  statusEl.className = isError ? "status error" : "status";
}

function setSizeValue(value) {
  sizeInput.value = value;
  sizeLabel.textContent = value;
  sizeOptions.forEach((btn) => {
    btn.classList.toggle("is-active", btn.dataset.value === value);
  });
}

function openSizeMenu() {
  sizeMenu.hidden = false;
  sizeSelect.classList.add("is-open");
}

function closeSizeMenu() {
  sizeMenu.hidden = true;
  sizeSelect.classList.remove("is-open");
}

function escapeHtml(text) {
  return String(text)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;");
}

async function loadConfig() {
  try {
    const resp = await fetch("/api/config");
    const data = await resp.json();
    if (!resp.ok) return;
    outputDirInput.value = data.default_output_dir || "";
    outputDirMeta.textContent = `默认目录: ${data.default_output_dir || "-"}`;
  } catch (_) {
    outputDirMeta.textContent = "默认目录加载失败";
  }
}

async function pickDirectory() {
  pickDirBtn.disabled = true;
  try {
    const resp = await fetch("/api/pick-directory", { method: "POST" });
    const data = await resp.json();
    if (!resp.ok) {
      throw new Error(data.error || "打开目录选择器失败");
    }
    if (data.path) {
      outputDirInput.value = data.path;
      outputDirMeta.textContent = `已选择: ${data.path}`;
    } else {
      outputDirMeta.textContent = "已取消目录选择";
    }
  } catch (err) {
    setStatus(`目录选择失败: ${err.message}`, true);
  } finally {
    pickDirBtn.disabled = false;
  }
}

function renderResults(results) {
  if (!results || results.length === 0) {
    resultsEl.innerHTML = "<p>暂无结果</p>";
    return;
  }

  const rows = results
    .map((item) => {
      const requested = escapeHtml(item.requested_name || "");
      const matched = escapeHtml(item.matched_name || "-");
      const sport = escapeHtml(item.sport || "-");
      const state = escapeHtml(item.status || "");
      const reason = escapeHtml(item.reason || "");
      const saved = escapeHtml(item.saved_to || "-");
      const idPlayer = escapeHtml(String(item.idPlayer || "-"));
      const imagePreview = item.image_preview_url
        ? `<img src="${item.image_preview_url}" alt="${matched}" class="avatar" />`
        : "-";

      return `
        <tr>
          <td>${requested}</td>
          <td>${matched}</td>
          <td>${sport}</td>
          <td>${idPlayer}</td>
          <td>${state}</td>
          <td>${reason || "-"}</td>
          <td class="path-cell" title="${saved}">${saved}</td>
          <td>${imagePreview}</td>
        </tr>
      `;
    })
    .join("");

  resultsEl.innerHTML = `
    <table>
      <thead>
        <tr>
          <th>输入名</th>
          <th>匹配名</th>
          <th>运动</th>
          <th>idPlayer</th>
          <th>状态</th>
          <th>说明</th>
          <th>保存路径</th>
          <th>头像</th>
        </tr>
      </thead>
      <tbody>${rows}</tbody>
    </table>
  `;
}

async function submit() {
  submitBtn.disabled = true;
  setStatus("正在下载，请稍候...");
  resultsEl.innerHTML = "";

  try {
    const resp = await fetch("/api/download", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        players: playersInput.value,
        size: sizeInput.value,
        delay: Number(delayInput.value),
        output_dir: outputDirInput.value.trim(),
      }),
    });

    const data = await resp.json();
    if (!resp.ok) {
      throw new Error(data.error || "请求失败");
    }

    setStatus(
      `完成：${data.downloaded_count}/${data.requested_count} 下载成功，目录：${data.output_dir}`
    );
    renderResults(data.results);
  } catch (err) {
    setStatus(`网络错误：${err.message}`, true);
  } finally {
    submitBtn.disabled = false;
  }
}

submitBtn.addEventListener("click", submit);
pickDirBtn.addEventListener("click", pickDirectory);

sizeTrigger.addEventListener("click", () => {
  if (sizeMenu.hidden) {
    openSizeMenu();
  } else {
    closeSizeMenu();
  }
});

sizeOptions.forEach((btn) => {
  btn.addEventListener("click", () => {
    setSizeValue(btn.dataset.value);
    closeSizeMenu();
  });
});

document.addEventListener("click", (event) => {
  if (!sizeSelect.contains(event.target)) {
    closeSizeMenu();
  }
});

document.addEventListener("keydown", (event) => {
  if (event.key === "Escape") {
    closeSizeMenu();
  }
});

loadConfig();
setSizeValue(sizeInput.value || "small");
