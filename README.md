# GoldSignal AI — Valetax MT5 read-only starter

This is a local-first starter project. It does **not** connect to Valetax's undocumented/private API.
Instead, a read-only MT5 Expert Advisor sends XAUUSD candles from your logged-in Valetax MT5 terminal to a small FastAPI backend. The browser dashboard reads the backend.

## Safety / limitations
- No broker password, trading account login, or trading API secret is required by this bridge.
- The EA contains no order placement, modification, or closing functions.
- Signals are rule-based technical-analysis examples, not predictions or guaranteed profitable advice.
- Run on a **demo account first**. Do not use signals as sole basis for live trades.
- Keep the backend private. Use HTTPS and a strong random `API_KEY` before exposing it beyond localhost.
- The EA sends completed candles only. Signal calculations need enough history and show WAIT when data is stale or insufficient.
- Broker symbol names can vary (e.g. `XAUUSD`, `XAUUSD.`, `GOLD`). Set `InpSymbol` to the exact Market Watch symbol.

## 1) Start backend
Python 3.10+ recommended.

```bash
cd backend
python -m venv .venv
# Windows:
.venv\Scripts\activate
# macOS/Linux:
source .venv/bin/activate
pip install -r requirements.txt
```

Set a strong key (same key goes into the EA):
```bash
# Windows PowerShell
$env:GOLDSIGNAL_API_KEY="replace-with-a-long-random-secret"
# macOS/Linux
export GOLDSIGNAL_API_KEY="replace-with-a-long-random-secret"
```

Start:
```bash
uvicorn app:app --host 127.0.0.1 --port 8787
```
Open http://127.0.0.1:8787

## 2) Install MT5 Expert Advisor
1. In MT5 choose File → Open Data Folder.
2. Copy `mt5/Experts/GoldSignalBridge.mq5` into `MQL5/Experts/`.
3. Open MetaEditor, compile the EA, then attach it to an XAUUSD chart.
4. In EA inputs, set `InpApiKey` to the same key used by the backend.
5. In MT5: Tools → Options → Expert Advisors → enable **Allow WebRequest for listed URL** and add exactly:
   `http://127.0.0.1:8787`
6. Leave Algo Trading disabled if you want; this EA only reads candles and sends HTTP data.
7. Check the Experts tab for upload status.

The backend and MT5 terminal must run on the same computer for the default localhost URL. If hosted elsewhere, use a secured HTTPS endpoint, never expose an unauthenticated HTTP server to the internet.

## 3) Open dashboard
Visit http://127.0.0.1:8787. It shows the last received candle data and a rule-based BUY/SELL/WAIT assessment.

## Signal logic (starter)
- D1 trend: EMA 50 vs EMA 200.
- H4 trend: EMA 50 vs EMA 200.
- H1 confirmation: EMA 20/50 plus RSI(14) and MACD histogram direction.
- Entry reference: latest completed H1 close.
- Stop distance: 1.5 × H4 ATR(14), with target levels at 1R, 2R, 3R.
- Risk sizing: uses user-entered account balance, risk %, and symbol contract-size/tick-value inputs. Confirm contract specs with Valetax before relying on lot calculations.
- WAIT if candles are stale, history is insufficient, timeframes conflict, or reward/risk conditions are not met.

This is a prototype, not a validated trading system. Backtest and forward-test on demo data before use.
"# MT5--signal-gold" 
