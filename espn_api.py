"""
ESPN API 体育明星头像下载模块
ESPN API 是免费的体育数据接口，覆盖几乎所有主流运动
无需 API Key，直接调用
"""

import json
import subprocess
import urllib.parse


# ESPN API 基础配置
ESPN_SEARCH_URL = "https://site.web.api.espn.com/apis/search/v2"  # 搜索 API
ESPN_BASE_URL = "https://site.api.espn.com/apis/site/v2/sports"  # 数据 API

# 运动类型映射
SPORT_TYPES = {
    "football": "soccer",  # 足球
    "basketball": "basketball",  # 篮球
    "tennis": "tennis",  # 网球
    "baseball": "baseball",  # 棒球
    "hockey": "hockey",  # 冰球
    "american-football": "football",  # 美式足球
    "cricket": "cricket",  # 板球
    "golf": "golf",  # 高尔夫
    "badminton": "badminton",  # 羽毛球
    "table-tennis": "table-tennis",  # 乒乓球
}


def http_get_json(url):
    """使用 curl 发送 GET 请求并返回 JSON 数据"""
    try:
        result = subprocess.run(
            ["curl", "-s", "-f", "--max-time", "15", url],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            return None
        return json.loads(result.stdout)
    except (FileNotFoundError, json.JSONDecodeError):
        return None


def search_athlete(player_name, sport=None):
    """
    通过运动员名字搜索 ESPN 运动员信息
    
    参数:
        player_name: 运动员英文名
        sport: 运动类型（可选，不指定则搜索所有类型）
    
    返回:
        运动员列表，每个运动员包含:
        - id: 运动员 ID
        - name: 姓名
        - sport: 运动类型
        - team: 所属团队
        - nationality: 国籍
        - headshot: 头像 URL
    """
    # 使用 ESPN 全局搜索 API
    encoded_name = urllib.parse.quote(player_name)
    search_url = f"{ESPN_SEARCH_URL}?query={encoded_name}&type=player&limit=20"
    
    if sport:
        search_url += f"&sport={sport}"
    
    data = http_get_json(search_url)
    if not data or "results" not in data:
        return []
    
    athletes = []
    for result in data["results"]:
        if result.get("type") != "player":
            continue
        
        # 球员数据在 contents 数组中
        contents = result.get("contents", [])
        for athlete in contents:
            # 提取运动员信息
            headshot_url = None
            if "image" in athlete and athlete["image"]:
                headshot_url = athlete["image"].get("default", "")
                # 如果没有图片，跳过这个运动员
                if not headshot_url:
                    continue
            
            athlete_info = {
                "id": athlete.get("id", ""),
                "name": athlete.get("displayName", "Unknown"),
                "sport": athlete.get("sport", "Unknown"),
                "team": athlete.get("subtitle", "Unknown"),
                "nationality": "Unknown",  # ESPN 搜索 API 不返回国籍
                "headshot": headshot_url,
                "description": athlete.get("description", ""),
            }
            
            athletes.append(athlete_info)
    
    return athletes


def get_athlete_details(athlete_id, sport_type="soccer"):
    """
    获取运动员详细信息
    
    参数:
        athlete_id: 运动员 ID
        sport_type: 运动类型
    
    返回:
        运动员详细信息字典
    """
    url = f"{ESPN_BASE_URL}/{sport_type}/athletes/{athlete_id}"
    data = http_get_json(url)
    
    if not data or "athlete" not in data:
        return None
    
    athlete = data["athlete"]
    
    # 获取头像 URL
    headshot_url = None
    if "headshot" in athlete:
        headshot_url = athlete["headshot"].get("href", "")
        if headshot_url:
            headshot_url = headshot_url.replace("/160x160/", "/500x500/")
    
    return {
        "id": athlete.get("id", ""),
        "name": athlete.get("fullName", athlete.get("displayName", "Unknown")),
        "sport": sport_type,
        "team": athlete.get("team", {}).get("displayName", "Unknown"),
        "nationality": athlete.get("nationality", "Unknown"),
        "headshot": headshot_url,
        "age": athlete.get("age", ""),
        "height": athlete.get("height", ""),
        "weight": athlete.get("weight", ""),
    }


def format_athletes_for_display(athletes):
    """
    格式化运动员列表用于显示
    保持与 TheSportsDB 相同的格式
    
    返回:
        格式化后的运动员列表
    """
    formatted = []
    
    for athlete in athletes:
        formatted.append({
            "strPlayer": athlete["name"],
            "strSport": translate_sport(athlete["sport"]),
            "strTeam": athlete["team"],
            "strNationality": athlete["nationality"],
            "strThumb": athlete["headshot"],
            "strCutout": athlete["headshot"],  # ESPN 没有抠图，使用同一张
            "strRender": None,
            "api_source": "ESPN",  # 标记数据来源
        })
    
    return formatted


def translate_sport(sport_code):
    """翻译运动类型代码为中文"""
    sport_map = {
        "soccer": "Soccer",
        "basketball": "Basketball",
        "tennis": "Tennis",
        "baseball": "Baseball",
        "hockey": "Ice Hockey",
        "football": "Football",
        "cricket": "Cricket",
        "golf": "Golf",
        "badminton": "Badminton",
        "table-tennis": "Table Tennis",
    }
    return sport_map.get(sport_code, sport_code)
