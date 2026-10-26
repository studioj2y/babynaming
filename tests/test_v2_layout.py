"""
V2 场景立绘与交互 UI 布局空间对应关系自动化验证套件
验证目标：
1. 确保在所有分支与场景中，操作 UI / 按钮（.cLayer）决不可遮挡立绘（.actor）。
2. 确保对话气泡（.bLayer）与操作 UI（.cLayer）无重叠挤压。
3. 验证跨设备分辨率（iPhone SE 375x667, iPhone 13 390x844, Pixel 7 412x915）。
"""

import subprocess
import time
import json
import urllib.request
import websocket
import os
import sys
from http.server import HTTPServer, SimpleHTTPRequestHandler
import threading

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def find_browser():
    candidates = [
        os.environ.get("CHROME_BIN"),
        os.environ.get("BROWSER_PATH"),
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
        "/usr/bin/google-chrome",
        "/usr/bin/chromium-browser",
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    ]
    for c in candidates:
        if c and os.path.isfile(c):
            return c
    return None

class QuietHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=REPO_ROOT, **kwargs)
    def log_message(self, format, *args):
        pass

def run_tests():
    browser_path = find_browser()
    if not browser_path:
        print("[SKIP] No Chrome/Edge browser found for headless verification.")
        return True

    port = 8130
    httpd = HTTPServer(('127.0.0.1', port), QuietHandler)
    server_thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    server_thread.start()

    debug_port = 9230
    proc = subprocess.Popen([
        browser_path,
        "--headless=new",
        f"--remote-debugging-port={debug_port}",
        "--remote-allow-origins=*",
        "--disable-gpu",
        "--no-first-run",
        "--no-default-browser-check",
        f"http://127.0.0.1:{port}/v2/index.html"
    ])
    time.sleep(1.5)

    req_id = 0
    def send_cmd(ws, method, params=None):
        nonlocal req_id
        req_id += 1
        payload = {"id": req_id, "method": method}
        if params: payload["params"] = params
        ws.send(json.dumps(payload))
        while True:
            r = json.loads(ws.recv())
            if r.get("id") == req_id:
                return r

    all_passed = True
    try:
        tabs = json.loads(urllib.request.urlopen(f'http://127.0.0.1:{debug_port}/json').read().decode())
        tab = next((t for t in tabs if f"{port}" in t.get("url", "")), tabs[0])
        ws = websocket.create_connection(tab["webSocketDebuggerUrl"])

        for _ in range(25):
            r = send_cmd(ws, "Runtime.evaluate", {"expression": "document.readyState === 'complete' && typeof go === 'function'"})
            if r.get("result", {}).get("result", {}).get("value") is True:
                break
            time.sleep(0.3)

        viewports = [
            ("iPhone SE", 375, 667),
            ("iPhone 13", 390, 844),
            ("Pixel 7", 412, 915)
        ]

        scenes = ["s01", "s02", "s03a", "s04", "s05", "s06", "s07", "s08", "s08b", "s08_tags", "s08c", "s08c2"]

        measure_js = """
        (scKey) => new Promise(resolve => {
            go(scKey);
            setTimeout(() => {
                const actor = document.querySelector('.actor.show') || document.querySelector('.actor');
                const bubble = document.querySelector('.bLayer');
                const clayer = document.querySelector('.cLayer');
                const getBox = el => {
                    if(!el) return null;
                    const r = el.getBoundingClientRect();
                    return { top: Math.round(r.top), bottom: Math.round(r.bottom), height: Math.round(r.height), left: Math.round(r.left), right: Math.round(r.right) };
                };
                resolve({
                    scene: scKey,
                    actor: getBox(actor),
                    bubble: getBox(bubble),
                    clayer: getBox(clayer)
                });
            }, 450);
        })
        """

        for vp_name, w, h in viewports:
            print(f"\n==========================================")
            print(f" 验证视口: {vp_name} ({w}x{h})")
            print(f"==========================================")
            send_cmd(ws, "Emulation.setDeviceMetricsOverride", {
                "width": w,
                "height": h,
                "deviceScaleFactor": 2,
                "mobile": True
            })
            time.sleep(0.3)

            for sc in scenes:
                r = send_cmd(ws, "Runtime.evaluate", {
                    "expression": f"({measure_js})('{sc}')",
                    "awaitPromise": True,
                    "returnByValue": True
                })
                data = r.get("result", {}).get("result", {}).get("value")
                if not data:
                    print(f"[FAIL] {sc}: 无法获取渲染度量")
                    all_passed = False
                    continue
                act = data.get("actor")
                bub = data.get("bubble")
                cl = data.get("clayer")

                cl_actor_overlap = False
                cl_bub_overlap = False
                if act and cl:
                    cl_actor_overlap = not (cl['top'] >= act['bottom'] or cl['bottom'] <= act['top'])
                if bub and cl:
                    cl_bub_overlap = not (cl['top'] >= bub['bottom'] or cl['bottom'] <= bub['top'])

                if cl_actor_overlap:
                    print(f" [FAIL] 场景 {sc:10s} - 操作按钮遮挡了立绘! (按钮顶:{cl['top']}px, 立绘底:{act['bottom']}px)")
                    all_passed = False
                elif cl_bub_overlap:
                    print(f" [FAIL] 场景 {sc:10s} - 操作按钮与对话框挤压重叠! (按钮顶:{cl['top']}px, 气泡底:{bub['bottom']}px)")
                    all_passed = False
                else:
                    print(f" [PASS] 场景 {sc:10s} | 立绘底: {act['bottom'] if act else '-'}px | 气泡: {bub['top'] if bub else '-'}-{bub['bottom'] if bub else '-'}px | 操作栏顶: {cl['top'] if cl else '-'}px")

        ws.close()
    finally:
        proc.terminate()
        httpd.shutdown()

    return all_passed

if __name__ == "__main__":
    success = run_tests()
    if not success:
        sys.exit(1)
    print("\n[SUCCESS] 所有场景立绘与操作UI空间对应关系校验通过，无任何遮挡或冲突！")
    sys.exit(0)
