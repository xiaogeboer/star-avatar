"""
体育明星头像下载工具 - 多 API 支持
支持 TheSportsDB（主）、ESPN（备）和 Wikidata（补充）
带缓存优化，提升搜索速度
"""

import os
import sys
import json
import subprocess
import urllib.parse
import time

# 导入 API 模块
try:
    import espn_api
except ImportError:
    print("警告: 无法导入 espn_api 模块，ESPN 备用功能不可用")
    espn_api = None

try:
    import wikidata_api
except ImportError:
    print("警告: 无法导入 wikidata_api 模块，Wikidata 功能不可用")
    wikidata_api = None

# 导入缓存管理
try:
    from cache_manager import get_cache
except ImportError:
    print("警告: 无法导入 cache_manager 模块，缓存功能不可用")
    get_cache = None

# TheSportsDB 免费 API (测试用 key 为 3)
# 如果你有 Patreon 赞助 key，可以替换下面的 API_KEY
API_KEY = "3"
BASE_URL = f"https://www.thesportsdb.com/api/v1/json/{API_KEY}"

# 默认下载目录
DOWNLOAD_DIR = "sports_avatars"


def http_get_json(url):
    """使用 curl 发送 GET 请求并返回 JSON 数据"""
    try:
        result = subprocess.run(
            ["curl", "-s", "-f", "--max-time", "15", url],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            print(f"  请求失败 (curl 返回码: {result.returncode})")
            return None
        return json.loads(result.stdout)
    except FileNotFoundError:
        print("错误: 未找到 curl 命令，请确保系统已安装 curl")
        sys.exit(1)
    except json.JSONDecodeError:
        print("  API 返回数据解析失败")
        return None


def download_file(url, save_path):
    """使用 curl 下载文件"""
    try:
        result = subprocess.run(
            ["curl", "-s", "-L", "-f", "--max-time", "30", "-o", save_path, url],
            capture_output=True,
            text=True,
        )
        return result.returncode == 0
    except FileNotFoundError:
        print("错误: 未找到 curl 命令")
        return False


def search_player(player_name):
    """通过球员名字搜索球员信息（多 API 降级 + 缓存）"""
    start_time = time.time()
    cache = get_cache() if get_cache else None
    
    # 1. 尝试 TheSportsDB（带缓存）
    if cache:
        cached = cache.get(player_name, "TheSportsDB")
        if cached:
            print(f"  从缓存找到结果 (TheSportsDB)")
            return cached
    
    encoded_name = urllib.parse.quote(player_name)
    url = f"{BASE_URL}/searchplayers.php?p={encoded_name}"
    
    print(f"正在搜索: {player_name}")
    
    data = http_get_json(url)
    if data and data.get("player"):
        players = data["player"]
        # 验证搜索结果是否精确匹配
        matched_players = []
        search_name = player_name.lower().strip()
        search_words = search_name.split()
        
        for player in players:
            player_name_db = player.get("strPlayer", "").lower().strip()
            
            # 完全匹配（忽略大小写）
            if search_name == player_name_db:
                matched_players.append(player)
                continue
            
            # 单字搜索：使用包含匹配
            if len(search_words) == 1:
                if search_name in player_name_db:
                    matched_players.append(player)
                continue
            
            # 多字搜索：使用单词边界匹配
            # 例如 "Lin Dan" 应该匹配 "Lin Dan"，但不匹配 "Daniel Lincoln"
            import re
            pattern = r'\b' + r'\b.*\b'.join(re.escape(word) for word in search_words) + r'\b'
            if re.search(pattern, player_name_db):
                matched_players.append(player)
        
        if matched_players:
            elapsed = time.time() - start_time
            print(f"  找到结果 (TheSportsDB) [{elapsed:.2f}s]")
            for player in matched_players:
                player["api_source"] = "TheSportsDB"
            
            if cache:
                cache.set(player_name, "TheSportsDB", matched_players)
            
            return matched_players
        else:
            print(f"  TheSportsDB 无精确匹配，继续搜索...")
    
    print(f"  TheSportsDB 未找到，尝试 ESPN...")
    
    # 2. 尝试 ESPN API（带缓存）
    if espn_api:
        if cache:
            cached = cache.get(player_name, "ESPN")
            if cached:
                print(f"  从缓存找到结果 (ESPN)")
                return cached
        
        athletes = espn_api.search_athlete(player_name)
        if athletes:
            elapsed = time.time() - start_time
            print(f"  ESPN 找到 {len(athletes)} 位运动员 [{elapsed:.2f}s]")
            formatted = espn_api.format_athletes_for_display(athletes)
            
            # 缓存结果
            if cache:
                cache.set(player_name, "ESPN", formatted)
            
            return formatted
    
    print(f"  ESPN 未找到，尝试 Wikidata...")
    
    # 3. 尝试 Wikidata（带缓存）
    if wikidata_api:
        if cache:
            cached = cache.get(player_name, "Wikidata")
            if cached:
                print(f"  从缓存找到结果 (Wikidata)")
                return cached
        
        athletes = wikidata_api.search_athlete_wikidata(player_name)
        if athletes:
            elapsed = time.time() - start_time
            print(f"  Wikidata 找到 {len(athletes)} 位运动员 [{elapsed:.2f}s]")
            formatted = wikidata_api.format_athletes_for_display(athletes)
            
            # 缓存结果
            if cache:
                cache.set(player_name, "Wikidata", formatted)
            
            return formatted
    
    elapsed = time.time() - start_time
    print(f"  所有 API 均未找到结果 [{elapsed:.2f}s]")
    return None


def display_players(players):
    """展示搜索到的球员列表"""
    print(f"\n找到 {len(players)} 位球员:")
    print("-" * 60)
    for i, player in enumerate(players, 1):
        name = player.get("strPlayer", "未知")
        sport = player.get("strSport", "未知")
        team = player.get("strTeam", "未知")
        nationality = player.get("strNationality", "未知")
        has_thumb = "有" if player.get("strThumb") else "无"
        has_cutout = "有" if player.get("strCutout") else "无"
        api_source = player.get("api_source", "TheSportsDB")
        print(f"  [{i}] {name} | 运动: {sport} | 球队: {team} | 国籍: {nationality}")
        print(f"      缩略图: {has_thumb} | 抠图头像: {has_cutout} | 来源: {api_source}")
    print("-" * 60)


def get_image_urls(player):
    """获取球员的所有可用图片 URL"""
    images = {}

    # 缩略图（最常用的头像）
    if player.get("strThumb"):
        images["thumb"] = player["strThumb"]

    # 抠图头像（透明背景）
    if player.get("strCutout"):
        images["cutout"] = player["strCutout"]

    # 渲染图
    if player.get("strRender"):
        images["render"] = player["strRender"]

    # 球迷艺术图
    for i in range(1, 5):
        key = f"strFanart{i}"
        if player.get(key):
            images[f"fanart{i}"] = player[key]

    # 横幅图
    if player.get("strBanner"):
        images["banner"] = player["strBanner"]

    return images


def sanitize_filename(name):
    """清理文件名中的非法字符"""
    invalid_chars = '<>:"/\\|?*'
    for ch in invalid_chars:
        name = name.replace(ch, "_")
    return name


def download_player_avatar(player, download_dir, image_type="thumb"):
    """下载指定球员的头像"""
    images = get_image_urls(player)

    if not images:
        print("  该球员没有可用的图片")
        return False

    # 如果指定类型不可用，尝试备选
    if image_type not in images:
        available = list(images.keys())
        print(f"  '{image_type}' 类型不可用，可用类型: {available}")
        image_type = available[0]
        print(f"  自动选择: {image_type}")

    url = images[image_type]
    player_name = sanitize_filename(player.get("strPlayer", "unknown"))

    # 从 URL 获取文件扩展名
    ext = os.path.splitext(urllib.parse.urlparse(url).path)[1]
    if not ext:
        ext = ".jpg"

    filename = f"{player_name}_{image_type}{ext}"
    save_path = os.path.join(download_dir, filename)

    print(f"  正在下载: {url}")
    print(f"  保存到: {save_path}")

    if download_file(url, save_path):
        file_size = os.path.getsize(save_path)
        print(f"  下载成功! 文件大小: {file_size / 1024:.1f} KB")
        return True
    else:
        print("  下载失败")
        return False


def interactive_mode():
    """交互式模式"""
    print("=" * 60)
    print("  体育明星头像下载工具 - 多 API 支持")
    print("  API: TheSportsDB -> ESPN -> Wikidata")
    print("  (输入 'q' 或 'quit' 退出)")
    print("=" * 60)

    # 创建下载目录
    os.makedirs(DOWNLOAD_DIR, exist_ok=True)
    print(f"下载目录: {os.path.abspath(DOWNLOAD_DIR)}\n")

    while True:
        player_name = input("\n请输入球员英文名 (如 Messi, Ronaldo, LeBron James): ").strip()

        if player_name.lower() in ("q", "quit", "exit"):
            print("再见!")
            break

        if not player_name:
            continue

        players = search_player(player_name)
        if not players:
            continue

        display_players(players)

        # 选择球员
        if len(players) == 1:
            choice = 1
        else:
            try:
                choice_input = input(f"\n请选择球员编号 [1-{len(players)}] (默认1): ").strip()
                choice = int(choice_input) if choice_input else 1
                if choice < 1 or choice > len(players):
                    print("编号无效")
                    continue
            except ValueError:
                print("请输入有效数字")
                continue

        selected = players[choice - 1]
        images = get_image_urls(selected)

        if not images:
            print("该球员没有可用的图片")
            continue

        # 显示可用图片类型
        print(f"\n可用图片类型:")
        img_types = list(images.keys())
        for i, t in enumerate(img_types, 1):
            print(f"  [{i}] {t}")
        print(f"  [0] 全部下载")

        try:
            type_input = input(f"\n选择要下载的类型 [0-{len(img_types)}] (默认1): ").strip()
            type_choice = int(type_input) if type_input else 1
        except ValueError:
            type_choice = 1

        print()
        if type_choice == 0:
            # 下载所有类型
            for img_type in img_types:
                download_player_avatar(selected, DOWNLOAD_DIR, img_type)
        elif 1 <= type_choice <= len(img_types):
            download_player_avatar(selected, DOWNLOAD_DIR, img_types[type_choice - 1])
        else:
            print("选择无效")


def batch_mode(names):
    """批量下载模式"""
    os.makedirs(DOWNLOAD_DIR, exist_ok=True)
    print(f"批量下载模式 - 共 {len(names)} 个球员")
    print(f"下载目录: {os.path.abspath(DOWNLOAD_DIR)}\n")

    success_count = 0
    for name in names:
        print(f"\n{'='*40}")
        players = search_player(name)
        if players:
            # 默认选第一个结果，下载缩略图
            if download_player_avatar(players[0], DOWNLOAD_DIR, "thumb"):
                success_count += 1

    print(f"\n{'='*40}")
    print(f"下载完成: 成功 {success_count}/{len(names)}")


def main():
    if len(sys.argv) > 1:
        # 命令行参数模式
        if sys.argv[1] in ("-h", "--help"):
            print("用法:")
            print(f"  python {sys.argv[0]}                  # 交互式模式")
            print(f"  python {sys.argv[0]} <球员名>         # 直接搜索并下载")
            print(f"  python {sys.argv[0]} <名1> <名2> ...  # 批量下载")
            print()
            print("示例:")
            print(f"  python {sys.argv[0]} Messi")
            print(f'  python {sys.argv[0]} "LeBron James" Ronaldo Neymar')
            return

        names = sys.argv[1:]
        if len(names) == 1:
            # 单个球员 - 搜索并显示结果后下载
            os.makedirs(DOWNLOAD_DIR, exist_ok=True)
            players = search_player(names[0])
            if players:
                display_players(players)
                download_player_avatar(players[0], DOWNLOAD_DIR, "thumb")
        else:
            batch_mode(names)
    else:
        interactive_mode()


if __name__ == "__main__":
    main()
