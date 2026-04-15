# ============================================================
# dashboard.py — Dashboard web (Flask) cu vizualizare semnale
# ============================================================

from flask import Flask, jsonify, render_template_string, request
import json
import os
import logging
from screener import run_screener
from backtester import backtest_ticker, backtest_all
from risk_manager import load_journal, get_journal_stats, add_trade, close_trade, calc_position
from config import CAPITAL, RISK_PER_TRADE

log = logging.getLogger(__name__)
app = Flask(__name__)

# ─── HTML DASHBOARD ────────────────────────────────────────
HTML = """
<!DOCTYPE html>
<html lang="ro">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Swing Trader Dashboard</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
<style>
  :root {
    --bg: #0a0e1a; --card: #111827; --border: #1f2937;
    --green: #10b981; --red: #ef4444; --yellow: #f59e0b;
    --blue: #3b82f6; --text: #e5e7eb; --muted: #6b7280;
  }
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { background: var(--bg); color: var(--text); font-family: 'Segoe UI', sans-serif; }
  header { background: var(--card); border-bottom: 1px solid var(--border);
           padding: 16px 24px; display: flex; align-items: center; gap: 12px; }
  header h1 { font-size: 1.4rem; color: var(--green); }
  header span { color: var(--muted); font-size: 0.85rem; }
  .tabs { display: flex; gap: 4px; padding: 16px 24px 0; }
  .tab { padding: 10px 20px; border-radius: 8px 8px 0 0; cursor: pointer;
         background: var(--card); border: 1px solid var(--border); color: var(--muted); }
  .tab.active { background: var(--blue); color: white; border-color: var(--blue); }
  .content { padding: 0 24px 24px; }
  .panel { display: none; padding-top: 20px; }
  .panel.active { display: block; }
  .grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap: 16px; margin-bottom: 24px; }
  .card { background: var(--card); border: 1px solid var(--border); border-radius: 12px; padding: 20px; }
  .card h3 { color: var(--muted); font-size: 0.8rem; text-transform: uppercase; margin-bottom: 8px; }
  .card .val { font-size: 1.8rem; font-weight: 700; }
  .green { color: var(--green); } .red { color: var(--red); } .yellow { color: var(--yellow); }
  table { width: 100%; border-collapse: collapse; background: var(--card);
          border-radius: 12px; overflow: hidden; }
  th { background: #1f2937; padding: 12px 16px; text-align: left;
       font-size: 0.8rem; color: var(--muted); text-transform: uppercase; }
  td { padding: 12px 16px; border-bottom: 1px solid var(--border); font-size: 0.9rem; }
  tr:last-child td { border-bottom: none; }
  tr:hover td { background: rgba(59,130,246,0.05); }
  .badge { padding: 3px 10px; border-radius: 999px; font-size: 0.75rem; font-weight: 600; }
  .badge.buy { background: rgba(16,185,129,0.15); color: var(--green); }
  .badge.sl  { background: rgba(239,68,68,0.15);  color: var(--red); }
  .badge.tp1 { background: rgba(245,158,11,0.15); color: var(--yellow); }
  .badge.tp2 { background: rgba(59,130,246,0.15); color: var(--blue); }
  .stars { color: var(--yellow); }
  btn, button { padding: 10px 20px; border-radius: 8px; border: none; cursor: pointer;
           background: var(--blue); color: white; font-size: 0.9rem; font-weight: 600; }
  button:hover { opacity: 0.85; }
  .btn-red { background: var(--red); }
  .btn-green { background: var(--green); }
  input, select { background: var(--card); border: 1px solid var(--border); color: var(--text);
                  padding: 10px 14px; border-radius: 8px; font-size: 0.9rem; width: 100%; }
  .form-row { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; margin-bottom: 12px; }
  .form-row label { display: block; color: var(--muted); font-size: 0.8rem; margin-bottom: 4px; }
  .loading { text-align: center; padding: 60px; color: var(--muted); }
  .spinner { width: 40px; height: 40px; border: 3px solid var(--border);
             border-top-color: var(--blue); border-radius: 50%; animation: spin 0.8s linear infinite;
             margin: 0 auto 16px; }
  @keyframes spin { to { transform: rotate(360deg); } }
  #equity-chart { max-height: 300px; }
</style>
</head>
<body>
<header>
  <div>📈</div>
  <h1>Swing Trader Dashboard</h1>
  <span id="last-update">Se încarcă...</span>
</header>

<div class="tabs">
  <div class="tab active" onclick="switchTab('screener')">🔍 Screener</div>
  <div class="tab" onclick="switchTab('backtest')">📊 Backtesting</div>
  <div class="tab" onclick="switchTab('journal')">📋 Jurnal</div>
  <div class="tab" onclick="switchTab('risk')">⚖️ Risc</div>
</div>

<div class="content">

  <!-- SCREENER -->
  <div id="panel-screener" class="panel active">
    <div class="grid" id="screener-stats"></div>
    <div style="margin-bottom:16px; display:flex; gap:12px; align-items:center">
      <button onclick="runScreener()">🔍 Rulează Screener Acum</button>
      <span id="screener-progress" style="color:var(--muted); font-size:0.85rem"></span>
    </div>
    <div id="screener-table"><div class="loading"><div class="spinner"></div>Apasă butonul pentru a rula screener-ul...</div></div>
  </div>

  <!-- BACKTESTING -->
  <div id="panel-backtest" class="panel">
    <div style="display:flex; gap:12px; margin-bottom:20px; align-items:flex-end">
      <div style="flex:1">
        <label style="color:var(--muted); font-size:0.8rem; display:block; margin-bottom:4px">Ticker pentru backtesting individual</label>
        <input id="bt-ticker" placeholder="ex: AAPL" style="max-width:200px">
      </div>
      <button onclick="runBacktest()">📊 Backtest Ticker</button>
      <button onclick="runBacktestAll()" style="background:var(--green)">🔄 Backtest Toate</button>
    </div>
    <div id="backtest-results"><div class="loading"><div class="spinner" style="display:none"></div>Introduce un ticker sau rulează backtesting complet...</div></div>
  </div>

  <!-- JURNAL -->
  <div id="panel-journal" class="panel">
    <div class="grid" id="journal-stats"></div>
    <div style="margin-bottom:16px">
      <button onclick="loadJournal()" style="background:var(--card); border:1px solid var(--border); color:var(--text)">🔄 Reîncarcă</button>
    </div>
    <div id="journal-table"></div>
  </div>

  <!-- RISC -->
  <div id="panel-risk" class="panel">
    <div style="max-width:600px">
      <div class="card" style="margin-bottom:20px">
        <h3 style="margin-bottom:16px; font-size:1rem; color:var(--text)">Calculator Poziție</h3>
        <div class="form-row">
          <div><label>Ticker</label><input id="r-ticker" placeholder="AAPL"></div>
          <div><label>Preț Intrare ($)</label><input id="r-entry" type="number" placeholder="100.00"></div>
        </div>
        <div class="form-row">
          <div><label>Stop Loss ($)</label><input id="r-sl" type="number" placeholder="95.00"></div>
          <div><label>Capital ($)</label><input id="r-capital" type="number" value="{{ capital }}"></div>
        </div>
        <button onclick="calcRisk()" style="margin-top:8px">⚖️ Calculează</button>
      </div>
      <div id="risk-result"></div>
    </div>
  </div>

</div>

<script>
function switchTab(name) {
  document.querySelectorAll('.tab').forEach((t,i) => {
    const tabs = ['screener','backtest','journal','risk'];
    t.classList.toggle('active', tabs[i] === name);
  });
  document.querySelectorAll('.panel').forEach(p => p.classList.remove('active'));
  document.getElementById('panel-' + name).classList.add('active');
  if (name === 'journal') loadJournal();
}

async function runScreener() {
  document.getElementById('screener-progress').textContent = '⏳ Scanare în curs (2-3 min)...';
  document.getElementById('screener-table').innerHTML = '<div class="loading"><div class="spinner"></div>Scanare ' + document.querySelectorAll('#screener-table').length + ' acțiuni...</div>';
  const r = await fetch('/api/screener');
  const data = await r.json();
  renderScreener(data);
  document.getElementById('screener-progress').textContent = `✅ ${data.signals.length} semnale găsite`;
  document.getElementById('last-update').textContent = 'Actualizat: ' + new Date().toLocaleTimeString('ro-RO');
}

function renderScreener(data) {
  // Stats
  const s = data.stats || {};
  document.getElementById('screener-stats').innerHTML = `
    <div class="card"><h3>Semnale găsite</h3><div class="val green">${data.signals.length}</div></div>
    <div class="card"><h3>Tickere scanate</h3><div class="val">${s.scanned || 0}</div></div>
    <div class="card"><h3>Rata de semnal</h3><div class="val yellow">${s.rate || 0}%</div></div>
    <div class="card"><h3>Data scanare</h3><div class="val" style="font-size:1.1rem">${s.date || '-'}</div></div>
  `;
  if (!data.signals.length) {
    document.getElementById('screener-table').innerHTML = '<div class="loading">Niciun semnal găsit astăzi. Piața nu oferă setup-uri valide.</div>';
    return;
  }
  const rows = data.signals.map(s => `
    <tr>
      <td><strong>${s.ticker}</strong></td>
      <td>$${s.price}</td>
      <td class="${s.rsi < 50 ? 'green' : 'yellow'}">${s.rsi}</td>
      <td>${s.dist_ema21}%</td>
      <td class="green">$${s.tp1}</td>
      <td class="blue">$${s.tp2}</td>
      <td class="red">$${s.sl}</td>
      <td>${s.shares} shares</td>
      <td><span class="stars">${'⭐'.repeat(s.score)}</span></td>
      <td><span class="badge buy">${s.candle_type}</span></td>
    </tr>`).join('');
  document.getElementById('screener-table').innerHTML = `
    <table>
      <thead><tr><th>Ticker</th><th>Preț</th><th>RSI</th><th>Dist EMA21</th><th>TP1</th><th>TP2</th><th>SL</th><th>Shares</th><th>Scor</th><th>Semnal</th></tr></thead>
      <tbody>${rows}</tbody>
    </table>`;
}

async function runBacktest() {
  const ticker = document.getElementById('bt-ticker').value.toUpperCase();
  if (!ticker) return alert('Introdu un ticker!');
  document.getElementById('backtest-results').innerHTML = '<div class="loading"><div class="spinner"></div>Backtesting ' + ticker + '...</div>';
  const r = await fetch('/api/backtest/' + ticker);
  const data = await r.json();
  renderBacktestSingle(data);
}

async function runBacktestAll() {
  document.getElementById('backtest-results').innerHTML = '<div class="loading"><div class="spinner"></div>Backtesting complet (poate dura 5-10 min)...</div>';
  const r = await fetch('/api/backtest-all');
  const data = await r.json();
  renderBacktestAll(data);
}

function renderBacktestSingle(d) {
  if (d.error || !d.trades) {
    document.getElementById('backtest-results').innerHTML = `<div class="loading">${d.message || d.error || 'Date insuficiente'}</div>`;
    return;
  }
  const pnlClass = d.total_pnl_$ >= 0 ? 'green' : 'red';
  const rows = (d.trade_list || []).slice(-20).map(t => `
    <tr>
      <td>${t.entry_date}</td><td>${t.exit_date}</td>
      <td>$${t.entry_price}</td><td>$${t.exit_price}</td>
      <td><span class="badge ${t.exit_type === 'SL' ? 'sl' : t.exit_type === 'TP1' ? 'tp1' : 'tp2'}">${t.exit_type}</span></td>
      <td class="${t.r > 0 ? 'green' : 'red'}">${t.r}R</td>
      <td class="${t.profit_$ >= 0 ? 'green' : 'red'}">$${t.profit_$}</td>
    </tr>`).join('');
  document.getElementById('backtest-results').innerHTML = `
    <div class="grid" style="margin-bottom:20px">
      <div class="card"><h3>Win Rate</h3><div class="val green">${d.win_rate}%</div></div>
      <div class="card"><h3>Total R</h3><div class="val ${pnlClass}">${d.total_r}R</div></div>
      <div class="card"><h3>P&L Total</h3><div class="val ${pnlClass}">$${d.total_pnl_$}</div></div>
      <div class="card"><h3>Profit Factor</h3><div class="val yellow">${d.profit_factor}</div></div>
      <div class="card"><h3>Max Drawdown</h3><div class="val red">${d.max_drawdown}%</div></div>
      <div class="card"><h3>Tranzacții</h3><div class="val">${d.trades}</div></div>
    </div>
    <h3 style="margin-bottom:12px; color:var(--muted)">Ultimele 20 Tranzacții</h3>
    <table><thead><tr><th>Intrare</th><th>Ieșire</th><th>Preț In</th><th>Preț Out</th><th>Tip</th><th>R</th><th>P&L</th></tr></thead>
    <tbody>${rows}</tbody></table>`;
}

function renderBacktestAll(data) {
  if (!data.top_performers) { document.getElementById('backtest-results').innerHTML = '<div class="loading">Eroare la backtesting complet.</div>'; return; }
  const rows = data.top_performers.slice(0,20).map((d,i) => `
    <tr>
      <td>${i+1}</td><td><strong>${d.ticker}</strong></td>
      <td>${d.win_rate}%</td><td>${d.trades}</td>
      <td class="${d.total_r >= 0 ? 'green' : 'red'}">${d.total_r}R</td>
      <td class="${d.total_pnl_$ >= 0 ? 'green' : 'red'}">$${d.total_pnl_$}</td>
      <td>${d.profit_factor}</td><td class="red">${d.max_drawdown}%</td>
    </tr>`).join('');
  document.getElementById('backtest-results').innerHTML = `
    <div class="grid" style="margin-bottom:20px">
      <div class="card"><h3>Tickere testate</h3><div class="val">${data.total_tickers_tested}</div></div>
      <div class="card"><h3>Win Rate global</h3><div class="val green">${data.aggregate_win_rate}%</div></div>
      <div class="card"><h3>Total R global</h3><div class="val green">${data.aggregate_total_r}R</div></div>
      <div class="card"><h3>P&L total</h3><div class="val green">$${data.aggregate_pnl_$}</div></div>
    </div>
    <h3 style="margin-bottom:12px; color:var(--muted)">Top 20 Performeri</h3>
    <table><thead><tr><th>#</th><th>Ticker</th><th>Win Rate</th><th>Trades</th><th>Total R</th><th>P&L</th><th>PF</th><th>Max DD</th></tr></thead>
    <tbody>${rows}</tbody></table>`;
}

async function loadJournal() {
  const r = await fetch('/api/journal');
  const data = await r.json();
  const stats = data.stats;
  document.getElementById('journal-stats').innerHTML = `
    <div class="card"><h3>Win Rate</h3><div class="val green">${stats.win_rate || 0}%</div></div>
    <div class="card"><h3>Total R</h3><div class="val ${(stats.total_r||0)>=0?'green':'red'}">${stats.total_r || 0}R</div></div>
    <div class="card"><h3>P&L Total</h3><div class="val ${(stats.total_pnl_$||0)>=0?'green':'red'}">$${stats.total_pnl_$ || 0}</div></div>
    <div class="card"><h3>Tranzacții deschise</h3><div class="val yellow">${stats.open_trades || 0}</div></div>
  `;
  const rows = data.journal.map(t => `
    <tr>
      <td>#${t.id}</td><td><strong>${t.ticker}</strong></td>
      <td><span class="badge ${t.status === 'OPEN' ? 'buy' : t.r > 0 ? 'tp2' : 'sl'}">${t.status}</span></td>
      <td>$${t.entry}</td><td class="red">$${t.sl}</td>
      <td class="yellow">$${t.tp1}</td><td class="green">$${t.tp2}</td>
      <td>${t.shares}</td>
      <td class="${(t.r||0)>0?'green':'red'}">${t.r != null ? t.r + 'R' : '-'}</td>
      <td class="${(t.pnl_$||0)>=0?'green':'red'}">${t.pnl_$ != null ? '$'+t.pnl_$ : '-'}</td>
      <td>${t.open_date}</td>
      ${t.status === 'OPEN' ? `<td><button class="btn-red" style="padding:6px 12px; font-size:0.8rem" onclick="closeTradePrompt(${t.id})">Închide</button></td>` : '<td></td>'}
    </tr>`).join('');
  document.getElementById('journal-table').innerHTML = `
    <table><thead><tr><th>#</th><th>Ticker</th><th>Status</th><th>Intrare</th><th>SL</th><th>TP1</th><th>TP2</th><th>Shares</th><th>R</th><th>P&L</th><th>Data</th><th>Acțiune</th></tr></thead>
    <tbody>${rows}</tbody></table>`;
}

async function closeTradePrompt(id) {
  const price = prompt('Preț de ieșire ($):');
  if (!price) return;
  await fetch('/api/journal/close', { method:'POST', headers:{'Content-Type':'application/json'},
    body: JSON.stringify({id, exit_price: parseFloat(price)}) });
  loadJournal();
}

async function calcRisk() {
  const payload = {
    ticker: document.getElementById('r-ticker').value,
    entry: parseFloat(document.getElementById('r-entry').value),
    sl: parseFloat(document.getElementById('r-sl').value),
    capital: parseFloat(document.getElementById('r-capital').value),
  };
  const r = await fetch('/api/risk', { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify(payload) });
  const d = await r.json();
  if (d.error) { document.getElementById('risk-result').innerHTML = `<div class="loading red">${d.error}</div>`; return; }
  document.getElementById('risk-result').innerHTML = `
    <div class="card">
      <h3 style="font-size:1rem; color:var(--text); margin-bottom:16px">Rezultat Calculator — ${payload.ticker || 'Ticker'}</h3>
      <div class="grid">
        <div><label style="color:var(--muted); font-size:0.8rem">Shares</label><div style="font-size:1.4rem; font-weight:700">${d.shares}</div></div>
        <div><label style="color:var(--muted); font-size:0.8rem">Valoare poziție</label><div style="font-size:1.4rem; font-weight:700">$${d.position_value}</div></div>
        <div><label style="color:var(--muted); font-size:0.8rem">Risc ($)</label><div style="font-size:1.4rem; font-weight:700; color:var(--red)">$${d.risk_amount_$}</div></div>
        <div><label style="color:var(--muted); font-size:0.8rem">% Capital</label><div style="font-size:1.4rem; font-weight:700">${d.pct_of_capital}%</div></div>
        <div><label style="color:var(--muted); font-size:0.8rem">TP1 (${d.rr_tp1}R)</label><div style="font-size:1.4rem; font-weight:700; color:var(--yellow)">$${d.tp1}</div></div>
        <div><label style="color:var(--muted); font-size:0.8rem">TP2 (${d.rr_tp2}R)</label><div style="font-size:1.4rem; font-weight:700; color:var(--green)">$${d.tp2}</div></div>
      </div>
      <div style="margin-top:16px">
        <button class="btn-green" onclick="addToJournal()">➕ Adaugă în Jurnal</button>
      </div>
    </div>`;
  window._lastRisk = {ticker: payload.ticker, entry: payload.entry, sl: d.sl, tp1: d.tp1, tp2: d.tp2, shares: d.shares};
}

async function addToJournal() {
  if (!window._lastRisk) return;
  await fetch('/api/journal/add', { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify(window._lastRisk) });
  alert('✅ Tranzacție adăugată în jurnal!');
}
</script>
</body>
</html>
"""

# ─── API ROUTES ─────────────────────────────────────────────

@app.route("/")
def index():
    return render_template_string(HTML, capital=CAPITAL)

@app.route("/api/screener")
def api_screener():
    signals = run_screener()
    return jsonify({
        "signals": signals,
        "stats": {
            "scanned": len(__import__('config').TICKERS),
            "found":   len(signals),
            "rate":    round(len(signals) / len(__import__('config').TICKERS) * 100, 1),
            "date":    __import__('datetime').datetime.now().strftime("%Y-%m-%d %H:%M"),
        }
    })

@app.route("/api/backtest/<ticker>")
def api_backtest(ticker):
    result = backtest_ticker(ticker.upper())
    return jsonify(result or {"error": "Date insuficiente", "trades": 0})

@app.route("/api/backtest-all")
def api_backtest_all():
    from config import TICKERS
    result = backtest_all(TICKERS)
    return jsonify(result)

@app.route("/api/journal")
def api_journal():
    journal = load_journal()
    stats   = get_journal_stats()
    return jsonify({"journal": journal, "stats": stats})

@app.route("/api/journal/add", methods=["POST"])
def api_journal_add():
    data = request.json
    trade = add_trade(
        ticker=data.get("ticker", ""),
        entry=data.get("entry", 0),
        sl=data.get("sl", 0),
        shares=data.get("shares", 0),
        tp1=data.get("tp1", 0),
        tp2=data.get("tp2", 0),
    )
    return jsonify(trade)

@app.route("/api/journal/close", methods=["POST"])
def api_journal_close():
    data  = request.json
    trade = close_trade(data["id"], data["exit_price"])
    return jsonify(trade or {"error": "Tranzacție negăsită"})

@app.route("/api/risk", methods=["POST"])
def api_risk():
    data   = request.json
    result = calc_position(
        entry=data.get("entry", 0),
        sl=data.get("sl", 0),
        capital=data.get("capital", CAPITAL),
    )
    return jsonify(result)


def run_dashboard(host: str = "0.0.0.0", port: int = 5000, debug: bool = False):
    log.info(f"🌐 Dashboard pornit la http://localhost:{port}")
    app.run(host=host, port=port, debug=debug)
