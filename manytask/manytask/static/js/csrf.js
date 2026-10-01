(function () {
    function csrfToken() {
        const meta = document.querySelector('meta[name="csrf-token"]');
        return meta ? meta.content : '';
    }

    // Merges the CSRF header into the headers of a state changing fetch().
    window.csrfHeaders = function (headers) {
        return Object.assign({}, headers || {}, {'X-CSRFToken': csrfToken()});
    };
})();
