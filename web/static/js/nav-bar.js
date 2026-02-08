/**
 * Row navigation and search.
 */
const NavBar = {
    currentRow: 0,
    totalRows: 0,
    searchResults: [],
    searchIndex: -1,

    init() {
        document.getElementById('btn-prev').addEventListener('click', () => this.prev());
        document.getElementById('btn-next').addEventListener('click', () => this.next());
        document.getElementById('btn-search').addEventListener('click', () => this.search());
        document.getElementById('btn-search-prev').addEventListener('click', () => this.searchPrev());
        document.getElementById('btn-search-next').addEventListener('click', () => this.searchNext());

        document.getElementById('search-input').addEventListener('keydown', (e) => {
            if (e.key === 'Enter') {
                e.preventDefault();
                this.search();
            }
        });
    },

    update(row, total) {
        this.currentRow = row;
        this.totalRows = total;
        this.render();
    },

    render() {
        const indicator = document.getElementById('row-indicator');
        if (this.totalRows === 0) {
            indicator.textContent = 'No rows';
        } else {
            indicator.textContent = `Row ${this.currentRow + 1} of ${this.totalRows}`;
        }

        document.getElementById('btn-prev').disabled = this.currentRow <= 0;
        document.getElementById('btn-next').disabled = this.currentRow >= this.totalRows - 1;
    },

    async goTo(idx) {
        if (idx < 0 || idx >= this.totalRows) return;
        this.currentRow = idx;
        this.render();
        await App.onRowChanged(idx);
    },

    prev() {
        if (this.currentRow > 0) this.goTo(this.currentRow - 1);
    },

    next() {
        if (this.currentRow < this.totalRows - 1) this.goTo(this.currentRow + 1);
    },

    async search() {
        const q = document.getElementById('search-input').value.trim();
        if (!q) return;

        try {
            const data = await API.searchCSV(q);
            this.searchResults = data.results || [];
            this.searchIndex = -1;

            if (this.searchResults.length === 0) {
                Toast.info('No matches found');
                document.getElementById('btn-search-prev').disabled = true;
                document.getElementById('btn-search-next').disabled = true;
            } else {
                Toast.info(`Found ${this.searchResults.length} match(es)`);
                document.getElementById('btn-search-prev').disabled = false;
                document.getElementById('btn-search-next').disabled = false;
                // Go to first match
                this.searchNext();
            }
        } catch (e) {
            Toast.error('Search failed');
        }
    },

    searchNext() {
        if (this.searchResults.length === 0) return;
        this.searchIndex = (this.searchIndex + 1) % this.searchResults.length;
        const match = this.searchResults[this.searchIndex];
        this.goTo(match.index);
    },

    searchPrev() {
        if (this.searchResults.length === 0) return;
        this.searchIndex = (this.searchIndex - 1 + this.searchResults.length) % this.searchResults.length;
        const match = this.searchResults[this.searchIndex];
        this.goTo(match.index);
    },
};
