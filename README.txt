======================================================
  Sports Avatar Downloader
  体育明星头像下载工具
======================================================

[Requirements / 系统要求]

  - Python 3.6+   (macOS/Linux 自带, Windows 需安装)
  - curl           (macOS/Linux 自带, Windows 10+ 自带)

  无需安装任何第三方 Python 库!


[Features / 功能特性]

  - 多 API 数据源: TheSportsDB + ESPN + Wikidata (+ Wikipedia 图片补充)
  - 智能降级: TheSportsDB 优先，未命中自动尝试 ESPN，再尝试 Wikidata
  - Wikipedia 图片补充: 当 Wikidata 搜到运动员但没图片时，自动从
    Wikipedia 中文/英文页面抓取 infobox 头像（中国大陆网络环境下更可靠）
  - 搜索缓存: 自动缓存搜索结果，提升重复查询速度
  - 纯 Python 标准库实现，零依赖


[API 说明]

  TheSportsDB  - 主数据源，专业体育图片库
  ESPN         - 备用数据源，覆盖全球主流运动员
  Wikidata     - 补充数据源，覆盖小众运动员
  Wikipedia    - 图片补充，当 Wikidata 无图时自动抓取 Wikipedia 页面头像


[Quick Start / 快速启动]

  macOS:
    双击 start_mac.command 文件即可
    (首次运行可能需要右键 -> 打开 -> 允许)

  Windows:
    双击 start_windows.bat 文件即可

  浏览器会自动打开 Web 界面。


[Manual Start / 手动启动]

  打开终端/命令提示符，进入本文件夹，运行:

    python3 web_server.py        (macOS/Linux)
    python web_server.py         (Windows)

  然后在浏览器访问: http://localhost:8888


[Command Line / 命令行模式]

  本工具也支持纯命令行使用，无需启动 Web 服务:

    python3 download_sports_avatar.py                    # 交互式模式
    python3 download_sports_avatar.py Messi              # 搜索并下载
    python3 download_sports_avatar.py "LeBron James" Ronaldo Neymar  # 批量下载

  更多帮助:
    python3 download_sports_avatar.py -h


[Files / 文件说明]

  web_server.py              Web UI 服务器（多 API 并行查询）
  index.html                 Web 界面页面
  download_sports_avatar.py  命令行工具（多 API 降级查询）
  espn_api.py                ESPN API 模块
  wikidata_api.py            Wikidata/Wikipedia API 模块
  cache_manager.py           搜索缓存模块
  start_mac.command          macOS 启动脚本
  start_windows.bat          Windows 启动脚本
  sports_avatars/            下载的头像保存目录 (自动创建)
  .cache/                    搜索缓存目录 (自动创建)


[Troubleshooting / 常见问题]

  Q: 端口 8888 被占用?
  A: 打开 web_server.py, 修改顶部的 PORT = 8888 为其他端口号

  Q: 提示找不到 curl?
  A: macOS/Linux 通常自带 curl
     Windows 10 及以上版本自带 curl
     旧版 Windows 请安装 curl: https://curl.se/download.html

  Q: macOS 双击 .command 文件提示 "无法打开"?
  A: 右键点击该文件 -> 打开 -> 再点 "打开"
     或在 系统设置 -> 隐私与安全 中允许

  Q: 搜索不到球员?
  A: 请使用球员的英文名搜索，如 "Messi" 而非 "梅西"
     系统会自动尝试 TheSportsDB -> ESPN -> Wikidata 三个数据源
     Wikidata 还会自动从 Wikipedia 中文/英文页面补充图片

  Q: Wikipedia 图片和 Wikidata 图片有什么区别?
  A: 两者使用相同的 Wikimedia 图片库，但 Wikipedia 页面可能有额外的
     头像图片未被 Wikidata 收录。搜索结果的 "Wikipedia 补充" 标签
     表示该图片来自 Wikipedia 页面抓取。
