(() => {
  const form = document.querySelector("#vg-auth-form");
  if (!form) return;

  let mode = "login";
  const title = document.querySelector("#vg-auth-title");
  const description = document.querySelector("#vg-auth-description");
  const identity = document.querySelector("#vg-auth-identity");
  const identityLabel = document.querySelector("#vg-auth-identity-label");
  const displayRow = document.querySelector("#vg-auth-display-row");
  const displayName = document.querySelector("#vg-auth-display-name");
  const password = document.querySelector("#vg-auth-password");
  const submit = document.querySelector("#vg-auth-submit");
  const message = document.querySelector("#vg-auth-message");
  const switchButton = document.querySelector("#vg-auth-switch");
  const account = document.querySelector("#vg-auth-account");
  const accountMessage = document.querySelector("#vg-account-message");

  function setMode(next) {
    mode = next;
    const signup = mode === "signup";
    title.textContent = signup ? "Create account" : "Sign in";
    description.textContent = signup
      ? "Create an account to keep your analyses and settings private to you."
      : "Use your email address or username and password.";
    identityLabel.firstChild.textContent = signup ? "Email address" : "Email or username";
    identity.type = signup ? "email" : "text";
    identity.autocomplete = signup ? "email" : "username";
    identity.maxLength = signup ? 320 : 320;
    identity.minLength = signup ? 5 : 3;
    displayRow.hidden = !signup;
    displayName.required = false;
    submit.textContent = signup ? "Create account" : "Sign in";
    switchButton.textContent = signup ? "Sign in instead" : "Create an account";
    document.querySelector("#vg-auth-switch-prompt").textContent = signup ? "Already registered?" : "New here?";
    password.autocomplete = signup ? "new-password" : "current-password";
    message.textContent = "";
  }

  function destinationAfterAuth() {
    const next = new URLSearchParams(location.search).get("next");
    if (!next || !next.startsWith("/") || next.startsWith("//")) return "/dashboard";
    const target = new URL(next, location.origin);
    if (target.origin !== location.origin || target.pathname === "/login") return "/dashboard";
    return `${target.pathname}${target.search}${target.hash}`;
  }

  async function postJson(path, payload) {
    const response = await fetch(path, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const result = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(result.detail || `Request failed (${response.status})`);
    return result;
  }

  function showAccount(user) {
    form.hidden = true;
    document.querySelector(".vg-auth-switch-row").hidden = true;
    account.hidden = false;
    document.querySelector(".vg-auth-back").hidden = false;
    title.textContent = "Your account";
    description.textContent = "Manage your VoiceGuard account and its stored data.";
    document.querySelector("#vg-account-identity").textContent = user.display_name
      ? `${user.display_name} · ${user.email || user.username}`
      : (user.email || user.username);
    message.textContent = "";
  }

  switchButton.addEventListener("click", () => setMode(mode === "login" ? "signup" : "login"));
  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    if (!form.reportValidity()) return;
    submit.disabled = true;
    message.textContent = "";
    try {
      const value = identity.value.trim();
      let payload;
      if (mode === "signup") {
        payload = { email: value, display_name: displayName.value.trim() || null, password: password.value };
      } else {
        payload = value.includes("@")
          ? { email: value, password: password.value }
          : { username: value, password: password.value };
      }
      await postJson(mode === "signup" ? "/api/auth/signup" : "/api/auth/login", payload);
      password.value = "";
      location.assign(destinationAfterAuth());
    } catch (error) {
      message.textContent = error.message || "Unable to sign in. Check the server connection.";
    } finally {
      submit.disabled = false;
    }
  });

  document.querySelector("#vg-change-password-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    const passwordForm = event.currentTarget;
    if (!passwordForm.reportValidity()) return;
    accountMessage.textContent = "";
    const values = new FormData(passwordForm);
    try {
      const response = await fetch("/api/auth/change-password", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ current_password: values.get("current_password"), new_password: values.get("new_password") }),
      });
      const result = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(result.detail || `Request failed (${response.status})`);
      passwordForm.reset();
      accountMessage.textContent = "Password updated. Other signed-in sessions have been revoked.";
    } catch (error) {
      accountMessage.textContent = error.message || "Could not update the password.";
    }
  });

  document.querySelector("#vg-account-export").addEventListener("click", async () => {
    accountMessage.textContent = "";
    try {
      const response = await fetch("/api/account/export");
      const result = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(result.detail || `Request failed (${response.status})`);
      const blob = new Blob([JSON.stringify(result, null, 2)], { type: "application/json" });
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = `voiceguard-account-export-${new Date().toISOString().slice(0, 10)}.json`;
      link.click();
      URL.revokeObjectURL(url);
      accountMessage.textContent = "Your account data export was downloaded.";
    } catch (error) {
      accountMessage.textContent = error.message || "Could not export account data.";
    }
  });

  document.querySelector("#vg-account-delete").addEventListener("click", async () => {
    if (!window.confirm("Permanently delete this account and all analyses and settings owned by it? This cannot be undone.")) return;
    const confirmationPassword = document.querySelector("#vg-account-delete-password");
    if (!confirmationPassword.value) {
      accountMessage.textContent = "Enter your password to confirm account deletion.";
      confirmationPassword.focus();
      return;
    }
    accountMessage.textContent = "";
    try {
      const response = await fetch("/api/account", {
        method: "DELETE",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ password: confirmationPassword.value }),
      });
      const result = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(result.detail || `Request failed (${response.status})`);
      confirmationPassword.value = "";
      location.assign("/login");
    } catch (error) {
      accountMessage.textContent = error.message || "Could not delete the account.";
    }
  });

  document.querySelector("#vg-account-signout").addEventListener("click", async () => {
    try {
      await postJson("/api/auth/logout", {});
      location.assign("/login");
    } catch (error) {
      accountMessage.textContent = error.message || "Could not sign out.";
    }
  });

  fetch("/api/auth/me").then((response) => response.ok ? response.json() : Promise.reject())
    .then((result) => { if (result.authenticated && result.user) showAccount(result.user); })
    .catch(() => {});
})();
