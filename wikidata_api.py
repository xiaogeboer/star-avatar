"""
Wikidata API 体育明星头像下载模块
使用 Wikidata SPARQL 查询运动员信息
完全免费，覆盖所有运动类型（包括羽毛球等小众运动）
"""

import json
import re
import subprocess
import urllib.parse
import urllib.request
import urllib.error


# Wikidata SPARQL 端点
WIKIDATA_SPARQL_URL = "https://query.wikidata.org/sparql"


def http_get_json(url):
    """使用 urllib 发送 GET 请求并返回 JSON 数据"""
    try:
        req = urllib.request.Request(url)
        req.add_header('User-Agent', 'SportsAvatarDownloader/1.0')
        
        with urllib.request.urlopen(req, timeout=30) as response:
            data = response.read().decode('utf-8')
            return json.loads(data)
    except urllib.error.URLError as e:
        print(f"  [Wikidata] 请求失败: {e}")
        return None
    except (json.JSONDecodeError, Exception) as e:
        print(f"  [Wikidata] 解析失败: {e}")
        return None


def search_athlete_wikidata(player_name):
    """
    使用 Wikidata SPARQL 搜索运动员
    
    参数:
        player_name: 运动员名字（英文或中文）
    
    返回:
        运动员列表
    """
    # SPARQL 查询：搜索运动员及其图片
    # 使用 rdfs:label 进行精确搜索
    sparql_query = f'''
    SELECT DISTINCT ?person ?personLabel ?image ?description WHERE {{
      {{
        ?person rdfs:label "{player_name}"@en .
      }}
      UNION
      {{
        ?person rdfs:label "{player_name}"@zh .
      }}
      ?person wdt:P31 wd:Q5 .  # 是人类
      OPTIONAL {{ ?person wdt:P18 ?image . }}  # 可选：图片
      OPTIONAL {{ ?person schema:description ?description . FILTER(LANG(?description) = "en") }}
      SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en,zh" . }}
    }}
    LIMIT 20
    '''
    
    # URL 编码 SPARQL 查询
    encoded_query = urllib.parse.quote(sparql_query)
    url = f"{WIKIDATA_SPARQL_URL}?query={encoded_query}&format=json"
    
    data = http_get_json(url)
    if not data or "results" not in data:
        return []
    
    athletes = []
    bindings = data["results"].get("bindings", [])
    
    for binding in bindings:
        # 提取运动员信息
        person_url = binding.get("person", {}).get("value", "")
        person_id = person_url.split("/")[-1] if person_url else ""
        
        person_label = binding.get("personLabel", {}).get("value", "Unknown")
        image_url = binding.get("image", {}).get("value", "")
        description = binding.get("description", {}).get("value", "")
        
        # 转换 Wikimedia 图片 URL 为可直接访问的缩略图 URL
        if image_url and "commons.wikimedia.org" in image_url:
            # 将 http 升级为 https，并添加 width 参数请求缩略图
            image_url = image_url.replace("http://", "https://")
            thumb_url = image_url + "?width=500"
            # 提前解析 302 重定向，获取最终的 upload.wikimedia.org URL
            # 避免 Web 代理时再跟随重定向导致超时
            try:
                req = urllib.request.Request(thumb_url, method='HEAD')
                req.add_header('User-Agent', 'SportsAvatarDownloader/1.0')
                with urllib.request.urlopen(req, timeout=15) as resp:
                    final_url = resp.geturl()
                    if final_url and final_url.startswith("https://upload.wikimedia.org"):
                        image_url = final_url
                    else:
                        image_url = thumb_url
            except Exception:
                image_url = thumb_url
        
        athlete_info = {
            "id": person_id,
            "name": person_label,
            "sport": "Unknown",
            "team": description.split(",")[0].strip() if description else "Unknown",
            "nationality": "Unknown",
            "headshot": image_url,
            "wikidata_url": person_url,
        }
        
        athletes.append(athlete_info)
    
    # 对没有图片的运动员，尝试从 Wikipedia 页面补充
    athletes = _enhance_with_wikipedia_images(athletes)
    
    return athletes


def search_athlete_by_sport(player_name, sport_zh):
    """
    按运动类型搜索运动员（更精确）
    
    参数:
        player_name: 运动员名字
        sport_zh: 运动类型中文（如 "羽毛球"）
    
    返回:
        运动员列表
    """
    # 运动类型中英文映射
    sport_map = {
        "羽毛球": "badminton",
        "乒乓球": "table tennis",
        "网球": "tennis",
        "足球": "association football",
        "篮球": "basketball",
        "棒球": "baseball",
        "冰球": "ice hockey",
    }
    
    sport_en = sport_map.get(sport_zh, sport_zh)
    
    # SPARQL 查询：指定运动类型
    sparql_query = f'''
    SELECT DISTINCT ?person ?personLabel ?image ?sportLabel ?description WHERE {{
      {{
        ?person rdfs:label "{player_name}"@en .
      }}
      UNION
      {{
        ?person rdfs:label "{player_name}"@zh .
      }}
      ?person wdt:P31 wd:Q5 .
      ?person wdt:P106 ?occupation .
      ?occupation wdt:P279* wd:Q937857 .
      ?person wdt:P641 ?sport .
      ?sport rdfs:label "{sport_en}"@en .
      OPTIONAL {{ ?person wdt:P18 ?image . }}
      OPTIONAL {{ ?person schema:description ?description . FILTER(LANG(?description) = "en") }}
      SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en,zh" . }}
    }}
    LIMIT 10
    '''
    
    encoded_query = urllib.parse.quote(sparql_query)
    url = f"{WIKIDATA_SPARQL_URL}?query={encoded_query}&format=json"
    
    data = http_get_json(url)
    if not data or "results" not in data:
        return []
    
    athletes = []
    bindings = data["results"].get("bindings", [])
    
    for binding in bindings:
        person_url = binding.get("person", {}).get("value", "")
        person_id = person_url.split("/")[-1] if person_url else ""
        
        person_label = binding.get("personLabel", {}).get("value", "Unknown")
        image_url = binding.get("image", {}).get("value", "")
        description = binding.get("description", {}).get("value", "")
        
        athlete_info = {
            "id": person_id,
            "name": person_label,
            "sport": sport_zh,
            "team": description.split(",")[0].strip() if description else "Unknown",
            "nationality": "Unknown",
            "headshot": image_url,
            "wikidata_url": person_url,
        }
        
        if image_url:
            athletes.append(athlete_info)
    
    # 对没有图片的运动员，尝试从 Wikipedia 页面补充
    athletes = _enhance_with_wikipedia_images(athletes)
    
    return athletes


def _extract_infobox_image(url):
    """
    从 Wikipedia 页面提取 infobox 中的第一张图片
    返回可直接访问的图片 URL（500px 缩略图）
    """
    try:
        req = urllib.request.Request(url)
        req.add_header('User-Agent', 'SportsAvatarDownloader/1.0')
        with urllib.request.urlopen(req, timeout=10) as resp:
            html = resp.read().decode('utf-8', errors='ignore')

            # 查找 infobox 表格
            infobox_match = re.search(
                r'<table[^>]*class="[^"]*infobox[^"]*"[^>]*>(.*?)</table>',
                html, re.DOTALL | re.IGNORECASE
            )
            if not infobox_match:
                return None

            # 提取 infobox 中的第一张图片 src
            img_match = re.search(
                r'<img[^>]*src="([^"]+)"',
                infobox_match.group(1), re.IGNORECASE
            )
            if not img_match:
                return None

            src = img_match.group(1)

            # 补全协议（// -> https://）
            if src.startswith('//'):
                src = 'https:' + src

            # 将 250px 缩略图升级为 500px（如果可用）
            if '/thumb/' in src and 'px-' in src:
                src = re.sub(r'/\d+px-', '/500px-', src)

            return src
    except Exception:
        return None


def fetch_wikipedia_image(player_name):
    """
    从 Wikipedia 页面抓取运动员图片
    先尝试中文页面，再尝试英文页面

    参数:
        player_name: 运动员名字（英文或中文）

    返回:
        图片 URL 或 None
    """
    # 先尝试中文页面（对中国运动员效果更好）
    zh_url = f"https://zh.wikipedia.org/wiki/{urllib.parse.quote(player_name)}"
    img = _extract_infobox_image(zh_url)
    if img:
        return img

    # 再尝试英文页面
    en_name = player_name.replace(' ', '_')
    en_url = f"https://en.wikipedia.org/wiki/{urllib.parse.quote(en_name)}"
    img = _extract_infobox_image(en_url)
    if img:
        return img

    return None


def _enhance_with_wikipedia_images(athletes):
    """
    对 Wikidata 搜索结果中没有图片的运动员，
    尝试从 Wikipedia 页面补充图片。
    最多只补充前 3 个没有图片的结果，避免过多请求。
    """
    enhanced_count = 0
    for athlete in athletes:
        if athlete.get("headshot"):
            continue
        if enhanced_count >= 3:
            break

        wiki_img = fetch_wikipedia_image(athlete["name"])
        if wiki_img:
            athlete["headshot"] = wiki_img
            athlete["_image_from_wiki"] = True
            enhanced_count += 1
    return athletes


def format_athletes_for_display(athletes):
    """
    格式化运动员列表用于显示
    保持与其他 API 相同的格式
    """
    formatted = []

    for athlete in athletes:
        source = "Wikidata"
        if athlete.get("_image_from_wiki"):
            source = "Wikidata+Wikipedia"

        formatted.append({
            "strPlayer": athlete["name"],
            "strSport": athlete["sport"],
            "strTeam": athlete["team"],
            "strNationality": athlete["nationality"],
            "strThumb": athlete["headshot"],
            "strCutout": athlete["headshot"],
            "strRender": None,
            "api_source": source,
            "wikidata_url": athlete.get("wikidata_url", ""),
        })

    return formatted
