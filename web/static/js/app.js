/**
 * Main application controller - wires all modules together.
 */
const App = {
    // Cached state
    config: null,
    csvInfo: null,
    currentRow: 0,
    fonts: [],

    async init() {
        Toast.init();

        // Load initial state from server
        await this.loadConfig();
        await this.loadCSVInfo();
        this.loadFonts(); // async, don't await

        // Initialize modules
        BadgeEditor.init();
        FieldPanel.init();
        NavBar.init();
        Dialogs.init();

        // Wire toolbar buttons
        this.bindToolbar();
        this.bindKeyboard();

        // Update UI state
        this.updateUIState();
    },

    async loadConfig() {
        try {
            this.config = await API.getConfig();
            BadgeEditor.updateSize(this.config.badge_width, this.config.badge_height);
        } catch (e) {
            console.error('Failed to load config:', e);
        }
    },

    async loadCSVInfo() {
        try {
            this.csvInfo = await API.getCSVInfo();
            this.currentRow = this.csvInfo.current_row || 0;
        } catch (e) {
            console.error('Failed to load CSV info:', e);
        }
    },

    async loadFonts() {
        try {
            const data = await API.getFonts();
            this.fonts = data.fonts || [];
            FieldPanel.populateFonts(this.fonts);
        } catch (e) {
            console.error('Failed to load fonts:', e);
        }
    },

    // --- Toolbar ---

    bindToolbar() {
        // File inputs
        const fileImage = document.getElementById('file-image');
        const fileCSV = document.getElementById('file-csv');
        const fileTemplate = document.getElementById('file-template');

        document.getElementById('btn-open-image').addEventListener('click', () => fileImage.click());
        document.getElementById('btn-open-csv').addEventListener('click', () => fileCSV.click());
        document.getElementById('btn-save-csv').addEventListener('click', () => this.saveCSV());
        document.getElementById('btn-load-template').addEventListener('click', () => fileTemplate.click());
        document.getElementById('btn-save-template').addEventListener('click', () => this.saveTemplate());
        document.getElementById('btn-manual-entry').addEventListener('click', () => Dialogs.showManualEntry());
        document.getElementById('btn-edit-badge').addEventListener('click', () => Dialogs.showEditBadge());
        document.getElementById('btn-delete-badge').addEventListener('click', () => Dialogs.confirmDeleteBadge());
        document.getElementById('btn-export-pdf').addEventListener('click', () => Dialogs.showExportPDF());
        document.getElementById('btn-print-badge').addEventListener('click', () => this.printBadge());

        // Preview toggle
        document.getElementById('preview-toggle').addEventListener('change', (e) => {
            BadgeEditor.setPreviewMode(e.target.checked);
        });

        // PDF settings
        document.getElementById('btn-apply-pdf').addEventListener('click', () => this.applyPDFSettings());

        // File input handlers
        fileImage.addEventListener('change', (e) => {
            if (e.target.files[0]) this.uploadImage(e.target.files[0]);
            e.target.value = '';
        });
        fileCSV.addEventListener('change', (e) => {
            if (e.target.files[0]) this.uploadCSV(e.target.files[0]);
            e.target.value = '';
        });
        fileTemplate.addEventListener('change', (e) => {
            if (e.target.files[0]) this.loadTemplate(e.target.files[0]);
            e.target.value = '';
        });
    },

    bindKeyboard() {
        document.addEventListener('keydown', (e) => {
            // Don't intercept when typing in inputs
            if (e.target.matches('input, select, textarea')) {
                if (e.key === 'Escape') e.target.blur();
                return;
            }

            if (e.ctrlKey && e.key === 'i') {
                e.preventDefault();
                document.getElementById('file-image').click();
            } else if (e.ctrlKey && e.key === 'o') {
                e.preventDefault();
                document.getElementById('file-csv').click();
            } else if (e.ctrlKey && e.key === 's') {
                e.preventDefault();
                this.saveCSV();
            } else if (e.ctrlKey && e.key === 'n') {
                e.preventDefault();
                Dialogs.showManualEntry();
            } else if (e.ctrlKey && e.key === 'e') {
                e.preventDefault();
                Dialogs.showEditBadge();
            } else if (e.ctrlKey && e.key === 'f') {
                e.preventDefault();
                document.getElementById('search-input').focus();
            } else if (e.key === 'ArrowLeft') {
                NavBar.prev();
            } else if (e.key === 'ArrowRight') {
                NavBar.next();
            } else if (e.key === 'Delete') {
                if (FieldPanel.selectedIndex >= 0) {
                    FieldPanel.deleteSelected();
                }
            }
        });
    },

    // --- Actions ---

    async uploadImage(file) {
        try {
            const result = await API.uploadImage(file);
            if (result.error) {
                Toast.error(result.error);
                return;
            }
            this.config.badge_width = result.width;
            this.config.badge_height = result.height;
            BadgeEditor.updateSize(result.width, result.height);
            BadgeEditor.setBackground(API.getBackgroundURL());
            document.getElementById('status-image').textContent =
                `Image: ${result.filename} (${result.width} x ${result.height})`;
            Toast.success(`Image loaded: ${result.filename}`);
            this.refreshEditor();
        } catch (e) {
            Toast.error('Failed to upload image');
        }
    },

    async uploadCSV(file) {
        try {
            const result = await API.uploadCSV(file);
            if (result.error) {
                Toast.error(result.error);
                return;
            }
            this.csvInfo = {
                loaded: true,
                filename: result.filename,
                headers: result.headers,
                row_count: result.row_count,
                current_row: 0,
            };
            this.currentRow = 0;
            FieldPanel.populateColumns(result.headers);
            NavBar.update(0, result.row_count);
            document.getElementById('status-csv').textContent =
                `CSV: ${result.filename} (${result.row_count} rows)`;
            Toast.success(`CSV loaded: ${result.row_count} rows`);
            this.updateUIState();
            this.refreshEditor();
        } catch (e) {
            Toast.error('Failed to upload CSV');
        }
    },

    async saveCSV() {
        if (!this.csvInfo?.loaded) return;
        try {
            const blob = await API.downloadCSV();
            API.downloadBlob(blob, this.csvInfo.filename || 'badges.csv');
            Toast.success('CSV downloaded');
        } catch (e) {
            Toast.error('Failed to save CSV');
        }
    },

    async saveTemplate() {
        try {
            const blob = await API.downloadTemplate();
            API.downloadBlob(blob, 'badge_template.json');
            Toast.success('Template saved');
        } catch (e) {
            Toast.error('Failed to save template');
        }
    },

    async loadTemplate(file) {
        try {
            const result = await API.uploadTemplate(file);
            if (result.error) {
                Toast.error(result.error);
                return;
            }
            this.config = result.config;
            BadgeEditor.updateSize(result.config.badge_width, result.config.badge_height);
            await FieldPanel.refresh();
            Toast.success('Template loaded');
            this.refreshEditor();
        } catch (e) {
            Toast.error('Failed to load template');
        }
    },

    async applyPDFSettings() {
        const data = {
            badges_per_row: parseInt(document.getElementById('pdf-cols').value) || 2,
            badges_per_col: parseInt(document.getElementById('pdf-rows').value) || 4,
            page_size: document.getElementById('pdf-page-size').value,
            margin_mm: parseFloat(document.getElementById('pdf-margin').value) || 10,
            spacing_mm: parseFloat(document.getElementById('pdf-spacing').value) || 2,
        };
        try {
            const result = await API.updateConfig(data);
            if (result.ok) {
                this.config = result.config;
                Toast.success('PDF settings updated');
            }
        } catch (e) {
            Toast.error('Failed to update settings');
        }
    },

    printBadge() {
        if (!this.csvInfo?.loaded) return;
        // Download single-badge PDF for printing via OS dialog
        API.downloadFile(API.getSinglePDFURL(this.currentRow), `badge_${this.currentRow + 1}.pdf`);
    },

    // --- State management ---

    updateUIState() {
        const hasCSV = this.csvInfo?.loaded;
        document.getElementById('btn-save-csv').disabled = !hasCSV;
        document.getElementById('btn-manual-entry').disabled = !hasCSV;
        document.getElementById('btn-edit-badge').disabled = !hasCSV || (this.csvInfo?.row_count || 0) === 0;
        document.getElementById('btn-delete-badge').disabled = !hasCSV || (this.csvInfo?.row_count || 0) === 0;
        document.getElementById('btn-export-pdf').disabled = !hasCSV || (this.csvInfo?.row_count || 0) === 0;
        document.getElementById('btn-print-badge').disabled = !hasCSV || (this.csvInfo?.row_count || 0) === 0;
        document.getElementById('csv-column-select').disabled = !hasCSV;
        document.getElementById('btn-add-field').disabled = !hasCSV;
        document.getElementById('search-input').disabled = !hasCSV;
        document.getElementById('btn-search').disabled = !hasCSV;

        if (hasCSV) {
            FieldPanel.populateColumns(this.csvInfo.headers);
            NavBar.update(this.currentRow, this.csvInfo.row_count);
        }

        // PDF settings from config
        if (this.config) {
            document.getElementById('pdf-cols').value = this.config.badges_per_row;
            document.getElementById('pdf-rows').value = this.config.badges_per_col;
            document.getElementById('pdf-page-size').value = this.config.page_size;
            document.getElementById('pdf-margin').value = this.config.margin_mm;
            document.getElementById('pdf-spacing').value = this.config.spacing_mm;
            document.getElementById('badge-size-info').textContent =
                `${this.config.badge_width} x ${this.config.badge_height} px`;
        }
    },

    /**
     * Refresh the SVG editor and preview with current state.
     */
    async refreshEditor() {
        await BadgeEditor.refresh();
    },

    /**
     * Called by NavBar when the current row changes.
     */
    async onRowChanged(idx) {
        this.currentRow = idx;
        if (this.csvInfo) {
            this.csvInfo.current_row = idx;
        }
        await this.refreshEditor();
    },
};

// Boot
document.addEventListener('DOMContentLoaded', () => App.init());
