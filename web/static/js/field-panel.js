/**
 * Field list and property editor panel.
 */
const FieldPanel = {
    selectedIndex: -1,
    fields: [],

    init() {
        document.getElementById('btn-add-field').addEventListener('click', () => this.addField());
        document.getElementById('btn-add-text').addEventListener('click', () => this.addStaticTextField());
        document.getElementById('btn-apply-props').addEventListener('click', () => this.applyProps());
        document.getElementById('btn-delete-field').addEventListener('click', () => this.deleteSelected());
        document.getElementById('btn-add-rule').addEventListener('click', () => this.addRule());

        // Load initial fields
        this.refresh();
    },

    _csvHeaders() {
        const sel = document.getElementById('csv-column-select');
        return Array.from(sel.options)
            .map(o => o.value)
            .filter(v => v !== '');
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
        const currentSide = App.currentSide || 'front';
        const sideFields = this.fields.filter(f => (f.side || 'front') === currentSide);
        if (sideFields.length === 0) {
            list.innerHTML = '<div class="empty-msg">No fields added</div>';
            return;
        }
        list.innerHTML = '';
        // Build mapping from filtered index to global index
        this._filteredToGlobal = [];
        this.fields.forEach((f, idx) => {
            if ((f.side || 'front') !== currentSide) return;
            this._filteredToGlobal.push(idx);
            const item = document.createElement('div');
            item.className = 'field-item' + (idx === this.selectedIndex ? ' selected' : '');
            let label;
            if (f.static_text) {
                label = `"${f.static_text}"`;
            } else if ((f.rules || []).length > 0) {
                label = `${f.csv_column || 'conditional'} (conditional)`;
            } else {
                label = f.csv_column;
            }
            item.innerHTML = `
                <span class="field-name">${escapeHTML(label)}</span>
                <span class="field-info">${escapeHTML(f.font_family)} ${f.font_size}px</span>
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
        document.getElementById('prop-static-text').value = f.static_text || '';
        document.getElementById('prop-x').value = Math.round(f.x);
        document.getElementById('prop-y').value = Math.round(f.y);
        document.getElementById('prop-font').value = f.font_family;
        document.getElementById('prop-size').value = f.font_size;
        document.getElementById('prop-color').value = f.font_color || '#000000';
        document.getElementById('prop-bold').checked = f.bold;
        document.getElementById('prop-italic').checked = f.italic;
        document.getElementById('prop-align').value = f.alignment || 'center';
        document.getElementById('prop-max-width').value = f.max_width || 0;
        document.getElementById('prop-wrap').checked = !!f.wrap;
        document.getElementById('prop-line-height').value = f.line_height || 1.0;
        this.renderRules(f.rules || []);
    },

    renderRules(rules) {
        const list = document.getElementById('rules-list');
        list.innerHTML = '';
        const headers = this._csvHeaders();
        rules.forEach((rule, i) => list.appendChild(this._buildRuleRow(rule, i, headers)));
    },

    _buildRuleRow(rule, index, headers) {
        const row = document.createElement('div');
        row.className = 'rule-row';
        row.dataset.index = index;

        const colSel = document.createElement('select');
        colSel.className = 'rule-column';
        const blank = document.createElement('option');
        blank.value = '';
        blank.textContent = '-- column --';
        colSel.appendChild(blank);
        headers.forEach(h => {
            const opt = document.createElement('option');
            opt.value = h;
            opt.textContent = h;
            if (h === rule.column) opt.selected = true;
            colSel.appendChild(opt);
        });
        if (rule.column && !headers.includes(rule.column)) {
            const opt = document.createElement('option');
            opt.value = rule.column;
            opt.textContent = rule.column + ' (missing)';
            opt.selected = true;
            colSel.appendChild(opt);
        }

        const matchSel = document.createElement('select');
        matchSel.className = 'rule-match';
        const optY = document.createElement('option');
        optY.value = 'y';
        optY.textContent = 'starts with Y';
        const optND = document.createElement('option');
        optND.value = 'non_dash';
        optND.textContent = 'not - / blank';
        matchSel.appendChild(optY);
        matchSel.appendChild(optND);
        matchSel.value = rule.match || 'y';

        const textInput = document.createElement('input');
        textInput.type = 'text';
        textInput.className = 'rule-text';
        textInput.placeholder = 'Text (prefix)';
        textInput.value = rule.text || '';

        const removeBtn = document.createElement('button');
        removeBtn.type = 'button';
        removeBtn.className = 'rule-remove';
        removeBtn.textContent = '×';
        removeBtn.title = 'Remove rule';
        removeBtn.addEventListener('click', () => row.remove());

        row.appendChild(colSel);
        row.appendChild(matchSel);
        row.appendChild(textInput);
        row.appendChild(removeBtn);
        return row;
    },

    _readRulesFromUI() {
        const rows = document.querySelectorAll('#rules-list .rule-row');
        const rules = [];
        rows.forEach(row => {
            const column = row.querySelector('.rule-column').value;
            const text = row.querySelector('.rule-text').value;
            const match = row.querySelector('.rule-match').value || 'y';
            if (column || text) {
                rules.push({ column, text, match });
            }
        });
        return rules;
    },

    addRule() {
        if (this.selectedIndex < 0) return;
        const list = document.getElementById('rules-list');
        list.appendChild(this._buildRuleRow({ column: '', text: '' }, list.children.length, this._csvHeaders()));
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
                side: App.currentSide || 'front',
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

    async addStaticTextField() {
        const x = Math.round(App.config?.badge_width / 2) || 525;
        const y = Math.round(App.config?.badge_height / 2) || 300;
        try {
            const result = await API.addField({
                csv_column: '',
                static_text: 'Text',
                x: x,
                y: y,
                font_family: 'Arial',
                font_size: 24,
                font_color: '#000000',
                bold: false,
                italic: false,
                alignment: 'center',
                max_width: 0,
                side: App.currentSide || 'front',
            });
            if (result.ok) {
                this.selectedIndex = result.index;
                await this.refresh();
                await BadgeEditor.refresh();
                Toast.success('Static text added');
            }
        } catch (e) {
            Toast.error('Failed to add text');
        }
    },

    async applyProps() {
        if (this.selectedIndex < 0) return;

        const data = {
            static_text: document.getElementById('prop-static-text').value,
            x: parseFloat(document.getElementById('prop-x').value) || 0,
            y: parseFloat(document.getElementById('prop-y').value) || 0,
            font_family: document.getElementById('prop-font').value,
            font_size: parseInt(document.getElementById('prop-size').value) || 24,
            font_color: document.getElementById('prop-color').value,
            bold: document.getElementById('prop-bold').checked,
            italic: document.getElementById('prop-italic').checked,
            alignment: document.getElementById('prop-align').value,
            max_width: parseInt(document.getElementById('prop-max-width').value) || 0,
            wrap: document.getElementById('prop-wrap').checked,
            line_height: parseFloat(document.getElementById('prop-line-height').value) || 1.0,
            rules: this._readRulesFromUI(),
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
