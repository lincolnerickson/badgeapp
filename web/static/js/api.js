/**
 * API wrapper - all server communication goes through here.
 */
const API = {
    token: '',

    init() {
        const meta = document.querySelector('meta[name="app-token"]');
        this.token = meta ? meta.content : '';
    },

    _headers(extra) {
        return Object.assign({ 'X-App-Token': this.token }, extra || {});
    },

    _urlWithToken(url) {
        const sep = url.includes('?') ? '&' : '?';
        return url + sep + 'token=' + encodeURIComponent(this.token);
    },

    // --- File uploads ---

    async uploadImage(file) {
        const fd = new FormData();
        fd.append('file', file);
        const resp = await fetch('/api/upload-image', { method: 'POST', body: fd, headers: this._headers() });
        return resp.json();
    },

    async uploadCSV(file) {
        const fd = new FormData();
        fd.append('file', file);
        const resp = await fetch('/api/upload-csv', { method: 'POST', body: fd, headers: this._headers() });
        return resp.json();
    },

    async downloadCSV() {
        const resp = await fetch('/api/download-csv', { headers: this._headers() });
        if (!resp.ok) throw new Error('Download failed');
        const blob = await resp.blob();
        return blob;
    },

    async saveCSV() {
        const resp = await fetch('/api/csv/save', { method: 'POST', headers: this._headers() });
        return resp.json();
    },

    async uploadTemplate(file) {
        const fd = new FormData();
        fd.append('file', file);
        const resp = await fetch('/api/upload-template', { method: 'POST', body: fd, headers: this._headers() });
        return resp.json();
    },

    async downloadTemplate() {
        const resp = await fetch('/api/download-template', { headers: this._headers() });
        if (!resp.ok) throw new Error('Download failed');
        return resp.blob();
    },

    // --- Config ---

    async getConfig() {
        const resp = await fetch('/api/config', { headers: this._headers() });
        return resp.json();
    },

    async updateConfig(data) {
        const resp = await fetch('/api/config', {
            method: 'PUT',
            headers: this._headers({ 'Content-Type': 'application/json' }),
            body: JSON.stringify(data),
        });
        return resp.json();
    },

    // --- Fields ---

    async getFields() {
        const resp = await fetch('/api/fields', { headers: this._headers() });
        return resp.json();
    },

    async addField(data) {
        const resp = await fetch('/api/fields', {
            method: 'POST',
            headers: this._headers({ 'Content-Type': 'application/json' }),
            body: JSON.stringify(data),
        });
        return resp.json();
    },

    async updateField(idx, data) {
        const resp = await fetch(`/api/fields/${idx}`, {
            method: 'PUT',
            headers: this._headers({ 'Content-Type': 'application/json' }),
            body: JSON.stringify(data),
        });
        return resp.json();
    },

    async deleteField(idx) {
        const resp = await fetch(`/api/fields/${idx}`, { method: 'DELETE', headers: this._headers() });
        return resp.json();
    },

    async getFonts() {
        const resp = await fetch('/api/fonts', { headers: this._headers() });
        return resp.json();
    },

    // --- CSV data ---

    async getCSVInfo() {
        const resp = await fetch('/api/csv/info', { headers: this._headers() });
        return resp.json();
    },

    async getRow(idx) {
        const resp = await fetch(`/api/csv/row/${idx}`, { headers: this._headers() });
        return resp.json();
    },

    async addRow(row) {
        const resp = await fetch('/api/csv/row', {
            method: 'POST',
            headers: this._headers({ 'Content-Type': 'application/json' }),
            body: JSON.stringify({ row }),
        });
        return resp.json();
    },

    async updateRow(idx, row) {
        const resp = await fetch(`/api/csv/row/${idx}`, {
            method: 'PUT',
            headers: this._headers({ 'Content-Type': 'application/json' }),
            body: JSON.stringify({ row }),
        });
        return resp.json();
    },

    async deleteRow(idx) {
        const resp = await fetch(`/api/csv/row/${idx}`, { method: 'DELETE', headers: this._headers() });
        return resp.json();
    },

    async searchCSV(query) {
        const resp = await fetch(`/api/csv/search?q=${encodeURIComponent(query)}`, { headers: this._headers() });
        return resp.json();
    },

    async getNextBadgeNumber(column) {
        const resp = await fetch(`/api/csv/next-badge-number?column=${encodeURIComponent(column)}`, { headers: this._headers() });
        return resp.json();
    },

    // --- Rendering & export ---

    getPreviewURL(rowIdx) {
        return this._urlWithToken(`/api/preview/${rowIdx}?t=${Date.now()}`);
    },

    getPreviewCustomURL(values) {
        return this._urlWithToken(`/api/preview-custom?values=${encodeURIComponent(JSON.stringify(values))}&t=${Date.now()}`);
    },

    getBackgroundURL() {
        return this._urlWithToken(`/api/background-image?t=${Date.now()}`);
    },

    async getBackgroundInfo() {
        const resp = await fetch('/api/background-info', { headers: this._headers() });
        return resp.json();
    },

    async startPDFExport() {
        const resp = await fetch('/api/export-pdf', { method: 'POST', headers: this._headers() });
        return resp.json();
    },

    async getPDFStatus(taskId) {
        const resp = await fetch(`/api/export-pdf/status/${taskId}`, { headers: this._headers() });
        return resp.json();
    },

    getPDFDownloadURL(taskId) {
        return this._urlWithToken(`/api/export-pdf/download/${taskId}`);
    },

    getSinglePDFURL(rowIdx) {
        return this._urlWithToken(`/api/export-single-pdf/${rowIdx}`);
    },

    getSingleImageURL(rowIdx) {
        return this._urlWithToken(`/api/export-single-image/${rowIdx}`);
    },

    /**
     * Trigger a file download from a URL.
     */
    downloadFile(url, filename) {
        const a = document.createElement('a');
        a.href = url;
        a.download = filename || '';
        document.body.appendChild(a);
        a.click();
        a.remove();
    },

    /**
     * Download a Blob as a file.
     */
    downloadBlob(blob, filename) {
        const url = URL.createObjectURL(blob);
        this.downloadFile(url, filename);
        setTimeout(() => URL.revokeObjectURL(url), 5000);
    },
};
