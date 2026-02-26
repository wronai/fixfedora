#!/usr/bin/env python3
"""
Disk Analyzer Module for fixOS
Analyzes disk usage and groups cleanup causes
"""

import os
import shutil
import json
from pathlib import Path
from typing import Dict, List, Any, Tuple
from datetime import datetime, timedelta


class DiskAnalyzer:
    """Analyzes disk usage and provides cleanup suggestions"""
    
    def __init__(self, base_path: str = "/"):
        self.base_path = Path(base_path)
        self.cache_patterns = [
            ".cache", "__pycache__", "node_modules", ".npm", 
            ".pip", "cache", "Cache", ".gradle", ".maven", ".cargo"
        ]
        self.log_patterns = [
            ".log", "logs", "Logs", "*.log", "*.out", "*.err"
        ]
        self.temp_patterns = [
            "tmp", "temp", ".tmp", "Temp", "/tmp", "/var/tmp"
        ]
        
    def analyze_disk_usage(self, path: str = None) -> Dict[str, Any]:
        """Comprehensive disk usage analysis"""
        if path is None:
            path = str(self.base_path)
            
        path = Path(path)
        if not path.exists():
            return {"error": f"Path {path} does not exist"}
            
        try:
            stat = shutil.disk_usage(path)
            total_gb = stat.total / (1024**3)
            used_gb = stat.used / (1024**3)
            free_gb = stat.free / (1024**3)
            usage_percent = (used_gb / total_gb) * 100
            
            analysis = {
                "path": str(path),
                "total_gb": round(total_gb, 2),
                "used_gb": round(used_gb, 2), 
                "free_gb": round(free_gb, 2),
                "usage_percent": round(usage_percent, 2),
                "status": self._get_disk_status(usage_percent),
                "large_files": self.get_large_files(path),
                "cache_dirs": self.get_cache_dirs(path),
                "log_dirs": self.get_log_dirs(path),
                "temp_dirs": self.get_temp_dirs(path),
                "suggestions": self.suggest_cleanup_actions(path),
                "timestamp": datetime.now().isoformat()
            }
            
            return analysis
            
        except Exception as e:
            return {"error": f"Failed to analyze {path}: {str(e)}"}
    
    def _get_disk_status(self, usage_percent: float) -> str:
        """Get disk status based on usage percentage"""
        if usage_percent >= 95:
            return "critical"
        elif usage_percent >= 85:
            return "warning" 
        elif usage_percent >= 70:
            return "moderate"
        else:
            return "healthy"
    
    def get_large_files(self, path: Path, min_size_mb: int = 100, max_files: int = 20) -> List[Dict]:
        """Find large files"""
        large_files = []
        
        try:
            for file_path in path.rglob("*"):
                if file_path.is_file():
                    try:
                        size_mb = file_path.stat().st_size / (1024**2)
                        if size_mb >= min_size_mb:
                            large_files.append({
                                "path": str(file_path),
                                "size_mb": round(size_mb, 2),
                                "size_gb": round(size_mb / 1024, 3),
                                "modified": datetime.fromtimestamp(file_path.stat().st_mtime).isoformat(),
                                "category": self._categorize_file(file_path)
                            })
                    except (OSError, PermissionError):
                        continue
                        
                # Limit results to avoid excessive scanning
                if len(large_files) >= max_files:
                    break
                    
        except Exception as e:
            pass
            
        # Sort by size (largest first)
        large_files.sort(key=lambda x: x["size_mb"], reverse=True)
        return large_files[:max_files]
    
    def get_cache_dirs(self, path: Path, max_dirs: int = 15) -> List[Dict]:
        """Find cache directories"""
        cache_dirs = []
        
        try:
            for dir_path in path.rglob("*"):
                if dir_path.is_dir():
                    dir_name = dir_path.name.lower()
                    if any(pattern in dir_name for pattern in self.cache_patterns):
                        try:
                            size_mb = self._get_dir_size_mb(dir_path)
                            if size_mb > 10:  # Only include significant cache dirs
                                cache_dirs.append({
                                    "path": str(dir_path),
                                    "size_mb": round(size_mb, 2),
                                    "size_gb": round(size_mb / 1024, 3),
                                    "files_count": len(list(dir_path.rglob("*"))) if size_mb < 1000 else "many",
                                    "cache_type": self._identify_cache_type(dir_path)
                                })
                        except (OSError, PermissionError):
                            continue
                            
                if len(cache_dirs) >= max_dirs:
                    break
                    
        except Exception:
            pass
            
        cache_dirs.sort(key=lambda x: x["size_mb"], reverse=True)
        return cache_dirs
    
    def get_log_dirs(self, path: Path, max_dirs: int = 10) -> List[Dict]:
        """Find log directories"""
        log_dirs = []
        
        try:
            for dir_path in path.rglob("*"):
                if dir_path.is_dir():
                    dir_name = dir_path.name.lower()
                    if any(pattern in dir_name for pattern in ["log", "logs"]):
                        try:
                            size_mb = self._get_dir_size_mb(dir_path)
                            if size_mb > 5:  # Only include significant log dirs
                                log_dirs.append({
                                    "path": str(dir_path),
                                    "size_mb": round(size_mb, 2),
                                    "size_gb": round(size_mb / 1024, 3),
                                    "oldest_log": self._get_oldest_file_date(dir_path),
                                    "newest_log": self._get_newest_file_date(dir_path)
                                })
                        except (OSError, PermissionError):
                            continue
                            
                if len(log_dirs) >= max_dirs:
                    break
                    
        except Exception:
            pass
            
        log_dirs.sort(key=lambda x: x["size_mb"], reverse=True)
        return log_dirs
    
    def get_temp_dirs(self, path: Path, max_dirs: int = 10) -> List[Dict]:
        """Find temporary directories"""
        temp_dirs = []
        
        try:
            for dir_path in path.rglob("*"):
                if dir_path.is_dir():
                    dir_name = dir_path.name.lower()
                    if any(pattern in dir_name for pattern in self.temp_patterns):
                        try:
                            size_mb = self._get_dir_size_mb(dir_path)
                            if size_mb > 5:
                                temp_dirs.append({
                                    "path": str(dir_path),
                                    "size_mb": round(size_mb, 2),
                                    "size_gb": round(size_mb / 1024, 3),
                                    "temp_type": self._identify_temp_type(dir_path)
                                })
                        except (OSError, PermissionError):
                            continue
                            
                if len(temp_dirs) >= max_dirs:
                    break
                    
        except Exception:
            pass
            
        temp_dirs.sort(key=lambda x: x["size_mb"], reverse=True)
        return temp_dirs
    
    def suggest_cleanup_actions(self, path: Path) -> List[Dict]:
        """Generate cleanup suggestions using heuristics"""
        suggestions = []
        
        try:
            # Get analysis data
            large_files = self.get_large_files(path, min_size_mb=500, max_files=10)
            cache_dirs = self.get_cache_dirs(path, max_dirs=10)
            log_dirs = self.get_log_dirs(path, max_dirs=8)
            temp_dirs = self.get_temp_dirs(path, max_dirs=8)
            
            # Cache cleanup suggestions
            for cache in cache_dirs[:5]:
                if cache["size_mb"] > 100:
                    suggestions.append({
                        "type": "cache_cleanup",
                        "priority": "high" if cache["size_mb"] > 500 else "medium",
                        "path": cache["path"],
                        "size_gb": cache["size_gb"],
                        "description": f"Clear {cache['cache_type']} cache",
                        "command": f"rm -rf {cache['path']}",
                        "safe": cache["cache_type"] in ["npm", "pip", "gradle", "maven"],
                        "impact": "high"
                    })
            
            # Log cleanup suggestions  
            for log_dir in log_dirs[:3]:
                if log_dir["size_mb"] > 50:
                    suggestions.append({
                        "type": "log_cleanup",
                        "priority": "medium",
                        "path": log_dir["path"],
                        "size_gb": log_dir["size_gb"],
                        "description": f"Clean old log files",
                        "command": f"find {log_dir['path']} -name '*.log' -mtime +30 -delete",
                        "safe": True,
                        "impact": "medium"
                    })
            
            # Temp directory cleanup
            for temp_dir in temp_dirs[:3]:
                if temp_dir["size_mb"] > 20:
                    suggestions.append({
                        "type": "temp_cleanup",
                        "priority": "high",
                        "path": temp_dir["path"],
                        "size_gb": temp_dir["size_gb"],
                        "description": f"Clean {temp_dir['temp_type']} temporary files",
                        "command": f"rm -rf {temp_dir['path']}/*",
                        "safe": temp_dir["temp_type"] in ["system_temp", "app_temp"],
                        "impact": "medium"
                    })
            
            # Large file suggestions
            for file_info in large_files[:3]:
                if file_info["size_gb"] > 1.0:
                    suggestions.append({
                        "type": "large_file",
                        "priority": "low",
                        "path": file_info["path"],
                        "size_gb": file_info["size_gb"],
                        "description": f"Review large {file_info['category']} file",
                        "command": f"# Manual review needed: {file_info['path']}",
                        "safe": False,
                        "impact": "low"
                    })
            
        except Exception as e:
            suggestions.append({
                "type": "error",
                "priority": "low",
                "description": f"Could not generate suggestions: {str(e)}",
                "safe": True,
                "impact": "none"
            })
        
        # Sort by priority and impact
        priority_order = {"high": 3, "medium": 2, "low": 1}
        suggestions.sort(key=lambda x: (priority_order.get(x.get("priority", "low"), 1), 
                                      x.get("size_gb", 0)), reverse=True)
        
        return suggestions[:15]  # Limit to top 15 suggestions
    
    def _get_dir_size_mb(self, dir_path: Path) -> float:
        """Calculate directory size in MB"""
        total_size = 0
        try:
            for item in dir_path.rglob("*"):
                if item.is_file():
                    total_size += item.stat().st_size
        except (OSError, PermissionError):
            pass
        return total_size / (1024**2)
    
    def _categorize_file(self, file_path: Path) -> str:
        """Categorize file type"""
        ext = file_path.suffix.lower()
        name = file_path.name.lower()
        
        if ext in [".mp4", ".avi", ".mkv", ".mov", ".wmv"]:
            return "video"
        elif ext in [".jpg", ".jpeg", ".png", ".gif", ".bmp", ".tiff"]:
            return "image"
        elif ext in [".zip", ".tar", ".gz", ".rar", ".7z"]:
            return "archive"
        elif ext in [".db", ".sqlite", ".sqlite3"]:
            return "database"
        elif "docker" in name:
            return "docker"
        elif "vm" in name or ext in [".vdi", ".vmdk", ".qcow2"]:
            return "virtual_machine"
        elif ext in [".iso", ".dmg"]:
            return "disk_image"
        else:
            return "other"
    
    def _identify_cache_type(self, dir_path: Path) -> str:
        """Identify cache directory type"""
        name = dir_path.name.lower()
        path_str = str(dir_path).lower()
        
        if "npm" in name or "node_modules" in path_str:
            return "npm"
        elif "pip" in name or "python" in path_str:
            return "pip"
        elif "gradle" in name:
            return "gradle"
        elif "maven" in name:
            return "maven"
        elif "cargo" in name:
            return "cargo"
        elif "browser" in path_str or "chrome" in path_str or "firefox" in path_str:
            return "browser"
        else:
            return "application"
    
    def _identify_temp_type(self, dir_path: Path) -> str:
        """Identify temporary directory type"""
        path_str = str(dir_path)
        
        if "/tmp" in path_str or "/var/tmp" in path_str:
            return "system_temp"
        elif "temp" in path_str.lower():
            return "app_temp"
        else:
            return "unknown"
    
    def _get_oldest_file_date(self, dir_path: Path) -> str:
        """Get oldest file date in directory"""
        oldest_time = None
        try:
            for file_path in dir_path.rglob("*"):
                if file_path.is_file():
                    mtime = file_path.stat().st_mtime
                    if oldest_time is None or mtime < oldest_time:
                        oldest_time = mtime
            if oldest_time:
                return datetime.fromtimestamp(oldest_time).isoformat()
        except Exception:
            pass
        return "unknown"
    
    def _get_newest_file_date(self, dir_path: Path) -> str:
        """Get newest file date in directory"""
        newest_time = None
        try:
            for file_path in dir_path.rglob("*"):
                if file_path.is_file():
                    mtime = file_path.stat().st_mtime
                    if newest_time is None or mtime > newest_time:
                        newest_time = mtime
            if newest_time:
                return datetime.fromtimestamp(newest_time).isoformat()
        except Exception:
            pass
        return "unknown"


def main():
    """Test the disk analyzer"""
    analyzer = DiskAnalyzer()
    result = analyzer.analyze_disk_usage()
    print(json.dumps(result, indent=2, default=str))


if __name__ == "__main__":
    main()
