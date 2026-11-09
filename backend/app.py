import os, json, time, math
from pathlib import Path
from typing import Dict, Any
from fastapi import FastAPI, Header, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

API_KEY = os.getenv("GOLDSIGNAL_API_KEY", "local-demo-change-me")
DATA: Dict[str, Any] = {}
app = FastAPI(title="GoldSignal AI", version="0.1.0")
FRONTEND = Path(__file__).resolve().parents[1] / "frontend"

def ema(values, period):
    if len(values) < period: return None
    k = 2.0 / (period + 1)
    out = sum(values[:period]) / period
    for v in values[period:]:
        out = v * k + out * (1-k)
    return out

def rsi(values, period=14):
    if len(values) <= period: return None
    gains, losses = [], []
    for a,b in zip(values[-period-1:-1], values[-period:]):
        d=b-a; gains.append(max(d,0)); losses.append(max(-d,0))
    ag=sum(gains)/period; al=sum(losses)/period
    if al == 0: return 100.0
    return 100 - 100/(1+ag/al)

def atr(candles, period=14):
    if len(candles) <= period: return None
    trs=[]
    for i in range(1, len(candles)):
        c, p = candles[i], candles[i-1]
        trs.append(max(c["high"]-c["low"], abs(c["high"]-p["close"]), abs(c["low"]-p["close"])))
    return sum(trs[-period:])/period if len(trs)>=period else None

def macd_hist(values):
    if len(values) < 35: return None
    # EMA arrays for standard MACD 12/26, signal 9
    def series(period):
        k=2/(period+1); out=[None]*(period-1)
        cur=sum(values[:period])/period; out.append(cur)
        for v in values[period:]:
            cur=v*k+cur*(1-k); out.append(cur)
        return out
    e12,e26=series(12),series(26)
    mac=[(a-b) for a,b in zip(e12,e26) if a is not None and b is not None]
    if len(mac)<9: return None
    sig=ema(mac,9)
    return mac[-1]-sig if sig is not None else None

def trend(candles, fast=50, slow=200):
    closes=[x["close"] for x in candles]
    a,b=ema(closes,fast),ema(closes,slow)
    if a is None or b is None: return "INSUFFICIENT"
    return "BULLISH" if a>b else "BEARISH" if a<b else "FLAT"

def build_signal(data):
    now=time.time()
    age=now-float(data.get("received_at",0))
    tf=data.get("timeframes",{})
    d1,h4,h1=tf.get("D1",[]),tf.get("H4",[]),tf.get("H1",[])
    if age>300: return {"signal":"WAIT","reason":"Market data is stale (older than 5 minutes).","data_age_seconds":int(age)}
    if min(len(d1),len(h4),len(h1)) < 205:
        return {"signal":"WAIT","reason":"Need at least 205 candles on D1, H4 and H1 for stable EMA200 analysis.","counts":{"D1":len(d1),"H4":len(h4),"H1":len(h1)}}
    td,th=trend(d1),trend(h4)
    c=[x["close"] for x in h1]
    e20,e50=ema(c,20),ema(c,50)
    rv=rsi(c)
    mh=macd_hist(c)
    a=atr(h4)
    if None in (e20,e50,rv,mh,a) or a<=0:
        return {"signal":"WAIT","reason":"Indicators are not ready."}
    bullish = td=="BULLISH" and th=="BULLISH" and e20>e50 and rv>=52 and mh>0
    bearish = td=="BEARISH" and th=="BEARISH" and e20<e50 and rv<=48 and mh<0
    last=h1[-1]["close"]
    # Require all higher timeframe filters to agree; no countertrend signals.
    if bullish: side="BUY"
    elif bearish: side="SELL"
    else: side="WAIT"
    result={"signal":side,"reason":"D1/H4 trend and H1 momentum aligned." if side!="WAIT" else "Timeframes or momentum are not fully aligned; wait for confirmation.",
            "trend":{"D1":td,"H4":th},"indicators":{"H1_EMA20":round(e20,2),"H1_EMA50":round(e50,2),"RSI14":round(rv,1),"MACD_hist":round(mh,5),"H4_ATR14":round(a,2)},
            "reference_entry":round(last,2),"stop_loss":None,"targets":[],
            "data_age_seconds":int(age),"last_candle_time":h1[-1].get("time")}
    if side!="WAIT":
        dist=1.5*a
        sl=last-dist if side=="BUY" else last+dist
        sign=1 if side=="BUY" else -1
        result["stop_loss"]=round(sl,2)
        result["targets"]=[round(last+sign*dist*r,2) for r in (1,2,3)]
        result["risk_distance"]=round(dist,2)
    return result

@app.get("/", response_class=HTMLResponse)
def home():
    return (FRONTEND/"index.html").read_text(encoding="utf-8")

@app.get("/api/health")
def health():
    return {"ok":True,"received":bool(DATA),"symbol":DATA.get("symbol"),"received_at":DATA.get("received_at")}

@app.post("/api/ingest")
def ingest(payload: dict, x_api_key: str = Header(default="")):
    if not API_KEY or x_api_key != API_KEY:
        raise HTTPException(status_code=401, detail="Invalid API key")
    if payload.get("symbol") is None or "timeframes" not in payload:
        raise HTTPException(status_code=400, detail="symbol and timeframes required")
    for tf in ("D1","H4","H1"):
        rows=payload["timeframes"].get(tf,[])
        if not isinstance(rows,list) or len(rows)>1000:
            raise HTTPException(status_code=400, detail=f"Invalid {tf} candles")
        for c in rows:
            for k in ("time","open","high","low","close"):
                if k not in c: raise HTTPException(status_code=400, detail=f"Missing {k}")
            if not all(math.isfinite(float(c[k])) for k in ("open","high","low","close")):
                raise HTTPException(status_code=400, detail="Non-finite candle")
    DATA.clear(); DATA.update(payload); DATA["received_at"]=time.time()
    return {"ok":True,"received_at":DATA["received_at"],"symbol":DATA["symbol"]}

@app.get("/api/status")
def status():
    if not DATA: return {"connected":False,"reason":"Waiting for MT5 bridge"}
    age=time.time()-DATA.get("received_at",0)
    return {"connected":age<=300,"symbol":DATA.get("symbol"),"bid":DATA.get("bid"),"ask":DATA.get("ask"),
            "received_at":DATA.get("received_at"),"age_seconds":int(age),
            "counts":{k:len(v) for k,v in DATA.get("timeframes",{}).items()}}

@app.get("/api/signal")
def signal():
    if not DATA: return {"signal":"WAIT","reason":"No MT5 data received yet."}
    return build_signal(DATA)

@app.get("/api/candles")
def candles():
    if not DATA: return {"symbol":None,"timeframes":{}}
    return {"symbol":DATA.get("symbol"),"timeframes":DATA.get("timeframes",{})}
