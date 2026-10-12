(() => {
  "use strict";

  const listEl = document.getElementById("fileList");
  const emptyState = document.getElementById("emptyState");
  const countLabel = document.getElementById("countLabel");
  const currentPathLabel = document.getElementById("currentPathLabel");
  const breadcrumb = document.getElementById("breadcrumb");
  const fileInput = document.getElementById("fileInput");
  const uploadProgress = document.getElementById("uploadProgress");
  const contextMenu = document.getElementById("contextMenu");
  const overlay = document.getElementById("modalOverlay");
  const modalTitle = document.getElementById("modalTitle");
  const modalInput = document.getElementById("modalInput");
  const modalError = document.getElementById("modalError");
  const modalOk = document.getElementById("modalOk");
  const modalCancel = document.getElementById("modalCancel");
  const dropHint = document.getElementById("dropHint");

  let currentPath = "";
  let entries = [];
  let contextTarget = null;
  let modalMode = null;

  const extIcon = {
    "dir": "📁", "pdf": "📕", "doc": "📘", "docx": "📘", "xls": "📗",
    "xlsx": "📗", "ppt": "📙", "pptx": "📙", "zip": "🗜️", "rar": "🗜️",
    "7z": "🗜️", "jpg": "🖼️", "jpeg": "🖼️", "png": "🖼️", "gif": "🖼️",
    "webp": "🖼️", "svg": "🖼️", "mp3": "🎵", "wav": "🎵", "mp4": "🎬",
    "txt": "📄", "md": "📄", "csv": "📄", "json": "📄", "html": "🌐",
    "css": "🎨", "js": "⚙️"
  };

  const fileIcon = (name) => {
    const ext = name.includes(".") ? name.split(".").pop().toLowerCase() : "";
    return extIcon[ext] || "📄";
  };

  const fmtDate = (ts) => {
    if (!ts) return "—";
    const d = new Date(ts * 1000);
    const p = (n) => String(n).padStart(2, "0");
    return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())} ${p(d.getHours())}:${p(d.getMinutes())}`;
  };

  const api = async (url, opts) => {
    const res = await fetch(url, opts);
    let data = null;
    try { data = await res.json(); } catch (e) {}
    if (!res.ok) {
      throw new Error((data && data.error) || `Ошибка (${res.status})`);
    }
    return data;
  };

  async function load(path) {
    currentPath = path || "";
    const data = await api("/api/list?path=" + encodeURIComponent(currentPath));
    entries = data.entries;
    render();
  }

  function render() {
    listEl.innerHTML = "";
    const dirs = entries.filter(e => e.type === "dir");
    const files = entries.filter(e => e.type === "file");

    const row = (e) => {
      const tr = document.createElement("tr");
      tr.dataset.path = e.path;
      tr.dataset.type = e.type;

      const nameTd = document.createElement("td");
      const cell = document.createElement("div");
      cell.className = "name-cell";
      const icon = document.createElement("span");
      icon.className = "icon";
      icon.textContent = e.type === "dir" ? extIcon.dir : fileIcon(e.name);
      const fname = document.createElement("span");
      fname.className = "fname" + (e.type === "dir" ? " clickable" : "");
      fname.textContent = e.name;
      fname.title = e.name;
      if (e.type === "dir") {
        fname.addEventListener("click", (ev) => {
          ev.stopPropagation();
          load(e.path);
        });
      } else {
        fname.addEventListener("click", () => download(e.path, e.name));
      }
      cell.append(icon, fname);
      nameTd.appendChild(cell);

      const sizeTd = document.createElement("td");
      sizeTd.className = "size-cell";
      sizeTd.textContent = e.size_h || "—";

      const dateTd = document.createElement("td");
      dateTd.className = "date-cell";
      dateTd.textContent = fmtDate(e.modified);

      const actionsTd = document.createElement("td");
      actionsTd.className = "actions-col";
      const btn = document.createElement("button");
      btn.className = "row-menu";
      btn.textContent = "⋯";
      btn.addEventListener("click", (ev) => {
        ev.stopPropagation();
        showContextMenu(ev.clientX, ev.clientY, e);
      });
      actionsTd.appendChild(btn);

      tr.append(nameTd, sizeTd, dateTd, actionsTd);
      tr.addEventListener("contextmenu", (ev) => {
        ev.preventDefault();
        showContextMenu(ev.clientX, ev.clientY, e);
      });
      return tr;
    };

    dirs.forEach(e => listEl.appendChild(row(e)));
    files.forEach(e => listEl.appendChild(row(e)));

    emptyState.hidden = entries.length > 0;
    const total = entries.length;
    countLabel.textContent = total ? (dirs.length ? `${dirs.length} пап. · ${files.length} файл.` : `${files.length} файл.`) : "";
    renderBreadcrumb();
  }

  function renderBreadcrumb() {
    breadcrumb.innerHTML = "";
    if (!currentPath) {
      currentPathLabel.textContent = "Корень";
    } else {
      currentPathLabel.textContent = currentPath;
    }
    const parts = currentPath.split("/").filter(Boolean);
    const rootCrumb = document.createElement("span");
    rootCrumb.className = "crumb";
    rootCrumb.textContent = "Корень";
    rootCrumb.addEventListener("click", () => load(""));
    breadcrumb.appendChild(rootCrumb);
    let acc = "";
    parts.forEach((p, i) => {
      const sep = document.createElement("span");
      sep.className = "sep";
      sep.textContent = "/";
      breadcrumb.appendChild(sep);
      acc = acc ? acc + "/" + p : p;
      const crumb = document.createElement("span");
      crumb.className = "crumb";
      crumb.textContent = p;
      if (i < parts.length - 1) {
        crumb.addEventListener("click", () => load(acc));
      } else {
        crumb.classList.add("active");
      }
      breadcrumb.appendChild(crumb);
    });
  }

  function download(path, name) {
    window.location.href = "/api/download?path=" + encodeURIComponent(path);
  }

  function showContextMenu(x, y, entry) {
    contextTarget = entry;
    contextMenu.innerHTML = "";
    contextMenu.hidden = false;

    const items = [];
    if (entry.type === "dir") items.push({ label: "Открыть", action: "open" });
    items.push({ label: "Скачать", action: "download" });
    items.push({ label: "Переименовать", action: "rename" });
    items.push({ label: "Удалить", action: "delete", danger: true });

    items.forEach(it => {
      const b = document.createElement("button");
      b.textContent = it.label;
      if (it.danger) b.className = "danger";
      b.addEventListener("click", () => handleAction(it.action, entry));
      contextMenu.appendChild(b);
    });

    const mw = 180, mh = items.length * 40 + 12;
    contextMenu.style.left = Math.min(x, window.innerWidth - mw) + "px";
    contextMenu.style.top = Math.min(y, window.innerHeight - mh) + "px";
  }

  function hideContextMenu() {
    contextMenu.hidden = true;
    contextMenu.innerHTML = "";
    contextTarget = null;
  }

  async function handleAction(action, entry) {
    hideContextMenu();
    switch (action) {
      case "open":
        load(entry.path);
        break;
      case "download":
        download(entry.path, entry.name);
        break;
      case "rename":
        openModal("rename", entry.name, entry.path);
        break;
      case "delete":
        if (confirm(`Удалить «${entry.name}»?`)) {
          try {
            await api("/api/delete", {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({ path: entry.path })
            });
            await load(currentPath);
          } catch (e) {
            alert(e.message);
          }
        }
        break;
    }
  }

  function openModal(mode, value, path) {
    modalMode = mode;
    modalError.hidden = true;
    contextTarget = { path };
    if (mode === "rename") {
      modalTitle.textContent = "Переименовать";
      modalInput.value = value;
    } else if (mode === "mkdir") {
      modalTitle.textContent = "Новая папка";
      modalInput.value = "";
    }
    overlay.hidden = false;
    modalInput.focus();
  }

  function closeModal() {
    overlay.hidden = true;
    modalMode = null;
    contextTarget = null;
  }

  async function submitModal() {
    const name = modalInput.value.trim();
    if (!name) { modalError.textContent = "Введите имя"; modalError.hidden = false; return; }
    try {
      if (modalMode === "mkdir") {
        await api("/api/mkdir", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ dir: currentPath, name })
        });
      } else if (modalMode === "rename") {
        await api("/api/rename", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ path: contextTarget.path, name })
        });
      }
      closeModal();
      await load(currentPath);
    } catch (e) {
      modalError.textContent = e.message;
      modalError.hidden = false;
    }
  }

  async function uploadFiles(files, dir) {
    if (!files || !files.length) return;
    uploadProgress.hidden = false;
    const parent = dir !== undefined ? dir : currentPath;
    try {
      await api("/api/upload?dir=" + encodeURIComponent(parent) + "&t=" + Date.now(), {
        method: "POST",
        body: files
      });
    } catch (e) {
      alert(e.message);
    } finally {
      uploadProgress.hidden = true;
      await load(parent);
    }
  }

  document.getElementById("uploadBtn").addEventListener("click", () => fileInput.click());
  fileInput.addEventListener("change", (e) => {
    uploadFiles(e.target.files);
    e.target.value = "";
  });
  document.getElementById("newFolderBtn").addEventListener("click", () => openModal("mkdir", "", currentPath));

  modalOk.addEventListener("click", submitModal);
  modalCancel.addEventListener("click", closeModal);
  overlay.addEventListener("click", (e) => { if (e.target === overlay) closeModal(); });
  modalInput.addEventListener("keydown", (e) => { if (e.key === "Enter") submitModal(); });

  document.addEventListener("click", (e) => {
    if (!contextMenu.hidden && !contextMenu.contains(e.target) && !e.target.classList.contains("row-menu")) {
      hideContextMenu();
    }
  });
  window.addEventListener("resize", hideContextMenu);

  let dragDepth = 0;
  document.addEventListener("dragenter", (e) => {
    e.preventDefault();
    dragDepth++;
    dropHint.hidden = false;
  });
  document.addEventListener("dragover", (e) => e.preventDefault());
  document.addEventListener("dragleave", (e) => {
    dragDepth--;
    if (dragDepth <= 0) { dragDepth = 0; dropHint.hidden = true; }
  });
  document.addEventListener("drop", (e) => {
    e.preventDefault();
    dragDepth = 0;
    dropHint.hidden = true;
    if (e.dataTransfer && e.dataTransfer.files && e.dataTransfer.files.length) {
      uploadFiles(e.dataTransfer.files);
    }
  });

  load("");
})();