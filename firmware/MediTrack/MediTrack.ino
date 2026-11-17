#include <WiFi.h>
#include <HTTPClient.h>
#include <Preferences.h>
#include <ArduinoJson.h>
#include <time.h>
#include "secrets.h"
#include "mechanism.h"

// Arduino-ESP32 3.x. LEDC avoids a library's default midpoint attachment pulse.
constexpr int SERVO_PIN=18;
Preferences prefs;
struct Record { uint32_t magic; char event[37]; char cycle[37]; int position; int target; int phase; char outcome[24]; } state;
// phase: 0 idle, 1 intent persisted before motion, 2 result awaiting acknowledgement.
bool aligned=false, emptyConfirmed=false, pwm=false, storageOK=true;
String pendingHome, approvedHome;
unsigned long nextPoll=0, nextWifi=0;
unsigned retryMs=3000;

bool persist() {
 storageOK=prefs.putBytes("record", &state, sizeof(state))==sizeof(state);
 if(!storageOK) { aligned=false; Serial.println("Помилка NVS: рух заблоковано."); }
 return storageOK;
}
void pulse(int angle) {
 int us=PULSE_HOME_US+(PULSE_160_US-PULSE_HOME_US)*angle/160;
 if(!pwm) { pwm=ledcAttach(SERVO_PIN,50,16); }
 if(pwm) ledcWrite(SERVO_PIN,(uint32_t)((uint64_t)us*65535/20000));
}
bool request(const char* path, JsonDocument &response, const String &body="") {
 if(WiFi.status()!=WL_CONNECTED)return false;
 WiFiClient client; HTTPClient http;
 http.setConnectTimeout(3000);http.setTimeout(5000);
 if(!http.begin(client,String(API_BASE)+path))return false;
 http.addHeader("X-Device-ID",DEVICE_ID);
 http.addHeader("Authorization",String("Bearer ")+DEVICE_SECRET);
 http.addHeader("Content-Type","application/json");
 int code=body.length()?http.POST(body):http.GET();
 bool ok=false;
 if(code==200)ok=!deserializeJson(response,http.getString());
 http.end();return ok;
}
bool acknowledge() {
 JsonDocument body,response;body["event_id"]=state.event;body["outcome"]=state.outcome;
 String serialized;serializeJson(body,serialized);
 if(!request("/api/confirm",response,serialized))return false;
 if(response["ok"]!=true || String(response["event_id"]|"")!=state.event)return false;
 if(String(response["state"]|"")!=state.outcome) { aligned=false;return false; }
 state.phase=0;return persist();
}
void execute(JsonDocument &cmd,bool home) {
 const char* id=cmd["event_id"]|"";const char* cycle=cmd["cycle_id"]|"";
 if(strlen(id)!=36||strlen(cycle)!=36)return;
 // Lost NVS cannot prove whether an already issued event moved the mechanism.
 // Report uncertainty so the backend can unlock the supervised service route.
 if(!home && strlen(state.cycle)!=36) {
  strncpy(state.event,id,37);strncpy(state.cycle,cycle,37);
  state.phase=2;strcpy(state.outcome,"uncertain");aligned=false;persist();return;
 }
 if(home) {pendingHome=id;emptyConfirmed=approvedHome==pendingHome;}
 Action action=nextAction(state.phase,String(id)==state.event,home,emptyConfirmed,aligned);
 if(action==Action::Acknowledge) {acknowledge();return;}
 if(action!=Action::Move)return;
 time_t now=time(nullptr);
 if(now<1700000000)return; // no usable network time: no new motion
 bool valid=home || (String(cycle)==state.cycle &&
   cmd["previous_compartment"].is<int>() && cmd["previous_compartment"].as<int>()==state.position &&
   cmd["compartment"].is<int>() && cmd["angle"].is<int>() &&
   validStep(state.position,cmd["compartment"],cmd["angle"]));
 valid=valid && cmd["expires_at"].is<long long>() && now<=cmd["expires_at"].as<long long>();
 strncpy(state.event,id,37);strncpy(state.cycle,cycle,37);
 state.target=home?0:cmd["compartment"].as<int>();
 if(!valid) {
  strcpy(state.outcome,"not_started");state.phase=2;aligned=false;persist();return;
 }
 state.phase=1;strcpy(state.outcome,"uncertain");
 if(!persist())return;
 int from=state.position*20,to=state.target*20;
 // The operator's EMPTY assertion makes an unknown home starting position safe.
 pulse(from);
 if(!pwm) { state.phase=2;aligned=false;persist();return; }
 for(int angle=from;angle!=to;angle+=(to>from?1:-1)) {pulse(angle);delay(30);}
 pulse(to);delay(2000);
 state.position=state.target;state.phase=2;
 strcpy(state.outcome,home?"homed":"command_completed");
 if(!persist())return;
 aligned=true;emptyConfirmed=false;approvedHome="";pendingHome="";acknowledge();
}
void setup() {
 Serial.begin(115200);Serial.setTimeout(100);
 storageOK=prefs.begin("meditrack",false);
 if(!storageOK)return;
 bool exists=prefs.getBytesLength("record")==sizeof(state);
 if(exists)prefs.getBytes("record",&state,sizeof(state));
 if(!exists||state.magic!=0x4D545231||state.position<0||state.position>8) {
  memset(&state,0,sizeof(state));state.magic=0x4D545231;persist();
 } else if(state.phase==1) {state.phase=phaseAfterRestart(state.phase);strcpy(state.outcome,"uncertain");persist();}
 WiFi.mode(WIFI_STA);WiFi.begin(WIFI_SSID,WIFI_PASSWORD);
 configTime(0,0,"pool.ntp.org","time.google.com");
 Serial.println("Огляньте позицію. ALIGN лише при збігу мітки; EMPTY лише після повного спорожнення для Home.");
}
void loop() {
 if(!storageOK){delay(100);return;}
 if(Serial.available()) {
  String command=Serial.readStringUntil('\n');command.trim();
  if(command=="EMPTY" && pendingHome.length()==36)approvedHome=pendingHome;
  if(command=="ALIGN"&&state.phase==0&&strlen(state.cycle)==36 && String(state.outcome)!="uncertain" && String(state.outcome)!="not_started")aligned=true;
  Serial.printf("Позиція %d, фаза %d\n",state.position,state.phase);
 }
 if(WiFi.status()!=WL_CONNECTED && (long)(millis()-nextWifi)>=0) {WiFi.reconnect();nextWifi=millis()+10000;}
 if((long)(millis()-nextPoll)<0){delay(10);return;}
 bool success=false;
 if(state.phase==2)success=acknowledge();
 else {
  JsonDocument cmd;
  success=request("/api/check",cmd);
  if(success) {
   String status=cmd["status"]|"";
   if(status=="DISPENSE"||status=="HOME")execute(cmd,status=="HOME");
  }
 }
 retryMs=success?3000:min(retryMs*2,60000u);nextPoll=millis()+retryMs;
}
