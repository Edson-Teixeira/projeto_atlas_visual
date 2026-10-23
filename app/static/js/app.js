// ==============================================================================
// Atlas - Interações de UI e Upload
// ==============================================================================

document.addEventListener("DOMContentLoaded", () => {
    initTheme();
    initDropzones();
    initServiceSearch();
});

// 1. TEMA CLARO / ESCURO
function initTheme() {
    const savedTheme = localStorage.getItem("atlas_theme") || "dark";
    document.documentElement.setAttribute("data-theme", savedTheme);

    const themeToggleBtn = document.getElementById("theme-toggle");
    if (themeToggleBtn) {
        updateThemeIcon(themeToggleBtn, savedTheme);
        themeToggleBtn.addEventListener("click", () => {
            const current = document.documentElement.getAttribute("data-theme") || "dark";
            const next = current === "dark" ? "light" : "dark";
            document.documentElement.setAttribute("data-theme", next);
            localStorage.setItem("atlas_theme", next);
            updateThemeIcon(themeToggleBtn, next);
        });
    }
}

function updateThemeIcon(btn, theme) {
    if (theme === "light") {
        btn.innerHTML = `
            <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <path d="M12 3a6 6 0 0 0 9 9 9 9 0 1 1-9-9Z"></path>
            </svg>
        `;
        btn.title = "Alternar para tema escuro";
    } else {
        btn.innerHTML = `
            <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <circle cx="12" cy="12" r="4"></circle>
                <path d="M12 2v2"></path>
                <path d="M12 20v2"></path>
                <path d="m4.93 4.93 1.41 1.41"></path>
                <path d="m17.66 17.66 1.41 1.41"></path>
                <path d="M2 12h2"></path>
                <path d="M20 12h2"></path>
                <path d="m6.34 17.66-1.41 1.41"></path>
                <path d="m19.07 4.93-1.41 1.41"></path>
            </svg>
        `;
        btn.title = "Alternar para tema claro";
    }
}

// 2. DRAG & DROP E FILE SELECTION
function initDropzones() {
    document.querySelectorAll(".upload-dropzone").forEach(dropzone => {
        const input = dropzone.querySelector("input[type='file']");
        const info = dropzone.querySelector(".file-chosen-info");
        const submitBtn = dropzone.closest("form").querySelector("button[type='submit']");

        if (!input) return;

        dropzone.addEventListener("click", () => {
            input.click();
        });

        input.addEventListener("change", () => {
            if (input.files.length > 0) {
                const file = input.files[0];
                const sizeKb = (file.size / 1024).toFixed(1);
                if (info) {
                    info.innerHTML = `📄 Arquivo: <strong>${file.name}</strong> (${sizeKb} KB)`;
                }
                if (submitBtn) {
                    submitBtn.disabled = false;
                }
            }
        });

        // Eventos de arrastar e soltar
        ['dragenter', 'dragover'].forEach(eventName => {
            dropzone.addEventListener(eventName, (e) => {
                e.preventDefault();
                e.stopPropagation();
                dropzone.classList.add("dragover");
            }, false);
        });

        ['dragleave', 'drop'].forEach(eventName => {
            dropzone.addEventListener(eventName, (e) => {
                e.preventDefault();
                e.stopPropagation();
                dropzone.classList.remove("dragover");
            }, false);
        });

        dropzone.addEventListener("drop", (e) => {
            const dt = e.dataTransfer;
            const files = dt.files;
            if (files.length > 0) {
                input.files = files;
                const file = files[0];
                const sizeKb = (file.size / 1024).toFixed(1);
                if (info) {
                    info.innerHTML = `📄 Arquivo: <strong>${file.name}</strong> (${sizeKb} KB)`;
                }
                if (submitBtn) {
                    submitBtn.disabled = false;
                }
            }
        });
    });
}

// 3. PESQUISA INSTANTÂNEA DE SERVIÇOS
function initServiceSearch() {
    const searchInput = document.getElementById("service-search-input");
    if (!searchInput) return;

    searchInput.addEventListener("input", () => {
        const query = searchInput.value.toLowerCase().trim();
        const rows = document.querySelectorAll("#services-table-body tr");
        rows.forEach(row => {
            const text = row.querySelector(".service-name")?.textContent.toLowerCase() || "";
            if (text.includes(query)) {
                row.style.display = "";
            } else {
                row.style.display = "none";
            }
        });
    });
}
