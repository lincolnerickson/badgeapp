/**
 * Field list and property editor panel.
 */
const FieldPanel = {
    selectedIndex: -1,
    fields: [],

    init() {
        document.getElementById('btn-add-field').addEventListener('click', () => this.addField());
        document.getElementById('btn-apply-props').addEventListener('click', () => this.applyProps());
        document.getElementById('btn-delete-field').addEventListener('click', () => this.deleteSelected());

        // Load initial fields
        this.refresh();
    },

    populateColumns(headers) {
        const sel = document.getElementById('csv-column-select');
        sel.innerHTML = '<option value="">-- CSV Column --</option>';
        (headers || []).forEach(h => {
            const opt = document.createElement('option');
            opt.value = h;
            opt.textContent = h;
            sel.appendChild(opt);
        });
    },

    populateFonts(fonts) {
        const sel = document.getElementById('prop-font');
        sel.innerHTML = '';
        (fonts || []).forEach(f => {
            const opt = document.createElement('option');
            opt.value = f;
            opt.textContent = f;
            sel.appendChild(opt);
        });
    },

    async refresh() {
        try {
            const data = await API.getFields();
            this.fields = data.fields || [];
        } catch (e) {
            this.fields = [];
        }
        this.renderList();
        // Keep selection if still valid
        if (this.selectedIndex >= this.fields.length) {
            this.selectedIndex = -1;
        }
        this.updatePropsPanel();
    },

    renderList() {
        const list = document.getElementById('field-list');
        if (this.fields.length === 0) {
            list.innerHTML = '<div class="empty-msg">No fields added</div>';
            return;
        }
        list.innerHTML = '';
        this.fields.forEach((f, idx) => {
            const item = document.createElement('div');
            item.className = 'field-item' + (idx === this.selectedIndex ? ' selected' : '');
            item.innerHTML = `
                <span class="field-name">${f.csv_column}</span>
                <span class="field-info">${f.font_family} ${f.font_size}px</span>
            `;
            item.addEventListener('click', () => this.select(idx));
            list.appendChild(item);
        });
    },

    select(idx) {
        this.selectedIndex = idx;
        this.renderList();
        this.updatePropsPanel();
        // Re-render SVG to show selection
        BadgeEditor.refresh();
    },

    deselect() {
        this.selectedIndex = -1;
        this.renderList();
        this.updatePropsPanel();
        BadgeEditor.refresh();
    },

    updatePropsPanel() {
        const panel = document.getElementById('field-props');
        if (this.selectedIndex < 0 || this.selectedIndex >= this.fields.length) {
            panel.style.display = 'none';
            return;
        }
        panel.style.display = '';
        const f = this.fields[this.selectedIndex];
        document.getElementById('prop-x').value = Math.round(f.x);
        document.getElementById('prop-y').value = Math.round(f.y);
        document.getElementById('prop-font').value = f.font_family;
        document.getElementById('prop-size').value = f.font_size;
        document.getElementById('prop-color').value = f.font_color || '#000000';
        document.getElementById('prop-bold').checked = f.bold;
        document.getElementById('prop-italic').checked = f.italic;
        document.getElementById('prop-align').value = f.alignment || 'center';
        document.getElementById('prop-max-width').value = f.max_width || 0;
    },

    async updatePropsFromServer(idx) {
        // Re-fetch fields and update panel
        await this.refresh();
        if (idx === this.selectedIndex) {
            this.updatePropsPanel();
        }
    },

    async addField() {
        const col = document.getElementById('csv-column-select').value;
        if (!col) {
            Toast.error('Select a CSV column first');
            return;
        }

        // Default position: center of badge
        const x = Math.round(App.config?.badge_width / 2) || 525;
        const y = Math.round(App.config?.badge_height / 2) || 300;

        try {
            const result = await API.addField({
                csv_column: col,
                x: x,
                y: y,
                font_family: 'Arial',
                font_size: 24,
                font_color: '#000000',
                bold: false,
                italic: false,
                alignment: 'center',
                max_width: 0,
            });
            if (result.ok) {
                this.selectedIndex = result.index;
                await this.refresh();
                await BadgeEditor.refresh();
                Toast.success(`Field added: ${col}`);
            }
        } catch (e) {
            Toast.error('Failed to add field');
        }
    },

    async applyProps() {
        if (this.selectedIndex < 0) return;

        const data = {
            x: parseFloat(document.getElementById('prop-x').value) || 0,
            y: parseFloat(document.getElementById('prop-y').value) || 0,
            font_family: document.getElementById('prop-font').value,
            font_size: parseInt(document.getElementById('prop-size').value) || 24,
            font_color: document.getElementById('prop-color').value,
            bold: document.getElementById('prop-bold').checked,
            italic: document.getElementById('prop-italic').checked,
            alignment: document.getElementById('prop-align').value,
            max_width: parseInt(document.getElementById('prop-max-width').value) || 0,
        };

        try {
            const result = await API.updateField(this.selectedIndex, data);
            if (result.ok) {
                await this.refresh();
                await BadgeEditor.refresh();
                Toast.info('Field updated');
            }
        } catch (e) {
            Toast.error('Failed to update field');
        }
    },

    async deleteSelected() {
        if (this.selectedIndex < 0) return;
        const field = this.fields[this.selectedIndex];
        try {
            const result = await API.deleteField(this.selectedIndex);
            if (result.ok) {
                this.selectedIndex = -1;
                await this.refresh();
                await BadgeEditor.refresh();
                Toast.info(`Field removed: ${field.csv_column}`);
            }
        } catch (e) {
            Toast.error('Failed to delete field');
        }
    },
};
