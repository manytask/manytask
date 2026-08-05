/*
 * Reusable "search users and pick one" widget.
 *
 * Wires a text input to the shared `GET /api/users/search` endpoint, renders a
 * dropdown of matching users and, on selection, stores the chosen user's rms_id
 * into a hidden input and shows a "selected user" summary card.
 *
 * It is used by both the namespace panel and the instance admin panel when
 * assigning a user a role in a namespace, so the two stay in sync.
 *
 * Usage:
 *   const widget = initUserSearch({
 *       searchInputId: "userSearch",
 *       resultsId: "userSearchResults",
 *       hiddenInputId: "userRmsId",
 *       selectedContainerId: "selectedUserContainer",
 *       selectedNameId: "selectedUserName",
 *       selectedUsernameId: "selectedUserUsername",
 *       selectedRmsId: "selectedUserRmsId",
 *       clearButtonId: "clearSelectedUser",
 *       modalId: "addUserModal",          // optional
 *       resetElementIds: ["addUserError"] // optional extra elements to hide on modal close
 *   });
 *   // later, e.g. after a successful submit:
 *   widget.clearSelected();
 */
function initUserSearch(options) {
    const {
        searchInputId,
        resultsId,
        hiddenInputId,
        selectedContainerId,
        selectedNameId,
        selectedUsernameId,
        selectedRmsId,
        clearButtonId,
        modalId = null,
        resetFormId = null,
        resetElementIds = [],
        endpoint = "/api/users/search",
        debounceMs = 250,
    } = options;

    const searchInput = document.getElementById(searchInputId);
    const resultsDiv = document.getElementById(resultsId);
    const hiddenInput = document.getElementById(hiddenInputId);
    const selectedContainer = document.getElementById(selectedContainerId);
    const selectedName = document.getElementById(selectedNameId);
    const selectedUsername = document.getElementById(selectedUsernameId);
    const selectedRms = document.getElementById(selectedRmsId);
    const clearButton = document.getElementById(clearButtonId);

    if (!searchInput || !resultsDiv) {
        return { clearSelected: function () {} };
    }

    let debounceTimeout = null;

    function hideResults() {
        resultsDiv.classList.add("d-none");
        resultsDiv.innerHTML = "";
    }

    function renderResults(users) {
        resultsDiv.innerHTML = "";

        if (!users || users.length === 0) {
            const empty = document.createElement("div");
            empty.className = "list-group-item text-muted";
            empty.textContent = "No users found";
            resultsDiv.appendChild(empty);
            resultsDiv.classList.remove("d-none");
            return;
        }

        users.forEach((user) => {
            const item = document.createElement("button");
            item.type = "button";
            item.className = "list-group-item list-group-item-action";
            const fullName = `${user.first_name} ${user.last_name}`.trim();
            item.innerHTML = `
                <div class="d-flex justify-content-between align-items-center">
                    <span><strong>${fullName || user.username}</strong>
                        <span class="text-muted">@${user.username}</span></span>
                    <span class="badge bg-secondary">ID: ${user.rms_id}</span>
                </div>`;
            item.addEventListener("click", () => selectUser(user));
            resultsDiv.appendChild(item);
        });
        resultsDiv.classList.remove("d-none");
    }

    function selectUser(user) {
        if (hiddenInput) {
            hiddenInput.value = user.rms_id;
        }
        const fullName = `${user.first_name} ${user.last_name}`.trim();
        if (selectedName) {
            selectedName.textContent = fullName || user.username;
        }
        if (selectedUsername) {
            selectedUsername.textContent = "@" + user.username;
        }
        if (selectedRms) {
            selectedRms.textContent = user.rms_id;
        }
        if (selectedContainer) {
            selectedContainer.classList.remove("d-none");
        }

        searchInput.value = "";
        hideResults();
    }

    function clearSelected() {
        if (hiddenInput) {
            hiddenInput.value = "";
        }
        if (selectedContainer) {
            selectedContainer.classList.add("d-none");
        }
    }

    async function performSearch(query) {
        if (!query || query.trim().length === 0) {
            hideResults();
            return;
        }

        try {
            const response = await fetch(`${endpoint}?q=${encodeURIComponent(query.trim())}`);
            if (!response.ok) {
                hideResults();
                return;
            }
            const data = await response.json();
            renderResults(data.users || []);
        } catch (error) {
            hideResults();
        }
    }

    searchInput.addEventListener("input", function () {
        const query = this.value;
        if (debounceTimeout) {
            clearTimeout(debounceTimeout);
        }
        debounceTimeout = setTimeout(() => performSearch(query), debounceMs);
    });

    if (clearButton) {
        clearButton.addEventListener("click", clearSelected);
    }

    // Hide the results dropdown when clicking outside of it.
    document.addEventListener("click", function (event) {
        if (!resultsDiv.contains(event.target) && event.target !== searchInput) {
            resultsDiv.classList.add("d-none");
        }
    });

    // Reset widget state whenever the containing modal is closed.
    if (modalId) {
        const modal = document.getElementById(modalId);
        if (modal) {
            modal.addEventListener("hidden.bs.modal", function () {
                if (resetFormId) {
                    const form = document.getElementById(resetFormId);
                    if (form) {
                        form.reset();
                    }
                }
                clearSelected();
                hideResults();
                resetElementIds.forEach((id) => {
                    const el = document.getElementById(id);
                    if (el) {
                        el.classList.add("d-none");
                    }
                });
            });
        }
    }

    return { clearSelected };
}
