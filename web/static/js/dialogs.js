/**
 * Modal dialogs: manual entry, edit badge, delete confirmation, PDF export progress.
 */
const Dialogs = {
    backdrop: null,
    container: null,

    init() {
        this.backdrop = document.getElementById('modal-backdrop');
        this.container = document.getElementById('modal-container');

        this.backdrop.addEventListener('click', () => this.close());

        // Escape key closes modal
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape' && !this.container.classList.contains('hidden')) {
                this.close();
            }
        });
    },

    open(title, bodyHTML, footerHTML) {
        this.container.innerHTML = `
            <div class="modal-header">
                <span>${title}</span>
                <button class="close-btn" id="modal-close-btn">&times;</button>
            </div>
            <div class="modal-body">${bodyHTML}</div>
            ${footerHTML ? `<div class="modal-footer">${footerHTML}</div>` : ''}
        `;
        this.backdrop.classList.remove('hidden');
        this.container.classList.remove('hidden');

        document.getElementById('modal-close-btn').addEventListener('click', () => this.close());

        // Focus first input if any
        const firstInput = this.container.querySelector('input, select');
        if (firstInput) setTimeout(() => firstInput.focus(), 50);
    },

    close() {
        this.backdrop.classList.add('hidden');
        this.container.classList.add('hidden');
        this.container.innerHTML = '';
    },

    // ---- Manual Entry ----

    async showManualEntry() {
        if (!App.csvInfo?.loaded) {
            Toast.error('Load a CSV file first');
            return;
        }

        const headers = App.csvInfo.headers;
        let formHTML = '';

        // Try to get next badge number
        let nextBadge = '';
        for (const h of headers) {
            if (h.toLowerCase().includes('badge') && h.toLowerCase().includes('number')) {
                try {
                    const data = await API.getNextBadgeNumber(h);
                    nextBadge = data.next;
                } catch (e) {}
                break;
            }
        }

        headers.forEach(h => {
            const isBadgeNum = h.toLowerCase().includes('badge') && h.toLowerCase().includes('number');
            const defaultVal = isBadgeNum && nextBadge ? nextBadge : '';
            formHTML += `
                <div class="form-group">
                    <label>${escapeHTML(h)}</label>
                    <input type="text" id="manual-${CSS.escape(h)}" value="${defaultVal}" data-column="${escapeHTML(h)}">
                </div>
            `;
        });

        const footer = `
            <button id="manual-cancel">Cancel</button>
            <button id="manual-save" class="accent">Add Badge</button>
        `;

        this.open('Manual Entry', formHTML, footer);

        document.getElementById('manual-cancel').addEventListener('click', () => this.close());
        document.getElementById('manual-save').addEventListener('click', () => this.saveManualEntry());

        // Enter key submits
        this.container.querySelectorAll('input').forEach(input => {
            input.addEventListener('keydown', (e) => {
                if (e.key === 'Enter') {
                    e.preventDefault();
                    this.saveManualEntry();
                }
            });
        });
    },

    async saveManualEntry() {
        const inputs = this.container.querySelectorAll('.modal-body input[data-column]');
        const row = {};
        inputs.forEach(input => {
            row[input.dataset.column] = input.value;
        });

        try {
            const result = await API.addRow(row);
            if (result.ok) {
                App.csvInfo.row_count = result.index + 1;
                App.currentRow = result.index;
                NavBar.update(result.index, result.index + 1);
                // Reload CSV info to get accurate count
                await App.loadCSVInfo();
                NavBar.update(App.currentRow, App.csvInfo.row_count);
                App.updateUIState();
                await App.refreshEditor();
                this.close();
                Toast.success('Badge added');
            }
        } catch (e) {
            Toast.error('Failed to add badge');
        }
    },

    // ---- Edit Badge ----

    async showEditBadge() {
        if (!App.csvInfo?.loaded || App.csvInfo.row_count === 0) return;

        let rowData = {};
        try {
            const data = await API.getRow(App.currentRow);
            rowData = data.row || {};
        } catch (e) {
            Toast.error('Failed to load badge data');
            return;
        }

        const headers = App.csvInfo.headers;
        let formHTML = '';
        headers.forEach(h => {
            const val = escapeHTML(rowData[h] || '');
            formHTML += `
                <div class="form-group">
                    <label>${escapeHTML(h)}</label>
                    <input type="text" id="edit-${CSS.escape(h)}" value="${val}" data-column="${escapeHTML(h)}">
                </div>
            `;
        });

        const footer = `
            <button id="edit-cancel">Cancel</button>
            <button id="edit-save" class="accent">Save Changes</button>
        `;

        this.open(`Edit Badge (Row ${App.currentRow + 1})`, formHTML, footer);

        document.getElementById('edit-cancel').addEventListener('click', () => this.close());
        document.getElementById('edit-save').addEventListener('click', () => this.saveEditBadge());

        this.container.querySelectorAll('input').forEach(input => {
            input.addEventListener('keydown', (e) => {
                if (e.key === 'Enter') {
                    e.preventDefault();
                    this.saveEditBadge();
                }
            });
        });
    },

    async saveEditBadge() {
        const inputs = this.container.querySelectorAll('.modal-body input[data-column]');
        const row = {};
        inputs.forEach(input => {
            row[input.dataset.column] = input.value;
        });

        try {
            const result = await API.updateRow(App.currentRow, row);
            if (result.ok) {
                await App.refreshEditor();
                this.close();
                Toast.success('Badge updated');
            }
        } catch (e) {
            Toast.error('Failed to update badge');
        }
    },

    // ---- Delete Badge ----

    confirmDeleteBadge() {
        if (!App.csvInfo?.loaded || App.csvInfo.row_count === 0) return;

        const body = `<p>Delete badge at row ${App.currentRow + 1}? This cannot be undone.</p>`;
        const footer = `
            <button id="delete-cancel">Cancel</button>
            <button id="delete-confirm" class="danger">Delete</button>
        `;

        this.open('Delete Badge', body, footer);

        document.getElementById('delete-cancel').addEventListener('click', () => this.close());
        document.getElementById('delete-confirm').addEventListener('click', () => this.doDeleteBadge());
    },

    async doDeleteBadge() {
        try {
            const result = await API.deleteRow(App.currentRow);
            if (result.ok) {
                await App.loadCSVInfo();
                if (App.currentRow >= App.csvInfo.row_count && App.csvInfo.row_count > 0) {
                    App.currentRow = App.csvInfo.row_count - 1;
                }
                NavBar.update(App.currentRow, App.csvInfo.row_count);
                App.updateUIState();
                await App.refreshEditor();
                this.close();
                Toast.success('Badge deleted');
            }
        } catch (e) {
            Toast.error('Failed to delete badge');
        }
    },

    // ---- PDF Export ----

    async showExportPDF() {
        if (!App.csvInfo?.loaded || App.csvInfo.row_count === 0) return;

        const body = `
            <p>Export ${App.csvInfo.row_count} badge(s) to PDF.</p>
            <div class="progress-bar" style="margin-top:12px">
                <div class="progress-fill" id="export-progress-fill" style="width:0%"></div>
            </div>
            <div class="progress-text" id="export-progress-text">Starting...</div>
        `;
        const footer = `<button id="export-close" disabled>Close</button>`;

        this.open('Exporting PDF', body, footer);
        document.getElementById('export-close').addEventListener('click', () => this.close());

        // Start export
        try {
            const result = await API.startPDFExport();
            if (result.error) {
                Toast.error(result.error);
                this.close();
                return;
            }
            this.pollExport(result.task_id);
        } catch (e) {
            Toast.error('Failed to start export');
            this.close();
        }
    },

    async pollExport(taskId) {
        const fill = document.getElementById('export-progress-fill');
        const text = document.getElementById('export-progress-text');
        const closeBtn = document.getElementById('export-close');

        const poll = async () => {
            try {
                const status = await API.getPDFStatus(taskId);

                if (status.status === 'running') {
                    const pct = status.total > 0 ? Math.round((status.progress / status.total) * 100) : 0;
                    if (fill) fill.style.width = pct + '%';
                    if (text) text.textContent = `${status.progress} of ${status.total} badges...`;
                    setTimeout(poll, 500);
                } else if (status.status === 'done') {
                    if (fill) fill.style.width = '100%';
                    if (text) text.textContent = 'Complete! Downloading...';
                    if (closeBtn) closeBtn.disabled = false;

                    // Trigger download
                    API.downloadFile(API.getPDFDownloadURL(taskId), 'badges.pdf');
                    Toast.success('PDF exported successfully');
                } else if (status.status === 'error') {
                    if (text) text.textContent = `Error: ${status.error}`;
                    if (closeBtn) closeBtn.disabled = false;
                    Toast.error('PDF export failed');
                }
            } catch (e) {
                if (text) text.textContent = 'Connection lost';
                if (closeBtn) closeBtn.disabled = false;
            }
        };

        setTimeout(poll, 500);
    },
};
