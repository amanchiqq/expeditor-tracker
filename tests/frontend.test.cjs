const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const { spawnSync } = require('node:child_process');
const root = path.join(__dirname, '..');

for (const file of ['dashboard.html','login.html','index.html','app-client.js','frontend-config.js','tracker-map.js','address-search.js','tests/map-preview.html']) {
  test(`JavaScript syntax: ${file}`, () => {
    const source = fs.readFileSync(path.join(root,file),'utf8');
    assert.ok(!source.includes('\uFFFD'), `Invalid text encoding in ${file}`);
    const scripts = file.endsWith('.html') ? [...source.matchAll(/<script\b[^>]*>([\s\S]*?)<\/script>/g)].map(x=>x[1]) : [source];
    for (const code of scripts.filter(x=>x.trim())) {
      const result = spawnSync(process.execPath,['--check'],{input:code,encoding:'utf8'});
      assert.equal(result.status,0,result.stderr);
    }
  });
}

function context() {
  function element(tag) {
    return {tag, children:[], listeners:{}, textContent:'', appendChild(child){this.children.push(child);},
      addEventListener(name,cb){this.listeners[name]=cb;},
      set innerHTML(value){throw Error('Untrusted HTML insertion');}};
  }
  const ctx = {URLSearchParams,window:{TRACKER_CONFIG:{apiBase:'http://localhost:8000'}},document:{createElement:element},Date};
  vm.createContext(ctx);
  vm.runInContext(fs.readFileSync(path.join(root,'app-client.js'),'utf8'),ctx);
  return {ctx,element};
}

test('Description is rendered as text, and buttons keep numeric IDs', () => {
  const {ctx,element} = context();
  ctx.body=element('tbody'); ctx.calls=[];
  ctx.task={id:5,description:'<img src=x onerror=alert(1)>',status:'in_progress',created_at:'now',eta:null};
  vm.runInContext('appendTaskRow(body,task,id=>calls.push(id),id=>calls.push(id))',ctx);
  const row=ctx.body.children[0];
  assert.equal(row.children[1].textContent,ctx.task.description);
  row.children[5].children[0].listeners.click();
  assert.equal(ctx.calls[0],5);
});

test('ETA editing and saving preserve an instant in the browser timezone',()=>{
 const {ctx}=context();
 ctx.instant='2026-10-28T12:34:00+05:00';
 const result=vm.runInContext('new Date(localDateTime(instant)).toISOString()',ctx);
 assert.equal(result,new Date(ctx.instant).toISOString());
});

test('401 clears the token and redirects to sign in',async()=>{
 const {ctx}=context(); let removed;
 ctx.localStorage={removeItem:key=>removed=key};
 ctx.window.location={}; ctx.fetch=async()=>({status:401});
 await assert.rejects(vm.runInContext('trackerFetch(API_BASE + "/tasks")',ctx),/Session expired/);
 assert.equal(removed,'token'); assert.equal(ctx.window.location.href,'login.html');
});


function mapContext() {
  const ctx = {window:{}};
  vm.createContext(ctx);
  vm.runInContext(fs.readFileSync(path.join(root,'tracker-map.js'),'utf8'),ctx);
  const instances = [];
  class Map {
    constructor(options) { this.options=options;this.events={};instances.push(this); }
    on(name,fn){ this.events[name]=fn; }
    addControl(control,position){ this.controlPosition=position; }
    flyTo(options){this.camera=options;}
    remove(){this.removed=true;}
  }
  class Marker {
    constructor(options){ this.options=options;this.events={};this.element={addEventListener:(name,cb)=>this.events[name]=cb}; }
    setLngLat(point){this.point=point;return this;}
    setPopup(popup){this.popup=popup;return this;}
    getPopup(){return this.popup;}
    addTo(map){assert.ok(this.point,'Coordinates must be set before addTo');this.map=map;return this;}
    getElement(){return this.element;}
    getLngLat(){return {lng:this.point[0],lat:this.point[1]};}
    on(name,fn){this.events[name]=fn;return this;}
    remove(){this.removed=true;}
  }
  class Popup {
    setText(value){this.text=value;return this;}
    remove(){this.removed=true;}
  }
  const library={Map,Marker,Popup,NavigationControl:class {}};
  return {TrackerMap:ctx.window.TrackerMap,library,instances};
}

test('Default map is keyless and does not call 2GIS',()=>{
 const code=fs.readFileSync(path.join(root,'frontend-config.js'),'utf8');
 const ctx={window:{},location:{protocol:'http:',hostname:'localhost'}};
 vm.createContext(ctx);vm.runInContext(code,ctx);
 assert.equal(ctx.window.TRACKER_CONFIG.mapStyleUrl,'https://tiles.openfreemap.org/styles/liberty');
 assert.ok(!('mapKey' in ctx.window.TRACKER_CONFIG));
 assert.ok(!('geocodeKey' in ctx.window.TRACKER_CONFIG));
 assert.ok(!fs.readFileSync(path.join(root,'dashboard.html'),'utf8').includes('2gis'));
});

test('Tasks received before SDK load are drawn, with safe popup text and attribution',async()=>{
 const {TrackerMap,library,instances}=mapContext();
 let resolve;
 const adapter=new TrackerMap({container:'map',styleUrl:'style',loadLibrary:()=>new Promise(r=>resolve=r)});
 const attack='<img src=x onerror=alert(1)>';
 adapter.setTasks([{id:1,latitude:51,longitude:71,description:attack},{id:2,latitude:null,longitude:null}]);
 resolve(library);assert.equal(await adapter.ready,true);
 assert.equal(adapter.markers.length,1);
 assert.equal(adapter.markers[0].popup.text,'Task 1: '+attack);
 assert.equal(instances[0].options.attributionControl,true);
 assert.equal(instances[0].controlPosition,'top-right');
 let stopped=false;adapter.markers[0].events.click({stopPropagation(){stopped=true;}});
 assert.equal(stopped,true);
});

test('Map click and drag select coordinates; task refresh preserves selection',async()=>{
 const {TrackerMap,library,instances}=mapContext();let selected;
 const adapter=new TrackerMap({container:'map',styleUrl:'style',loadLibrary:async()=>library,onSelect:point=>selected=point});
 await adapter.ready;
 instances[0].events.click({lngLat:{lat:51.123456789,lng:71.432109876}});
 assert.equal(selected.latitude,51.123457);assert.equal(selected.longitude,71.43211);
 const marker=adapter.selectionMarker;
 adapter.setTasks([{id:1,latitude:51,longitude:71}]);
 assert.equal(adapter.selectionMarker,marker);assert.ok(!marker.removed);
 marker.setLngLat([71.5,51.2]);marker.events.dragend();
 assert.equal(selected.latitude,51.2);assert.equal(selected.longitude,71.5);
 adapter.setTasks([]);assert.equal(adapter.selectionMarker,marker);
 adapter.clearSelection();assert.equal(selected,null);assert.equal(marker.removed,true);
});

test('Marker updates remove stale markers and validate coordinate ranges including zero',async()=>{
 const {TrackerMap,library}=mapContext();
 const adapter=new TrackerMap({container:'map',styleUrl:'style',loadLibrary:async()=>library});
 await adapter.ready;
 adapter.setTasks([{id:1,latitude:0,longitude:0}]);const old=adapter.markers[0];
 adapter.setTasks([{id:2,latitude:100,longitude:71},{id:3,latitude:51,longitude:200},{id:4,latitude:51,longitude:71}]);
 assert.equal(old.removed,true);assert.equal(old.popup.removed,true);assert.equal(adapter.markers.length,1);
 assert.equal(adapter.select(NaN,71),false);assert.equal(adapter.select(0,0),true);
});

test('Clear before SDK load does not resurrect tasks, and late SDK load respects disposal',async()=>{
 const {TrackerMap,library,instances}=mapContext();let resolve;
 const adapter=new TrackerMap({container:'map',styleUrl:'style',loadLibrary:()=>new Promise(r=>resolve=r)});
 adapter.setTasks([{id:1,latitude:51,longitude:71}]);adapter.clearTasks();resolve(library);await adapter.ready;
 assert.equal(adapter.markers.length,0);adapter.destroy();assert.equal(instances[0].removed,true);
 let resolveLate;
 const disposed=new TrackerMap({container:'map',styleUrl:'style',loadLibrary:()=>new Promise(r=>resolveLate=r)});
 disposed.destroy();resolveLate(library);assert.equal(await disposed.ready,false);assert.equal(instances.length,1);
});

test('SDK or tile failures are reported without breaking task entry',async()=>{
 const {TrackerMap,library,instances}=mapContext();let status='';
 const failed=new TrackerMap({container:'map',styleUrl:'style',loadLibrary:async()=>{throw Error('offline');},onStatus:value=>status=value});
 assert.equal(await failed.ready,false);assert.ok(status.includes('вручную') || status.includes('ручной'));
 assert.equal(failed.select(51,71),true);
 const adapter=new TrackerMap({container:'map',styleUrl:'style',loadLibrary:async()=>library,onStatus:value=>status=value});
 await adapter.ready;instances[0].events.error();assert.ok(status.includes('вручную'));
 instances[0].events.load();assert.ok(status.includes('готова'));
});


test('Closing a task modal never removes the shared loading overlay',()=>{
 const page=fs.readFileSync(path.join(root,'dashboard.html'),'utf8');
 assert.ok(!page.includes("querySelector('.fixed')"));
 assert.equal((page.match(/form.className = 'task-modal'/g)||[]).length,2);
});


test('Executor filter is encoded together with all other task filters',()=>{
 const {ctx}=context();
 const url=vm.runInContext("taskListUrl({page:2,perPage:5,taskId:'7',expeditorId:'3',status:'completed',date:'2026-10-28'})",ctx);
 const parsed=new URL(url);
 assert.equal(parsed.searchParams.get('expeditor_id'),'3');
 assert.equal(parsed.searchParams.get('task_id'),'7');
 assert.equal(parsed.searchParams.get('status'),'completed');
 assert.equal(parsed.searchParams.get('date'),'2026-10-28');
});

test('ETA edit preserves seconds and milliseconds; empty time has a readable label',()=>{
 const {ctx}=context();
 ctx.instant='2026-10-28T12:34:56.789+05:00';
 assert.equal(vm.runInContext('new Date(localDateTime(instant)).toISOString()',ctx),new Date(ctx.instant).toISOString());
 assert.equal(vm.runInContext('formatTaskTime(null)',ctx),'—');
});

test('Address selection focuses the map, including before SDK load',async()=>{
 const {TrackerMap,library,instances}=mapContext();let resolve;
 const adapter=new TrackerMap({container:'map',styleUrl:'style',loadLibrary:()=>new Promise(r=>resolve=r)});
 assert.equal(adapter.focus(51.1,71.4),true);resolve(library);await adapter.ready;
 assert.equal(instances[0].camera.zoom,16);assert.equal(adapter.selection.latitude,51.1);
 adapter.focus(51.2,71.5);assert.equal(instances[0].camera.center[0],71.5);
 assert.equal(adapter.focus(100,71),false);
});

function searchContext(search,onPick=()=>{}) {
 function element(){return {value:'',children:[],listeners:{},disabled:false,textContent:'',
  addEventListener(name,fn){this.listeners[name]=fn;},appendChild(child){this.children.push(child);},
  replaceChildren(){this.children=[];},set innerHTML(value){throw Error('Unsafe HTML');}};}
 const ctx={window:{},AbortController,document:{createElement:element}};
 vm.createContext(ctx);vm.runInContext(fs.readFileSync(path.join(root,'address-search.js'),'utf8'),ctx);
 const controls={form:element(),input:element(),button:element(),results:element(),status:element()};
 const controller=new ctx.window.AddressSearch({...controls,search,onPick});
 return {...controls,controller};
}

test('Search sends no keystroke requests and selects results as text',async()=>{
 let calls=0,picked;
 const item={label:'<img src=x onerror=alert(1)>',latitude:51,longitude:71};
 const ui=searchContext(async()=>{calls++;return [item];},value=>picked=value);
 ui.input.value='Astana';ui.input.listeners.input();assert.equal(calls,0);
 await ui.controller.run();assert.equal(calls,1);
 const button=ui.results.children[0].children[0];assert.equal(button.textContent,item.label);
 button.listeners.click();assert.equal(picked,item);assert.equal(ui.results.children.length,0);
});

test('Stale search results never replace a newer input',async()=>{
 let resolve;
 const ui=searchContext(()=>new Promise(r=>resolve=r));
 ui.input.value='First';const pending=ui.controller.run();
 ui.input.value='Second';ui.input.listeners.input();resolve([{label:'Old'}]);await pending;
 assert.equal(ui.results.children.length,0);assert.equal(ui.button.disabled,false);
});

test('Search handles short queries, empty results and provider errors',async()=>{
 let calls=0;const ui=searchContext(async()=>{calls++;return [];});
 ui.input.value='ab';await ui.controller.run();assert.equal(calls,0);
 ui.input.value='Astana';await ui.controller.run();assert.ok(ui.status.textContent.includes('Ничего'));
 ui.controller.search=async()=>{throw Error('Поиск занят');};await ui.controller.run();
 assert.equal(ui.status.textContent,'Поиск занят');assert.equal(ui.button.disabled,false);
});
