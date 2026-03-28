/**
 * Generic autocomplete setup function
 * @param {string} targetSelector - CSS selector for the target input/textarea
 * @param {function} fetcher - async function(query) => Promise<string[]>
 */
function setupAutocomplete(targetSelector, fetcher) {
  const input = document.querySelector(targetSelector);
  if (!input) return;

  // Create dropdown container
  const dropdown = document.createElement("ul");
  dropdown.style.position = "absolute";
  dropdown.style.background = "#2b2b2b";
  dropdown.style.color = "#fff";
  dropdown.style.border = "1px solid #555";
  dropdown.style.listStyle = "none";
  dropdown.style.padding = "0";
  dropdown.style.margin = "0";
  dropdown.style.maxHeight = "150px";
  dropdown.style.overflowY = "auto";
  dropdown.style.zIndex = "1000";
  dropdown.hidden = true;

  // Ensure parent is positioned for absolute dropdown
  input.parentNode.style.position = "relative";
  input.parentNode.appendChild(dropdown);

  const MIN_DROPDOWN_WIDTH = 220;
  const syncDropdownWidth = () => {
    const width = input.getBoundingClientRect().width || input.offsetWidth || MIN_DROPDOWN_WIDTH;
    dropdown.style.minWidth = `${Math.max(width, MIN_DROPDOWN_WIDTH)}px`;
  };
  syncDropdownWidth();
  input.addEventListener("focus", syncDropdownWidth);
  window.addEventListener("resize", syncDropdownWidth);

  let timer = null;
  let selectedIndex = -1;

  // Update dropdown suggestions
  async function updateSuggestions(query) {
    try {
      const results = await fetcher(query);
      dropdown.innerHTML = "";
      selectedIndex = -1;

      if (!results || results.length === 0) {
        dropdown.hidden = true;
        return;
      }

      results.forEach((name, idx) => {
        const li = document.createElement("li");
        li.textContent = name;
        li.style.padding = "4px";
        li.style.cursor = "pointer";

        // Mouse click selection
        li.addEventListener("mousedown", () => {
          input.value = name;
          dropdown.hidden = true;
        });

        dropdown.appendChild(li);
      });

      dropdown.hidden = false;
    } catch (err) {
      console.error("Autocomplete fetch error", err);
    }
  }

  // Input event: fetch suggestions after debounce
  input.addEventListener("input", () => {
    clearTimeout(timer);
    const query = input.value.trim();
    if (!query) {
      dropdown.hidden = true;
      return;
    }
    timer = setTimeout(() => updateSuggestions(query), 300);
  });

  // Keyboard navigation
  input.addEventListener("keydown", (e) => {
    const items = dropdown.querySelectorAll("li");
    if (dropdown.hidden || items.length === 0) return;

    if (e.key === "Tab") {
      // Tab moves down one item
      e.preventDefault();
      selectedIndex = (selectedIndex + 1) % items.length;
      items.forEach((li, idx) => {
        li.style.background = idx === selectedIndex ? "#3a5080" : "#2b2b2b";
      });
      items[selectedIndex].scrollIntoView({ block: "nearest" });

    } else if (e.key === "Enter" || e.key === " ") {
      // Enter or Space applies the selected suggestion
      if (selectedIndex >= 0 && selectedIndex < items.length) {
        e.preventDefault();
        input.value = items[selectedIndex].textContent;
        dropdown.hidden = true;
      }

    } else if (e.key === "ArrowDown") {
      // Move selection down
      e.preventDefault();
      selectedIndex = (selectedIndex + 1) % items.length;
      items.forEach((li, idx) => {
        li.style.background = idx === selectedIndex ? "#3a5080" : "#2b2b2b";
      });
      items[selectedIndex].scrollIntoView({ block: "nearest" });

    } else if (e.key === "ArrowUp") {
      // Move selection up
      e.preventDefault();
      selectedIndex = (selectedIndex - 1 + items.length) % items.length;
      items.forEach((li, idx) => {
        li.style.background = idx === selectedIndex ? "#3a5080" : "#2b2b2b";
      });
      items[selectedIndex].scrollIntoView({ block: "nearest" });

    } else if (e.key === "ArrowLeft") {
      // Jump to the first suggestion
      e.preventDefault();
      selectedIndex = 0;
      items.forEach((li, idx) => {
        li.style.background = idx === selectedIndex ? "#3a5080" : "#2b2b2b";
      });
      items[selectedIndex].scrollIntoView({ block: "nearest" });

    } else if (e.key === "ArrowRight") {
      // Jump to the last suggestion
      e.preventDefault();
      selectedIndex = items.length - 1;
      items.forEach((li, idx) => {
        li.style.background = idx === selectedIndex ? "#3a5080" : "#2b2b2b";
      });
      items[selectedIndex].scrollIntoView({ block: "nearest" });
    }
  });

  // Hide dropdown when input loses focus
  input.addEventListener("blur", () => {
    setTimeout(() => dropdown.hidden = true, 200);
  });
}

/**
 * Fetcher for Civitai API (model names)
 */
async function civitaiFetcher(query) {
  if (!query) return [];
  const res = await fetch(`/civitai_suggest?q=${encodeURIComponent(query)}`);
  const data = await res.json();
  return data.results || [];
}

/**
 * Fetcher for Civitai API (tags)
 */
async function civitaiTagFetcher(query) {
  if (!query) return [];
  const res = await fetch(`/civitai_tag_suggest?q=${encodeURIComponent(query)}`);
  const data = await res.json();
  return data.results || [];
}

// Initialize on WebUI load
onUiLoaded(() => {
  // Query欄: textareaまたはinput両方に対応
  setupAutocomplete("#ch_browser_query textarea", civitaiFetcher);
  setupAutocomplete("#ch_browser_query input", civitaiFetcher);

  // Tag欄: textareaまたはinput両方に対応
  setupAutocomplete("#ch_browser_tag textarea", civitaiTagFetcher);
  setupAutocomplete("#ch_browser_tag input", civitaiTagFetcher);
});