"""
搜索缓存模块
用于缓存 API 搜索结果，减少重复请求，提升响应速度
"""

import json
import os
import time
from pathlib import Path


class SearchCache:
    """搜索缓存管理器"""
    
    def __init__(self, cache_dir=None, max_age=3600):
        """
        初始化缓存
        
        参数:
            cache_dir: 缓存目录路径
            max_age: 缓存最大有效期（秒），默认 1 小时
        """
        if cache_dir is None:
            cache_dir = Path(__file__).parent / ".cache"
        
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(exist_ok=True)
        self.max_age = max_age
        self.cache_file = self.cache_dir / "search_cache.json"
        self.cache = self._load_cache()
    
    def _load_cache(self):
        """加载缓存文件"""
        if self.cache_file.exists():
            try:
                with open(self.cache_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError):
                return {}
        return {}
    
    def _save_cache(self):
        """保存缓存到文件"""
        try:
            with open(self.cache_file, 'w', encoding='utf-8') as f:
                json.dump(self.cache, f, ensure_ascii=False, indent=2)
        except IOError:
            pass
    
    def _make_key(self, player_name, api_name):
        """生成缓存键"""
        return f"{api_name}:{player_name.strip().lower()}"
    
    def get(self, player_name, api_name):
        """
        获取缓存的搜索结果
        
        参数:
            player_name: 运动员名字
            api_name: API 名称（TheSportsDB, ESPN, Wikidata）
        
        返回:
            缓存的结果，如果不存在或过期则返回 None
        """
        key = self._make_key(player_name, api_name)
        
        if key in self.cache:
            cached_data = self.cache[key]
            timestamp = cached_data.get("timestamp", 0)
            
            # 检查是否过期
            if time.time() - timestamp < self.max_age:
                return cached_data.get("data")
            else:
                # 过期，删除
                del self.cache[key]
        
        return None
    
    def set(self, player_name, api_name, data):
        """
        缓存搜索结果
        
        参数:
            player_name: 运动员名字
            api_name: API 名称
            data: 要缓存的数据
        """
        key = self._make_key(player_name, api_name)
        self.cache[key] = {
            "data": data,
            "timestamp": time.time()
        }
        self._save_cache()
    
    def clear(self):
        """清空所有缓存"""
        self.cache = {}
        if self.cache_file.exists():
            self.cache_file.unlink()
    
    def clear_expired(self):
        """清理过期缓存"""
        current_time = time.time()
        expired_keys = []
        
        for key, cached_data in self.cache.items():
            timestamp = cached_data.get("timestamp", 0)
            if current_time - timestamp >= self.max_age:
                expired_keys.append(key)
        
        for key in expired_keys:
            del self.cache[key]
        
        if expired_keys:
            self._save_cache()
        
        return len(expired_keys)
    
    def get_stats(self):
        """获取缓存统计信息"""
        total = len(self.cache)
        current_time = time.time()
        valid = 0
        expired = 0
        
        for cached_data in self.cache.values():
            timestamp = cached_data.get("timestamp", 0)
            if current_time - timestamp < self.max_age:
                valid += 1
            else:
                expired += 1
        
        return {
            "total": total,
            "valid": valid,
            "expired": expired,
            "cache_file_size": self.cache_file.stat().st_size if self.cache_file.exists() else 0
        }


# 全局缓存实例
_search_cache = None


def get_cache():
    """获取全局缓存实例"""
    global _search_cache
    if _search_cache is None:
        _search_cache = SearchCache()
    return _search_cache
