"""Real browser + API + PostgreSQL + Socket.IO. Public map/search traffic is stubbed."""
import asyncio
from functools import partial
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler, BaseHTTPRequestHandler
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import threading
import time
import httpx
import pytest
import asyncpg
from test_postgres import database, migrate
from app.security import get_password_hash

ROOT=Path(__file__).resolve().parents[1]
pytestmark=pytest.mark.skipif(os.environ.get('RUN_BROWSER_E2E')!='1' or not os.environ.get('TEST_DATABASE_URL'),reason='Opt in with RUN_BROWSER_E2E=1 and TEST_DATABASE_URL')

MAP_STUB = """
export class Map {
 constructor(){this.events={};setTimeout(()=>this.events.load?.(),0);}
 on(name,fn){this.events[name]=fn;return this;}
 addControl(){} flyTo(){} remove(){}
}
export class NavigationControl {}
export class Marker {
 constructor(){this.element=document.createElement('button');}
 setLngLat(point){this.point=point;return this;}
 setPopup(popup){this.popup=popup;return this;}
 getPopup(){return this.popup;}
 addTo(){return this;} getElement(){return this.element;}
 on(){return this;} remove(){}
}
export class Popup {setText(text){this.text=text;return this;}remove(){}}
"""

class StaticHandler(SimpleHTTPRequestHandler):
    def log_message(self,*args): pass

class PhotonHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        from urllib.parse import urlsplit,parse_qs
        query=parse_qs(urlsplit(self.path).query).get('q',[''])[0]
        code=503 if query=='Offline' else 200
        features=[] if query=='Nothing' else [{"geometry":{"type":"Point","coordinates":[71.4288,51.1232]},"properties":{"name":"Baiterek","city":"Astana"}}]
        data=json.dumps({'features':features}).encode()
        self.send_response(code);self.send_header('Content-Type','application/json');self.send_header('Content-Length',str(len(data)));self.end_headers();self.wfile.write(data)
    def log_message(self,*args): pass


def serve(server):
    thread=threading.Thread(target=server.serve_forever,daemon=True)
    thread.start()
    return thread


def free_port():
    with socket.socket() as sock:
        sock.bind(('127.0.0.1',0));return sock.getsockname()[1]


def test_two_dispatcher_workflow(database):
    from playwright.sync_api import sync_playwright, expect
    migrate()
    async def seed():
        conn=await asyncpg.connect(database)
        try: await conn.execute('INSERT INTO users(username,password) VALUES($1,$2)','browser-dispatcher',get_password_hash('browser-test-password'))
        finally: await conn.close()
    asyncio.run(seed())
    static=ThreadingHTTPServer(('127.0.0.1',0),partial(StaticHandler,directory=str(ROOT)))
    photon=ThreadingHTTPServer(('127.0.0.1',0),PhotonHandler)
    serve(static);serve(photon)
    static_origin=f'http://127.0.0.1:{static.server_port}'
    api_port=free_port();api_origin=f'http://127.0.0.1:{api_port}'
    env=dict(os.environ,CORS_ORIGINS=static_origin,PHOTON_API_URL=f'http://127.0.0.1:{photon.server_port}/api/')
    process=subprocess.Popen([sys.executable,'-m','uvicorn','main:app','--host','127.0.0.1','--port',str(api_port)],cwd=ROOT,env=env,stdout=subprocess.DEVNULL,stderr=subprocess.STDOUT)
    artifacts=ROOT/'test-results';artifacts.mkdir(exist_ok=True)
    try:
        for _ in range(100):
            if process.poll() is not None: raise RuntimeError('Test API exited')
            try:
                if httpx.get(api_origin+'/docs',timeout=1).status_code==200: break
            except httpx.HTTPError: pass
            time.sleep(0.1)
        else: raise RuntimeError('Test API did not start')
        socket_client=(ROOT/'node_modules/socket.io-client/dist/socket.io.min.js').read_text(encoding='utf-8')
        css=(ROOT/'output.css').read_text(encoding='utf-8')
        with sync_playwright() as pw:
            browser=pw.chromium.launch()
            contexts=[]
            try:
                for _ in range(2):
                    context=browser.new_context(viewport={'width':1360,'height':1000})
                    context.tracing.start(screenshots=True,snapshots=True)
                    def route_request(route):
                        url=route.request.url
                        if url.endswith('/frontend-config.js'):
                            return route.fulfill(content_type='text/javascript',body='window.TRACKER_CONFIG='+json.dumps({'apiBase':api_origin,'mapStyleUrl':'https://example.invalid/style'})+';')
                        if url.startswith('https://cdn.tailwindcss.com'):
                            return route.fulfill(content_type='text/javascript',body='const style=document.createElement("style");style.textContent='+json.dumps(css)+';document.head.append(style);')
                        if 'socket.io.min.js' in url:
                            return route.fulfill(content_type='text/javascript',body=socket_client)
                        if 'maplibre-gl.mjs' in url:
                            return route.fulfill(content_type='text/javascript',body=MAP_STUB,headers={'Access-Control-Allow-Origin':'*'})
                        if url.startswith('http://127.0.0.1:'): return route.continue_()
                        return route.abort()
                    context.route('**/*',route_request)
                    contexts.append(context)
                first,second=[context.new_page() for context in contexts]
                for page in [first,second]:
                    page.goto(static_origin+'/login.html')
                    page.locator('#username').fill('browser-dispatcher')
                    page.locator('#password').fill('browser-test-password')
                    page.locator('#loginButton').click()
                    page.wait_for_url('**/dashboard.html')
                    page.wait_for_function("typeof socket !== 'undefined' && socket.connected")
                    expect(page.locator('#loading')).to_be_hidden()
                # Deterministic provider failures and no-results states.
                first.locator('#addressQuery').fill('Nothing');first.locator('#addressSearchButton').click()
                expect(first.locator('#addressStatus')).to_contain_text('Ничего не найдено')
                first.locator('#addressQuery').fill('Offline');first.locator('#addressSearchButton').click()
                expect(first.locator('#addressStatus')).to_contain_text('Поиск недоступен')
                first.locator('#addressQuery').fill('Baiterek');first.locator('#addressSearchButton').click()
                first.locator('#addressResults button').click()
                expect(first.locator('#selectedCoordinates')).to_contain_text('51.123200')
                first.locator('#addTaskBtn').click()
                expect(first.locator('#add_latitude')).to_have_value('51.1232')
                expect(first.locator('#add_description')).to_have_value('Baiterek, Astana')
                first.locator('#add_expeditor_id').fill('7')
                attack='<img src=x onerror="window.__xss=1">'
                first.locator('#add_description').fill(attack)
                first.locator('.task-modal').get_by_role('button',name='Add Task',exact=True).click()
                expect(first.locator('.task-modal')).to_have_count(0)
                expect(second.locator('#tasksBody')).to_contain_text(attack)
                assert second.locator('#tasksBody img').count()==0
                assert second.evaluate('window.__xss') is None
                # Executor filter is applied by the API and can be reset.
                first.locator('#expeditorFilter').fill('9');first.locator('#applyFiltersBtn').click()
                expect(first.locator('#tasksBody')).to_contain_text('No tasks found')
                first.locator('#expeditorFilter').fill('7');first.locator('#applyFiltersBtn').click()
                expect(first.locator('#tasksBody')).to_contain_text(attack)
                first.locator('#tasksBody').get_by_role('button',name='Edit',exact=True).click()
                first.locator('#edit_status').select_option('completed')
                first.locator('.task-modal').get_by_role('button',name='Save',exact=True).click()
                expect(second.locator('#tasksBody')).to_contain_text('Завершено')
                expect(second.locator('#completedCount')).to_have_text('1')
                token=first.evaluate('localStorage.getItem("token")')
                for index in range(6):
                    response=httpx.post(api_origin+'/tasks',json={'expeditor_id':7,'description':f'Extra {index}'},headers={'Authorization':'Bearer '+token})
                    assert response.status_code==200
                expect(first.locator('#pageInfo')).to_contain_text('из 2')
                first.get_by_role('button',name='Следующая страница').click()
                expect(first.locator('#pageInfo')).to_contain_text('Страница 2')
                first.get_by_role('button',name='Предыдущая страница').click()
                expect(first.locator('#pageInfo')).to_contain_text('Страница 1')
                target=first.locator('#tasksBody tr').filter(has_text=attack)
                first.once('dialog',lambda dialog:dialog.accept())
                target.get_by_role('button',name='Delete',exact=True).click()
                expect(second.locator('#tasksBody')).not_to_contain_text(attack)
                expect(second.locator('#completedCount')).to_have_text('0')
                assert first.locator('#loading').count()==1
                first.screenshot(path=str(artifacts/'dispatcher-workflow.png'),full_page=True)
                print('Browser E2E: two dispatchers, address search, errors, XSS, CRUD, filtering, pagination and live updates passed')
            finally:
                for index,context in enumerate(contexts):
                    for page in context.pages:
                        page.screenshot(path=str(artifacts/f'final-{index}.png'),full_page=True)
                    context.tracing.stop(path=str(artifacts/f'trace-{index}.zip'))
                    context.close()
                browser.close()
    finally:
        process.terminate()
        try: process.wait(timeout=10)
        except subprocess.TimeoutExpired: process.kill();process.wait()
        static.shutdown();static.server_close();photon.shutdown();photon.server_close()
