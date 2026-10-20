(() => {
  const storedTheme = () => {
    try { return localStorage.getItem("voiceguard.theme") === "dark" ? "dark" : "light"; }
    catch { return "light"; }
  };

  function applyTheme(theme) {
    const selected = theme === "dark" ? "dark" : "light";
    document.documentElement.dataset.theme = selected;
    try { localStorage.setItem("voiceguard.theme", selected); } catch {}
    const controls = document.querySelectorAll("#vg-theme-toggle, #vg-auth-theme-toggle");
    controls.forEach((button) => {
      const target = selected === "dark" ? "light" : "dark";
      const icon = target === "dark"
        ? '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M20.2 15.2A8.5 8.5 0 0 1 8.8 3.8 8.8 8.8 0 1 0 20.2 15.2Z"/></svg>'
        : '<svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="4"/><path d="M12 2v2m0 16v2M4.93 4.93l1.42 1.42m11.3 11.3 1.42 1.42M2 12h2m16 0h2M4.93 19.07l1.42-1.42m11.3-11.3 1.42-1.42"/></svg>';
      button.querySelector("svg")?.remove();
      button.insertAdjacentHTML("afterbegin", icon);
      const label = button.querySelector("[data-theme-label]");
      if (label) label.textContent = target === "dark" ? "Dark mode" : "Light mode";
      button.classList.add("vg-theme-icon-button");
      button.setAttribute("aria-label", `Switch to ${target} mode`);
      button.title = `Switch to ${target} mode`;
      button.setAttribute("aria-pressed", String(selected === "dark"));
    });
  }

  function initializeAuthPageTheme() {
    const button = document.querySelector("#vg-auth-theme-toggle");
    if (button) button.addEventListener("click", () => applyTheme(storedTheme() === "dark" ? "light" : "dark"));
    applyTheme(storedTheme());
  }

  function mountUserMenu() {
    const avatar = document.querySelector("header .flex.items-center.gap-6 > .rounded-full.bg-primary");
    if (!avatar || document.querySelector("#vg-user-menu")) return;
    const headerTools = avatar.parentElement;
    headerTools.style.position = "relative";
    avatar.id = "vg-user-trigger";
    avatar.tabIndex = 0;
    avatar.setAttribute("role", "button");
    avatar.setAttribute("aria-label", "Open user menu");
    avatar.setAttribute("aria-haspopup", "true");
    avatar.setAttribute("aria-expanded", "false");
    avatar.title = "User menu";

    const menu = document.createElement("section");
    menu.id = "vg-user-menu";
    menu.hidden = true;
    menu.setAttribute("aria-label", "User menu");
    menu.innerHTML = '<p class="vg-user-heading" id="vg-user-name">Guest</p><p class="vg-user-caption" id="vg-user-caption">Local account</p><a id="vg-auth-link" href="/login">Sign in or create account <span aria-hidden="true">→</span></a><div class="vg-menu-divider" role="separator"></div><button id="vg-theme-toggle" class="vg-theme-icon-button" type="button" aria-label="Switch to dark mode" title="Switch to dark mode" aria-pressed="false"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M20.2 15.2A8.5 8.5 0 0 1 8.8 3.8 8.8 8.8 0 1 0 20.2 15.2Z"/></svg><span data-theme-label>Dark mode</span></button><button id="vg-logout" type="button" hidden>Sign out</button>';
    headerTools.append(menu);

    const setOpen = (open) => {
      menu.hidden = !open;
      avatar.setAttribute("aria-expanded", String(open));
    };
    const toggle = () => setOpen(menu.hidden);
    avatar.addEventListener("click", toggle);
    avatar.addEventListener("keydown", (event) => {
      if (event.key === "Enter" || event.key === " ") { event.preventDefault(); toggle(); }
    });
    document.addEventListener("click", (event) => {
      if (!menu.contains(event.target) && !avatar.contains(event.target)) setOpen(false);
    });
    document.addEventListener("keydown", (event) => { if (event.key === "Escape") setOpen(false); });
    document.querySelector("#vg-theme-toggle").addEventListener("click", () => applyTheme(storedTheme() === "dark" ? "light" : "dark"));
    document.querySelector("#vg-logout").addEventListener("click", async () => {
      try {
        await fetch("/api/auth/logout", { method: "POST", headers: { "Content-Type": "application/json" }, body: "{}" });
      } finally { location.reload(); }
    });
    applyTheme(storedTheme());
    fetch("/api/auth/me").then((response) => response.ok ? response.json() : Promise.reject(new Error("Account status unavailable"))).then((payload) => {
      if (!payload.authenticated || !payload.user) return;
      document.querySelector("#vg-user-name").textContent = payload.user.display_name || payload.user.email || payload.user.username;
      document.querySelector("#vg-user-caption").textContent = "Signed in on this device";
      const link = document.querySelector("#vg-auth-link");
      link.textContent = "Account page";
      link.href = "/login";
      document.querySelector("#vg-logout").hidden = false;
      avatar.setAttribute("aria-label", `User menu for ${payload.user.display_name || payload.user.email || payload.user.username}`);
    }).catch(() => {});
  }

  initializeAuthPageTheme();
  mountUserMenu();
})();
