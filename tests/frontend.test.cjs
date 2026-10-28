const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const { spawnSync } = require('node:child_process');
const root = path.join(__dirname, '..');

for (const file of ['dashboard.html','login.html','index.html','app-client.js','frontend-config.js']) {
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
  const ctx = {window:{TRACKER_CONFIG:{apiBase:'http://localhost:8000'}},document:{createElement:element},Date};
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
