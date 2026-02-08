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
        this.previewImg.src = API.getPreviewURL(App.currentRow);
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

        // Rebuild SVG text elements
        this.fieldsGroup.innerHTML = '';
        fields.forEach((field, idx) => {
            const text = rowData[field.csv_column] || field.csv_column;
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

        const text = document.createElementNS(NS, 'text');
        text.setAttribute('x', field.x);
        text.setAttribute('y', field.y);
        text.setAttribute('fill', field.font_color || '#000000');
        text.setAttribute('font-size', field.font_size || 24);
        text.setAttribute('font-family', field.font_family || 'Arial');

        if (field.bold) text.setAttribute('font-weight', 'bold');
        if (field.italic) text.setAttribute('font-style', 'italic');

        // Alignment -> text-anchor
        const anchorMap = { left: 'start', center: 'middle', right: 'end' };
        text.setAttribute('text-anchor', anchorMap[field.alignment] || 'middle');
        text.setAttribute('dominant-baseline', 'hanging');

        text.textContent = displayText;
        g.appendChild(text);

        // Selection highlight
        if (idx === FieldPanel.selectedIndex) {
            g.classList.add('selected');
            // Draw selection box
            const bbox = { x: field.x - 2, y: field.y - 2, width: 100, height: field.font_size + 4 };
            const rect = document.createElementNS(NS, 'rect');
            rect.setAttribute('x', bbox.x);
            rect.setAttribute('y', bbox.y);
            rect.setAttribute('width', bbox.width);
            rect.setAttribute('height', bbox.height);
            rect.setAttribute('fill', 'none');
            rect.setAttribute('stroke', '#0078D4');
            rect.setAttribute('stroke-width', '2');
            rect.setAttribute('stroke-dasharray', '4,2');
            rect.setAttribute('pointer-events', 'none');
            g.appendChild(rect);

            // Fix rect size after text renders
            requestAnimationFrame(() => {
                try {
                    const tb = text.getBBox();
                    rect.setAttribute('x', tb.x - 4);
                    rect.setAttribute('y', tb.y - 2);
                    rect.setAttribute('width', tb.width + 8);
                    rect.setAttribute('height', tb.height + 4);
                } catch (e) {}
            });
        }

        return g;
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
