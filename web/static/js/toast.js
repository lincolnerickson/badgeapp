/**
 * Escape HTML special characters to prevent XSS.
 */
function escapeHTML(str) {
    return String(str)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#39;');
}

/**
 * Toast notification system.
 */
const Toast = {
    container: null,

    init() {
        this.container = document.getElementById('toast-container');
    },

    /**
     * Show a toast message.
     * @param {string} message
     * @param {'info'|'success'|'error'} type
     * @param {number} duration - ms before auto-dismiss
     */
    show(message, type = 'info', duration = 3000) {
        if (!this.container) this.init();
        const el = document.createElement('div');
        el.className = `toast ${type}`;
        el.textContent = message;
        this.container.appendChild(el);

        setTimeout(() => {
            el.classList.add('fade-out');
            el.addEventListener('animationend', () => el.remove());
        }, duration);
    },

    info(msg)    { this.show(msg, 'info'); },
    success(msg) { this.show(msg, 'success'); },
    error(msg)   { this.show(msg, 'error', 5000); },
};
