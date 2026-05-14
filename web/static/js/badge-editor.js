/**
 * SVG badge editor with drag-and-drop field positioning.
 */
const BadgeEditor = {
    svg: null,
    bgRect: null,
    bgImage: null,
    fieldsGroup: null,
    previewImg: null,
    container: null,

    badgeWidth: 1050,
    badgeHeight: 600,
    previewMode: false,

    // Drag state
    dragging: null,
    dragStartX: 0,
    dragStartY: 0,
    fieldStartX: 0,
    fieldStartY: 0,

    init() {
        this.svg = document.getElementById('badge-svg');
        this.bgRect = document.getElementById('badge-bg-rect');
        this.bgImage = document.getElementById('badge-bg-image');
        this.fieldsGroup = document.getElementById('fields-group');
        this.previewImg = document.getElementById('preview-img');
        this.container = document.getElementById('canvas-container');

        this.updateSize(this.badgeWidth, this.badgeHeight);

        // Pointer events for drag
        this.svg.addEventListener('pointerdown', (e) => this.onPointerDown(e));
        document.addEventListener('pointermove', (e) => this.onPointerMove(e));
        document.addEventListener('pointerup', (e) => this.onPointerUp(e));

        // Click on background deselects
        this.svg.addEventListener('click', (e) => {
            if (e.target === this.svg || e.target === this.bgRect || e.target === this.bgImage) {
                FieldPanel.deselect();
            }
        });
    },

    updateSize(w, h) {
        this.badgeWidth = w;
        this.badgeHeight = h;
        this.svg.setAttribute('viewBox', `0 0 ${w} ${h}`);
        // Maintain aspect ratio via CSS
        const aspect = w / h;
        // Max container size limited by CSS flex, just set aspect
        this.svg.style.aspectRatio = `${w} / ${h}`;
    },

    setBackground(url) {
        if (url) {
            this.bgImage.setAttribute('href', url);
            this.bgImage.setAttribute('width', this.badgeWidth);
            this.bgImage.setAttribute('height', this.badgeHeight);
            this.bgImage.style.display = '';
            this.bgRect.style.display = 'none';
        } else {
            this.bgImage.style.display = 'none';
            this.bgRect.style.display = '';
        }
    },

    setPreviewMode(on) {
        this.previewMode = on;
        if (on) {
            this.svg.style.display = 'none';
            this.previewImg.style.display = '';
            this.updatePreview();
        } else {
            this.svg.style.display = '';
            this.previewImg.style.display = 'none';
        }
    },

    updatePreview() {
        if (!App.csvInfo?.loaded || App.csvInfo.row_count === 0) return;
        this.previewImg.src = API.getPreviewURL(App.currentRow, App.currentSide);
    },

    /**
     * Resolve the display text for a field, mirroring the server-side renderer.
     * Honors conditional rules: first rule whose cell starts with 'Y' wins;
     * any text after the leading Y is appended with a space.
     */
    resolveFieldText(field, rowData) {
        if (field.static_text) return field.static_text;
        const rules = field.rules || [];
        if (rules.length === 0) {
            // No rules — show the row value if loaded, otherwise the column name as a placeholder.
            return (rowData[field.csv_column] !== undefined ? rowData[field.csv_column] : field.csv_column) || '';
        }
        for (const rule of rules) {
            const cell = (rowData[rule.column] || '').trim();
            const mode = rule.match || 'y';
            if (mode === 'non_dash') {
                if (!cell || cell === '-') continue;
                return rule.text ? `${rule.text} ${cell}`.trim() : cell;
            }
            // default 'y'
            if (!cell || cell[0] !== 'Y') continue;
            const trailing = cell.slice(1).trim();
            return trailing ? `${rule.text} ${trailing}`.trimEnd() : rule.text;
        }
        return '';
    },

    /**
     * Full refresh: rebuild SVG fields and update preview.
     */
    async refresh() {
        // Reload fields from server
        let fields = [];
        try {
            const data = await API.getFields();
            fields = data.fields || [];
        } catch (e) {
            console.error('Failed to load fields:', e);
        }

        // Get current row data
        let rowData = {};
        if (App.csvInfo?.loaded && App.csvInfo.row_count > 0) {
            try {
                const data = await API.getRow(App.currentRow);
                rowData = data.row || {};
            } catch (e) {
                console.error('Failed to load row:', e);
            }
        }

        // Rebuild SVG text elements (filtered by current side)
        this.fieldsGroup.innerHTML = '';
        const currentSide = App.currentSide || 'front';
        fields.forEach((field, idx) => {
            if ((field.side || 'front') !== currentSide) return;
            const text = this.resolveFieldText(field, rowData);
            const el = this.createFieldElement(field, idx, text);
            this.fieldsGroup.appendChild(el);
        });

        // Update background
        if (App.config?.badge_width) {
            this.bgImage.setAttribute('width', this.badgeWidth);
            this.bgImage.setAttribute('height', this.badgeHeight);
        }

        // Update preview if in preview mode
        if (this.previewMode) {
            this.updatePreview();
        }
    },

    createFieldElement(field, idx, displayText) {
        const NS = 'http://www.w3.org/2000/svg';
        const g = document.createElementNS(NS, 'g');
        g.dataset.fieldIndex = idx;
        g.classList.add('svg-field-text');

        const dpi = (App.config && App.config.dpi) || 300;
        const pixelSize = Math.round((field.font_size || 24) * dpi / 72);
        const anchorMap = { left: 'start', center: 'middle', right: 'end' };
        const isSelected = idx === FieldPanel.selectedIndex;
        const isEmpty = !displayText;

        if (!isEmpty) {
            const lines = (field.wrap && field.max_width > 0)
                ? this._wrapTextSVG(displayText, field, pixelSize)
                : [displayText];

            // Approximate line height from font size (matches PIL's ascent+descent).
            const multiplier = (field.line_height && field.line_height > 0) ? field.line_height : 1.0;
            const lineHeight = Math.round(pixelSize * 1.2 * multiplier);

            const text = document.createElementNS(NS, 'text');
            text.setAttribute('x', field.x);
            text.setAttribute('y', field.y);
            text.setAttribute('fill', field.font_color || '#000000');
            text.setAttribute('font-size', pixelSize);
            text.setAttribute('font-family', field.font_family || 'Arial');
            if (field.bold) text.setAttribute('font-weight', 'bold');
            if (field.italic) text.setAttribute('font-style', 'italic');
            text.setAttribute('text-anchor', anchorMap[field.alignment] || 'middle');
            // Use the em-box top (ascender line) as the y origin so the SVG
            // editor preview matches the PIL renderer's "a" anchor.
            text.setAttribute('dominant-baseline', 'text-before-edge');

            lines.forEach((line, i) => {
                const tspan = document.createElementNS(NS, 'tspan');
                tspan.setAttribute('x', field.x);
                tspan.setAttribute('dy', i === 0 ? 0 : lineHeight);
                tspan.textContent = line;
                text.appendChild(tspan);
            });
            g.appendChild(text);
        }

        // Selection highlight: dashed outline. If the field has no visible text
        // (e.g. an empty conditional field), draw a placeholder-sized rect so it
        // stays grabbable without polluting the rendered badge with fake text.
        if (isSelected) {
            g.classList.add('selected');
            const rect = document.createElementNS(NS, 'rect');
            rect.setAttribute('fill', 'none');
            rect.setAttribute('stroke', '#0078D4');
            rect.setAttribute('stroke-width', '2');
            rect.setAttribute('stroke-dasharray', '4,2');

            if (isEmpty) {
                // Placeholder rect — center-aligned around the field's anchor.
                const phWidth = Math.max(60, field.max_width || 100);
                const phHeight = pixelSize + 8;
                const align = field.alignment || 'center';
                let rx = field.x;
                if (align === 'center') rx = field.x - phWidth / 2;
                else if (align === 'right') rx = field.x - phWidth;
                rect.setAttribute('x', rx);
                rect.setAttribute('y', field.y - 2);
                rect.setAttribute('width', phWidth);
                rect.setAttribute('height', phHeight);
                rect.setAttribute('pointer-events', 'all');
                rect.style.cursor = 'move';
            } else {
                rect.setAttribute('x', field.x - 2);
                rect.setAttribute('y', field.y - 2);
                rect.setAttribute('width', 100);
                rect.setAttribute('height', pixelSize + 4);
                rect.setAttribute('pointer-events', 'none');

                requestAnimationFrame(() => {
                    try {
                        const textEl = g.querySelector('text');
                        const tb = textEl.getBBox();
                        rect.setAttribute('x', tb.x - 4);
                        rect.setAttribute('y', tb.y - 2);
                        rect.setAttribute('width', tb.width + 8);
                        rect.setAttribute('height', tb.height + 4);
                    } catch (e) {}
                });
            }
            g.appendChild(rect);
        }

        return g;
    },

    /**
     * Measure a string in SVG without a visible text element.
     */
    _measureText(str, fontSize, fontFamily, bold, italic) {
        if (!this._measureSvg) {
            const NS = 'http://www.w3.org/2000/svg';
            this._measureSvg = document.createElementNS(NS, 'svg');
            this._measureSvg.style.position = 'absolute';
            this._measureSvg.style.visibility = 'hidden';
            this._measureSvg.style.pointerEvents = 'none';
            this._measureText_el = document.createElementNS(NS, 'text');
            this._measureSvg.appendChild(this._measureText_el);
            document.body.appendChild(this._measureSvg);
        }
        const t = this._measureText_el;
        t.setAttribute('font-size', fontSize);
        t.setAttribute('font-family', fontFamily || 'Arial');
        t.setAttribute('font-weight', bold ? 'bold' : 'normal');
        t.setAttribute('font-style', italic ? 'italic' : 'normal');
        t.textContent = str;
        return t.getComputedTextLength();
    },

    /**
     * Greedy word-wrap to fit max_width (in badge pixels at full DPI). Returns
     * an array of line strings.
     */
    _wrapTextSVG(text, field, pixelSize) {
        const words = text.split(/\s+/).filter(Boolean);
        if (words.length === 0) return [text];
        const lines = [];
        let current = words[0];
        for (let i = 1; i < words.length; i++) {
            const candidate = current + ' ' + words[i];
            const w = this._measureText(candidate, pixelSize, field.font_family,
                                         field.bold, field.italic);
            if (w <= field.max_width) {
                current = candidate;
            } else {
                lines.push(current);
                current = words[i];
            }
        }
        lines.push(current);
        return lines;
    },

    // --- Drag and drop ---

    svgPoint(clientX, clientY) {
        const pt = this.svg.createSVGPoint();
        pt.x = clientX;
        pt.y = clientY;
        const ctm = this.svg.getScreenCTM().inverse();
        return pt.matrixTransform(ctm);
    },

    onPointerDown(e) {
        if (this.previewMode) return;
        const fieldGroup = e.target.closest('.svg-field-text');
        if (!fieldGroup) return;

        const idx = parseInt(fieldGroup.dataset.fieldIndex, 10);
        FieldPanel.select(idx);

        // Start drag
        this.dragging = fieldGroup;
        const pt = this.svgPoint(e.clientX, e.clientY);
        this.dragStartX = pt.x;
        this.dragStartY = pt.y;

        // Get current field position
        const textEl = fieldGroup.querySelector('text');
        this.fieldStartX = parseFloat(textEl.getAttribute('x'));
        this.fieldStartY = parseFloat(textEl.getAttribute('y'));

        fieldGroup.setPointerCapture(e.pointerId);
        e.preventDefault();
    },

    onPointerMove(e) {
        if (!this.dragging) return;
        const pt = this.svgPoint(e.clientX, e.clientY);
        const dx = pt.x - this.dragStartX;
        const dy = pt.y - this.dragStartY;

        const newX = Math.round(this.fieldStartX + dx);
        const newY = Math.round(this.fieldStartY + dy);

        const textEl = this.dragging.querySelector('text');
        textEl.setAttribute('x', newX);
        textEl.setAttribute('y', newY);

        // Update selection rect too
        const rect = this.dragging.querySelector('rect');
        if (rect) {
            requestAnimationFrame(() => {
                try {
                    const tb = textEl.getBBox();
                    rect.setAttribute('x', tb.x - 4);
                    rect.setAttribute('y', tb.y - 2);
                    rect.setAttribute('width', tb.width + 8);
                    rect.setAttribute('height', tb.height + 4);
                } catch (e) {}
            });
        }
    },

    async onPointerUp(e) {
        if (!this.dragging) return;
        const fieldGroup = this.dragging;
        this.dragging = null;

        const textEl = fieldGroup.querySelector('text');
        const newX = parseFloat(textEl.getAttribute('x'));
        const newY = parseFloat(textEl.getAttribute('y'));
        const idx = parseInt(fieldGroup.dataset.fieldIndex, 10);

        // Only update server if position actually changed
        if (newX !== this.fieldStartX || newY !== this.fieldStartY) {
            try {
                await API.updateField(idx, { x: newX, y: newY });
                FieldPanel.updatePropsFromServer(idx);
            } catch (e) {
                console.error('Failed to update field position:', e);
            }
        }
    },
};
