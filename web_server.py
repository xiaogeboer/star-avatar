"""
体育明星头像下载工具 - Web UI 服务器
支持 TheSportsDB（主）、ESPN（备）和 Wikidata（补充）
带缓存优化，提升响应速度
纯 Python 标准库实现，无需安装任何第三方依赖
"""

import json
import mimetypes
import os
import queue
import subprocess
import sys
import threading
import time
import urllib.parse
import webbrowser
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from pathlib import Path

# 导入 API 模块
try:
    import espn_api
except ImportError:
    print("警告: 无法导入 espn_api 模块")
    espn_api = None

try:
    import wikidata_api
except ImportError:
    print("警告: 无法导入 wikidata_api 模块")
    wikidata_api = None

# 导入缓存管理
try:
    from cache_manager import get_cache
except ImportError:
    print("警告: 无法导入 cache_manager 模块")
    get_cache = None

# 配置
PORT = 8888
API_KEY = "3"
BASE_URL = f"https://www.thesportsdb.com/api/v1/json/{API_KEY}"
SCRIPT_DIR = Path(__file__).parent.resolve()
DOWNLOAD_DIR = SCRIPT_DIR / "sports_avatars"
INDEX_HTML = SCRIPT_DIR / "index.html"


def http_get(url):
    """使用 curl 发送 GET 请求并返回原始字节"""
    try:
        result = subprocess.run(
            ["curl", "-s", "-L", "-f", "--max-time", "15", url],
            capture_output=True,
        )
        if result.returncode != 0:
            return None
        return result.stdout
    except FileNotFoundError:
        return None


def download_file(url, save_path):
    """使用 curl 下载文件到指定路径"""
    try:
        result = subprocess.run(
            ["curl", "-s", "-f", "--max-time", "30", "-o", str(save_path), url],
            capture_output=True,
        )
        return result.returncode == 0
    except FileNotFoundError:
        return False


def sanitize_filename(name):
    """清理文件名中的非法字符"""
    invalid_chars = '<>:"/\\|?*'
    for ch in invalid_chars:
        name = name.replace(ch, "_")
    return name


def is_safe_filename(filename):
    """检查文件名是否安全（防止路径穿越攻击）"""
    if not filename:
        return False
    if ".." in filename or "/" in filename or "\\" in filename:
        return False
    basename = os.path.basename(filename)
    return basename == filename and len(basename) > 0


class Handler(BaseHTTPRequestHandler):

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        query = urllib.parse.parse_qs(parsed.query)

        if path == "/" or path == "/index.html":
            self._serve_index()
        elif path == "/api/search":
            self._handle_search(query)
        elif path == "/api/search-stream":
            self._handle_search_stream(query)
        elif path == "/api/gallery":
            self._handle_gallery()
        elif path == "/api/proxy-image":
            self._handle_proxy_image(query)
        elif path == "/api/open-folder":
            self._handle_open_folder()
        elif path.startswith("/sports_avatars/"):
            self._serve_static(path)
        else:
            self._send_error(404, "Not Found")

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length) if content_length > 0 else b""

        try:
            data = json.loads(body) if body else {}
        except json.JSONDecodeError:
            self._send_json({"error": "Invalid JSON"}, 400)
            return

        if path == "/api/download":
            self._handle_download(data)
        elif path == "/api/delete":
            self._handle_delete(data)
        else:
            self._send_error(404, "Not Found")

    def _serve_index(self):
        try:
            content = INDEX_HTML.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(content)))
            self.end_headers()
            self.wfile.write(content)
        except FileNotFoundError:
            self._send_error(500, "index.html not found")

    def _query_thesportsdb(self, q, cache, result_queue):
        """查询 TheSportsDB，结果放入队列"""
        try:
            thesportsdb_results = None
            if cache:
                cached = cache.get(q, "TheSportsDB")
                if cached:
                    thesportsdb_results = cached
            
            if not thesportsdb_results:
                encoded = urllib.parse.quote(q)
                url = f"{BASE_URL}/searchplayers.php?p={encoded}"
                raw = http_get(url)
                if raw:
                    try:
                        data = json.loads(raw)
                        if data and data.get("player"):
                            thesportsdb_results = data["player"]
                            for player in thesportsdb_results:
                                player["api_source"] = "TheSportsDB"
                            if cache:
                                cache.set(q, "TheSportsDB", thesportsdb_results)
                    except json.JSONDecodeError:
                        pass
            
            if thesportsdb_results:
                result_queue.put({"api": "TheSportsDB", "players": thesportsdb_results})
        except Exception as e:
            print(f"  [TheSportsDB] 查询异常: {e}")
        finally:
            result_queue.put(None)  # sentinel

    def _query_espn(self, q, cache, result_queue):
        """查询 ESPN，结果放入队列"""
        try:
            if not espn_api:
                return
            
            espn_results = None
            if cache:
                cached = cache.get(q, "ESPN")
                if cached:
                    espn_results = cached
            
            if not espn_results:
                athletes = espn_api.search_athlete(q)
                if athletes:
                    espn_results = espn_api.format_athletes_for_display(athletes)
                    if cache:
                        cache.set(q, "ESPN", espn_results)
            
            if espn_results:
                result_queue.put({"api": "ESPN", "players": espn_results})
        except Exception as e:
            print(f"  [ESPN] 查询异常: {e}")
        finally:
            result_queue.put(None)  # sentinel

    def _query_wikidata(self, q, cache, result_queue):
        """查询 Wikidata，结果放入队列"""
        try:
            if not wikidata_api:
                return
            
            wikidata_results = None
            if cache:
                cached = cache.get(q, "Wikidata")
                if cached:
                    wikidata_results = cached
            
            if not wikidata_results:
                athletes = wikidata_api.search_athlete_wikidata(q)
                if athletes:
                    wikidata_results = wikidata_api.format_athletes_for_display(athletes)
                    if cache:
                        cache.set(q, "Wikidata", wikidata_results)
            
            if wikidata_results:
                result_queue.put({"api": "Wikidata", "players": wikidata_results})
        except Exception as e:
            print(f"  [Wikidata] 查询异常: {e}")
        finally:
            result_queue.put(None)  # sentinel

    def _send_sse(self, event, data):
        """发送 SSE 事件"""
        payload = json.dumps(data, ensure_ascii=False)
        self.wfile.write(f"event: {event}\ndata: {payload}\n\n".encode("utf-8"))
        self.wfile.flush()

    def _handle_search_stream(self, query):
        """SSE 流式搜索：各 API 谁先返回谁就先推送给前端"""
        q = query.get("q", [""])[0].strip()
        if not q:
            self._send_json({"error": "Missing query parameter 'q'"}, 400)
            return
        
        # 设置 SSE 响应头
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "keep-alive")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        
        start_time = time.time()
        cache = get_cache() if get_cache else None
        result_queue = queue.Queue()
        
        # 启动三个线程并行查询
        threads = [
            threading.Thread(target=self._query_thesportsdb, args=(q, cache, result_queue)),
            threading.Thread(target=self._query_espn, args=(q, cache, result_queue)),
            threading.Thread(target=self._query_wikidata, args=(q, cache, result_queue)),
        ]
        
        for t in threads:
            t.daemon = True
            t.start()
        
        # 收集所有结果并实时推送
        all_results = []
        sources_count = {"TheSportsDB": 0, "ESPN": 0, "Wikidata": 0, "Wikidata+Wikipedia": 0}
        finished_threads = 0
        
        while finished_threads < len(threads):
            item = result_queue.get()
            if item is None:
                finished_threads += 1
                continue
            
            api_name = item["api"]
            players = item["players"]
            
            # 统计来源
            for p in players:
                source = p.get("api_source", api_name)
                if source in sources_count:
                    sources_count[source] += 1
            
            all_results.extend(players)
            
            # 实时推送给前端
            self._send_sse("result", {
                "api": api_name,
                "players": players,
                "count": len(players)
            })
        
        elapsed = time.time() - start_time
        
        # 发送完成事件
        self._send_sse("done", {
            "total": len(all_results),
            "sources": sources_count,
            "time": round(elapsed, 2)
        })

    def _handle_search(self, query):
        q = query.get("q", [""])[0].strip()
        if not q:
            self._send_json({"error": "Missing query parameter 'q'"}, 400)
            return
        
        start_time = time.time()
        cache = get_cache() if get_cache else None
        all_results = []
        
        # 并行查询所有 API，收集所有结果
        
        # 1. TheSportsDB
        thesportsdb_results = None
        if cache:
            cached = cache.get(q, "TheSportsDB")
            if cached:
                thesportsdb_results = cached
        
        if not thesportsdb_results:
            encoded = urllib.parse.quote(q)
            url = f"{BASE_URL}/searchplayers.php?p={encoded}"
            raw = http_get(url)
            if raw:
                try:
                    data = json.loads(raw)
                    if data and data.get("player"):
                        thesportsdb_results = data["player"]
                        for player in thesportsdb_results:
                            player["api_source"] = "TheSportsDB"
                        if cache:
                            cache.set(q, "TheSportsDB", thesportsdb_results)
                except json.JSONDecodeError:
                    pass
        
        if thesportsdb_results:
            all_results.extend(thesportsdb_results)
        
        # 2. ESPN API
        espn_results = None
        if espn_api:
            if cache:
                cached = cache.get(q, "ESPN")
                if cached:
                    espn_results = cached
            
            if not espn_results:
                athletes = espn_api.search_athlete(q)
                if athletes:
                    espn_results = espn_api.format_athletes_for_display(athletes)
                    if cache:
                        cache.set(q, "ESPN", espn_results)
        
        if espn_results:
            all_results.extend(espn_results)
        
        # 3. Wikidata
        wikidata_results = None
        if wikidata_api:
            if cache:
                cached = cache.get(q, "Wikidata")
                if cached:
                    wikidata_results = cached
            
            if not wikidata_results:
                athletes = wikidata_api.search_athlete_wikidata(q)
                if athletes:
                    wikidata_results = wikidata_api.format_athletes_for_display(athletes)
                    if cache:
                        cache.set(q, "Wikidata", wikidata_results)
        
        if wikidata_results:
            all_results.extend(wikidata_results)
        
        # 按 API 优先级排序：TheSportsDB > ESPN > Wikidata
        api_priority = {"TheSportsDB": 0, "ESPN": 1, "Wikidata": 2}
        all_results.sort(key=lambda x: api_priority.get(x.get("api_source", ""), 99))
        
        elapsed = time.time() - start_time
        
        # 统计各来源数量（包括 Wikipedia 补充的图片）
        wiki_wiki_count = sum(1 for p in wikidata_results if p.get("api_source") == "Wikidata+Wikipedia") if wikidata_results else 0
        wiki_pure_count = sum(1 for p in wikidata_results if p.get("api_source") == "Wikidata") if wikidata_results else 0
        
        if all_results:
            response = {
                "player": all_results,
                "total": len(all_results),
                "sources": {
                    "TheSportsDB": len(thesportsdb_results) if thesportsdb_results else 0,
                    "ESPN": len(espn_results) if espn_results else 0,
                    "Wikidata": wiki_pure_count,
                    "Wikidata+Wikipedia": wiki_wiki_count
                },
                "time": elapsed
            }
            self._send_json(response)
        else:
            self._send_json({"error": "No results found", "time": elapsed}, 404)

    def _handle_download(self, data):
        url = data.get("url", "")
        player_name = data.get("playerName", "unknown")
        image_type = data.get("imageType", "thumb")

        if not url:
            self._send_json({"error": "Missing 'url'"}, 400)
            return

        safe_name = sanitize_filename(player_name)
        ext = os.path.splitext(urllib.parse.urlparse(url).path)[1]
        if not ext:
            ext = ".jpg"

        filename = f"{safe_name}_{image_type}{ext}"
        save_path = DOWNLOAD_DIR / filename

        DOWNLOAD_DIR.mkdir(exist_ok=True)

        if download_file(url, save_path):
            file_size = save_path.stat().st_size
            self._send_json({
                "success": True,
                "filename": filename,
                "size": file_size,
            })
        else:
            self._send_json({"success": False, "error": "Download failed"}, 500)

    def _handle_gallery(self):
        DOWNLOAD_DIR.mkdir(exist_ok=True)
        image_exts = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp"}
        files = []

        for f in DOWNLOAD_DIR.iterdir():
            if f.is_file() and f.suffix.lower() in image_exts:
                stat = f.stat()
                files.append({
                    "filename": f.name,
                    "size": stat.st_size,
                    "modified": stat.st_mtime,
                })

        files.sort(key=lambda x: x["modified"], reverse=True)

        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Cache-Control", "no-cache")
        body = json.dumps(files).encode()
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _handle_proxy_image(self, query):
        """代理外部图片请求，解决浏览器无法直接加载 CDN 图片的问题"""
        url = query.get("url", [""])[0]
        if not url:
            self._send_error(400, "Missing 'url' parameter")
            return

        # 安全校验：允许代理 thesportsdb、espn 和 wikimedia 的图片
        parsed_url = urllib.parse.urlparse(url)
        allowed_hosts = {
            "r2.thesportsdb.com", "www.thesportsdb.com", "thesportsdb.com",
            "a.espncdn.com", "espn.com",  # ESPN CDN
            "upload.wikimedia.org", "upload.wikimedia.com",  # Wikimedia CDN
            "commons.wikimedia.org",  # Wikimedia Special:FilePath
        }
        if parsed_url.hostname not in allowed_hosts:
            self._send_error(403, "Only trusted image hosts allowed")
            return

        raw = http_get(url)
        if raw is None:
            self._send_error(502, "Failed to fetch image")
            return

        mime_type = mimetypes.guess_type(parsed_url.path)[0] or "image/jpeg"
        self.send_response(200)
        self.send_header("Content-Type", mime_type)
        self.send_header("Cache-Control", "public, max-age=86400")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def _handle_open_folder(self):
        """打开下载文件夹"""
        try:
            DOWNLOAD_DIR.mkdir(exist_ok=True)
            subprocess.Popen(["open", str(DOWNLOAD_DIR)])
            self._send_json({"success": True})
        except Exception as e:
            self._send_json({"success": False, "error": str(e)}, 500)

    def _handle_delete(self, data):
        filename = data.get("filename", "")

        if not is_safe_filename(filename):
            self._send_json({"error": "Invalid filename"}, 400)
            return

        filepath = DOWNLOAD_DIR / filename
        resolved = filepath.resolve()
        if not str(resolved).startswith(str(DOWNLOAD_DIR.resolve())):
            self._send_json({"error": "Access denied"}, 403)
            return

        if filepath.exists():
            filepath.unlink()
            self._send_json({"success": True})
        else:
            self._send_json({"error": "File not found"}, 404)

    def _serve_static(self, path):
        filename = path.split("/sports_avatars/", 1)[-1]
        filename = urllib.parse.unquote(filename)

        if not is_safe_filename(filename):
            self._send_error(400, "Invalid filename")
            return

        filepath = DOWNLOAD_DIR / filename
        resolved = filepath.resolve()
        if not str(resolved).startswith(str(DOWNLOAD_DIR.resolve())):
            self._send_error(403, "Access denied")
            return

        if not filepath.exists():
            self._send_error(404, "File not found")
            return

        mime_type = mimetypes.guess_type(str(filepath))[0] or "application/octet-stream"
        content = filepath.read_bytes()

        self.send_response(200)
        self.send_header("Content-Type", mime_type)
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)

    def _send_json(self, data, status=200):
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_error(self, status, message):
        self._send_json({"error": message}, status)

    def log_message(self, format, *args):
        sys.stdout.write(f"  {args[0]}\n")


def main():
    if not INDEX_HTML.exists():
        print(f"错误: 找不到 {INDEX_HTML}")
        print("请确保 index.html 与 web_server.py 在同一目录下")
        sys.exit(1)

    DOWNLOAD_DIR.mkdir(exist_ok=True)

    server = ThreadingHTTPServer(("", PORT), Handler)

    print("=" * 50)
    print("  体育明星头像下载工具 - Web UI")
    print("  API: TheSportsDB -> ESPN -> Wikidata")
    print("=" * 50)
    print(f"  服务地址: http://localhost:{PORT}")
    print(f"  下载目录: {DOWNLOAD_DIR}")
    print(f"  按 Ctrl+C 停止服务器")
    print("=" * 50)

    threading.Timer(1.0, webbrowser.open, args=[f"http://localhost:{PORT}"]).start()

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n服务器已停止")
        server.server_close()


if __name__ == "__main__":
    main()
