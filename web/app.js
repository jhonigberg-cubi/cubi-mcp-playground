const state = {
  lastPaymentId: "",
  lastRail: "WIRE",
};

async function api(path, options = {}) {
  const res = await fetch(path, {
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
    ...options,
  });
  const text = await res.text();
  const body = text ? JSON.parse(text) : {};
  if (!res.ok) {
    throw new Error(body.error || body.message || `Request failed ${res.status}`);
  }
  return body;
}

function byId(id) {
  return document.getElementById(id);
}

function pretty(value) {
  return JSON.stringify(value, null, 2);
}

async function copyText(text) {
  await navigator.clipboard.writeText(text);
}

function renderStatus(data) {
  const mock = data.mock || {};
  const running = !!mock.running && !!(mock.health && mock.health.status === "ok");
  const badge = byId("runtimeBadge");
  badge.textContent = running ? "healthy" : "offline";
  badge.className = `badge ${running ? "ok" : "neutral"}`;
  byId("healthBox").textContent = pretty(mock);
  byId("envBox").textContent = (data.env && data.env.dotenv) || "";
  byId("mcpBox").textContent = pretty(data.mcp_config || {});

  const select = byId("profileSelect");
  if (!select.options.length) {
    for (const profile of data.profiles || []) {
      const option = document.createElement("option");
      option.value = profile;
      option.textContent = profile;
      select.appendChild(option);
    }
  }
}

async function refresh() {
  const data = await api("/api/status");
  renderStatus(data);
}

async function ensureMock() {
  const data = await api("/api/mock/ensure", {
    method: "POST",
    body: JSON.stringify({
      bind_host: byId("bindHostInput").value.trim(),
      port: Number(byId("portInput").value || "8791"),
      profile: byId("profileSelect").value,
      reset: byId("resetCheckbox").checked,
    }),
  });
  renderStatus({
    mock: { running: true, health: data.health, process: { bind_host: byId("bindHostInput").value.trim(), port: Number(byId("portInput").value || "8791") } },
    env: data.env,
    mcp_config: data.mcp_config,
    profiles: ["default", "returns", "repair", "wire-heavy"],
  });
}

async function stopMock() {
  await api("/api/mock/stop", { method: "POST", body: "{}" });
  await refresh();
}

async function resetState() {
  await api("/api/mock/reset", {
    method: "POST",
    body: JSON.stringify({ profile: byId("profileSelect").value }),
  });
  await refresh();
}

async function loadAccounts() {
  const data = await api("/api/mock/accounts");
  const list = byId("accountsList");
  list.innerHTML = "";
  for (const acct of data.items || []) {
    const card = document.createElement("button");
    card.className = "account-card";
    card.innerHTML = `
      <strong>${acct.name}</strong>
      <span>${acct.id}</span>
      <span>****${String(acct.accountNumber).slice(-4)}</span>
      <span>${Number(acct.availableBalance).toLocaleString()} USD</span>
    `;
    card.addEventListener("click", async () => {
      const tx = await api(`/api/mock/transactions?account_id=${encodeURIComponent(acct.id)}&limit=6`);
      byId("paymentBox").textContent = pretty(tx);
    });
    list.appendChild(card);
  }
}

async function createPayment() {
  const data = await api("/api/mock/payments", {
    method: "POST",
    body: JSON.stringify({
      rail: byId("railInput").value,
      direction: byId("directionInput").value,
      amount: byId("amountInput").value.trim(),
      source_payment_id: byId("sourceIdInput").value.trim(),
      client_reference: byId("clientRefInput").value.trim(),
      beneficiary_bank_routing: byId("routingInput").value.trim(),
    }),
  });
  state.lastPaymentId = data.paymentId;
  state.lastRail = byId("railInput").value;
  byId("paymentBox").textContent = pretty(data);
}

async function pollPayment() {
  if (!state.lastPaymentId) {
    byId("paymentBox").textContent = "Create a payment first.";
    return;
  }
  const data = await api("/api/mock/payments/poll", {
    method: "POST",
    body: JSON.stringify({ payment_id: state.lastPaymentId, rail: state.lastRail }),
  });
  byId("paymentBox").textContent = pretty(data);
}

function wire() {
  byId("refreshBtn").addEventListener("click", refresh);
  byId("startBtn").addEventListener("click", ensureMock);
  byId("stopBtn").addEventListener("click", stopMock);
  byId("resetBtn").addEventListener("click", resetState);
  byId("loadAccountsBtn").addEventListener("click", loadAccounts);
  byId("createPaymentBtn").addEventListener("click", createPayment);
  byId("pollPaymentBtn").addEventListener("click", pollPayment);
  byId("copyEnvBtn").addEventListener("click", async () => copyText(byId("envBox").textContent));
  byId("copyMcpBtn").addEventListener("click", async () => copyText(byId("mcpBox").textContent));
}

wire();
refresh().catch((err) => {
  byId("healthBox").textContent = err.message;
});
