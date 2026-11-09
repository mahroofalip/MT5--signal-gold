#property strict
#property version   "1.00"
#property description "READ-ONLY GoldSignal AI candle bridge. Contains no trading functions."

input string InpSymbol = ""; // blank = chart symbol; otherwise exact broker symbol
input string InpApiUrl = "http://127.0.0.1:8787/api/ingest";
input string InpApiKey = "CHANGE_THIS_TO_A_LONG_RANDOM_SECRET";
input int    InpTimerSeconds = 60;
input int    InpBars = 250;

string Sym()
{
   if(StringLen(InpSymbol)>0) return InpSymbol;
   return _Symbol;
}

string EscapeJson(string s)
{
   StringReplace(s,"\\","\\\\");
   StringReplace(s,"\"","\\\"");
   return s;
}

string CandlesJson(string symbol, ENUM_TIMEFRAMES tf)
{
   MqlRates rates[];
   ArraySetAsSeries(rates,false);
   int copied=CopyRates(symbol,tf,1,InpBars,rates); // completed bars only
   if(copied<=0) return "[]";
   string out="[";
   for(int i=0;i<copied;i++)
   {
      if(i>0) out+=",";
      out+="{\"time\":"+IntegerToString((long)rates[i].time)+
           ",\"open\":"+DoubleToString(rates[i].open,_Digits)+
           ",\"high\":"+DoubleToString(rates[i].high,_Digits)+
           ",\"low\":"+DoubleToString(rates[i].low,_Digits)+
           ",\"close\":"+DoubleToString(rates[i].close,_Digits)+"}";
   }
   out+="]";
   return out;
}

void SendSnapshot()
{
   string symbol=Sym();
   if(!SymbolSelect(symbol,true))
   {
      Print("GoldSignal: symbol not available in Market Watch: ",symbol);
      return;
   }
   MqlTick tick;
   if(!SymbolInfoTick(symbol,tick))
   {
      Print("GoldSignal: waiting for tick for ",symbol);
      return;
   }

   string body="{\"symbol\":\""+EscapeJson(symbol)+"\",\"bid\":"+DoubleToString(tick.bid,_Digits)+
      ",\"ask\":"+DoubleToString(tick.ask,_Digits)+",\"timeframes\":{"+
      "\"D1\":"+CandlesJson(symbol,PERIOD_D1)+","+
      "\"H4\":"+CandlesJson(symbol,PERIOD_H4)+","+
      "\"H1\":"+CandlesJson(symbol,PERIOD_H1)+"}}";

   char data[],result[];
   string headers="Content-Type: application/json\r\nX-API-Key: "+InpApiKey+"\r\n";
   StringToCharArray(body,data,0,WHOLE_ARRAY,CP_UTF8);
   ArrayResize(data,ArraySize(data)-1); // remove terminating NUL
   string response_headers;
   ResetLastError();
   int code=WebRequest("POST",InpApiUrl,headers,5000,data,result,response_headers);
   if(code==200)
      Print("GoldSignal: candle snapshot sent for ",symbol);
   else
      Print("GoldSignal: WebRequest failed. HTTP=",code," MT5 error=",GetLastError(),
            ". Check backend, API key and MT5 allowed URL.");
}

int OnInit()
{
   if(InpApiKey=="CHANGE_THIS_TO_A_LONG_RANDOM_SECRET" || StringLen(InpApiKey)<20)
   {
      Print("GoldSignal: set a unique API key of at least 20 characters in EA inputs.");
      return INIT_PARAMETERS_INCORRECT;
   }
   EventSetTimer(MathMax(15,InpTimerSeconds));
   SendSnapshot();
   return INIT_SUCCEEDED;
}
void OnDeinit(const int reason){ EventKillTimer(); }
void OnTimer(){ SendSnapshot(); }
void OnTick(){ /* intentionally empty: READ-ONLY */ }
