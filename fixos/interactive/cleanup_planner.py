#!/usr/bin/env python3
"""
Interactive Cleanup Planner for fixOS
Groups cleanup actions and provides interactive selection
"""

import json
from typing import Dict, List, Any, Tuple
from dataclasses import dataclass
from enum import Enum


class Priority(Enum):
    CRITICAL = "critical"
    HIGH = "high" 
    MEDIUM = "medium"
    LOW = "low"


class CleanupType(Enum):
    CACHE = "cache_cleanup"
    LOG = "log_cleanup"
    TEMP = "temp_cleanup"
    LARGE_FILE = "large_file"
    SYSTEM = "system_cleanup"
    USER = "user_cleanup"


@dataclass
class CleanupAction:
    """Represents a cleanup action"""
    type: CleanupType
    priority: Priority
    path: str
    size_gb: float
    description: str
    command: str
    safe: bool
    impact: str
    category: str = ""
    estimated_time: str = ""
    dependencies: List[str] = None
    
    def __post_init__(self):
        if self.dependencies is None:
            self.dependencies = []


class CleanupPlanner:
    """Interactive cleanup planning and grouping system"""
    
    def __init__(self):
        self.categories = {
            "cache": {
                "name": "Cache Files",
                "description": "Application cache that can be safely cleared",
                "color": "blue",
                "icon": "🗂️"
            },
            "logs": {
                "name": "Log Files", 
                "description": "Old system and application logs",
                "color": "yellow",
                "icon": "📋"
            },
            "temp": {
                "name": "Temporary Files",
                "description": "Temporary files and directories",
                "color": "orange", 
                "icon": "🗑️"
            },
            "large_files": {
                "name": "Large Files",
                "description": "Large individual files requiring review",
                "color": "red",
                "icon": "📦"
            },
            "system": {
                "name": "System Cleanup",
                "description": "System-level cleanup operations",
                "color": "purple",
                "icon": "⚙️"
            },
            "user": {
                "name": "User Data",
                "description": "User-specific cleanup actions",
                "color": "green",
                "icon": "👤"
            }
        }
        
        self.impact_levels = {
            "high": {"name": "High Impact", "gain_gb": "> 1.0 GB", "color": "green"},
            "medium": {"name": "Medium Impact", "gain_gb": "0.1-1.0 GB", "color": "yellow"},
            "low": {"name": "Low Impact", "gain_gb": "< 0.1 GB", "color": "red"}
        }
    
    def group_by_category(self, suggestions: List[Dict]) -> Dict[str, List[CleanupAction]]:
        """Group cleanup suggestions by category"""
        grouped = {}
        
        for suggestion in suggestions:
            try:
                # Convert dict to CleanupAction
                action = self._dict_to_action(suggestion)
                
                # Determine category
                category = self._get_category_for_action(action)
                
                if category not in grouped:
                    grouped[category] = []
                grouped[category].append(action)
                
            except Exception as e:
                # Skip invalid suggestions
                continue
        
        # Sort actions within each category by priority and size
        for category in grouped:
            grouped[category].sort(key=lambda x: (
                self._priority_score(x.priority),
                x.size_gb
            ), reverse=True)
        
        return grouped
    
    def prioritize_actions(self, grouped_actions: Dict[str, List[CleanupAction]]) -> List[CleanupAction]:
        """Create prioritized list of all actions"""
        all_actions = []
        
        # Add high priority actions first
        for category, actions in grouped_actions.items():
            high_priority = [a for a in actions if a.priority in [Priority.CRITICAL, Priority.HIGH]]
            all_actions.extend(high_priority)
        
        # Add medium priority actions
        for category, actions in grouped_actions.items():
            medium_priority = [a for a in actions if a.priority == Priority.MEDIUM]
            all_actions.extend(medium_priority)
        
        # Add low priority actions
        for category, actions in grouped_actions.items():
            low_priority = [a for a in actions if a.priority == Priority.LOW]
            all_actions.extend(low_priority)
        
        # Sort by impact and safety
        all_actions.sort(key=lambda x: (
            self._priority_score(x.priority),
            x.size_gb if x.safe else 0,
            x.safe
        ), reverse=True)
        
        return all_actions
    
    def create_cleanup_plan(self, suggestions: List[Dict]) -> Dict[str, Any]:
        """Create comprehensive cleanup plan"""
        grouped = self.group_by_category(suggestions)
        prioritized = self.prioritize_actions(grouped)
        
        # Calculate statistics
        total_size_gb = sum(action.size_gb for action in prioritized)
        safe_size_gb = sum(action.size_gb for action in prioritized if action.safe)
        high_priority_size = sum(action.size_gb for action in prioritized 
                               if action.priority in [Priority.CRITICAL, Priority.HIGH])
        
        plan = {
            "summary": {
                "total_actions": len(prioritized),
                "total_size_gb": round(total_size_gb, 2),
                "safe_size_gb": round(safe_size_gb, 2),
                "high_priority_size_gb": round(high_priority_size, 2),
                "categories_count": len(grouped)
            },
            "categories": {},
            "prioritized_actions": [],
            "recommendations": self._generate_recommendations(grouped, prioritized)
        }
        
        # Add category details
        for category, actions in grouped.items():
            category_info = self.categories.get(category, {
                "name": category.title(),
                "description": "Cleanup actions",
                "color": "gray",
                "icon": "📁"
            })
            
            plan["categories"][category] = {
                "info": category_info,
                "actions_count": len(actions),
                "total_size_gb": round(sum(a.size_gb for a in actions), 2),
                "safe_size_gb": round(sum(a.size_gb for a in actions if a.safe), 2),
                "actions": [self._action_to_dict(a) for a in actions[:5]]  # Top 5 per category
            }
        
        # Add prioritized actions (top 15)
        plan["prioritized_actions"] = [self._action_to_dict(a) for a in prioritized[:15]]
        
        return plan
    
    def interactive_selection(self, plan: Dict[str, Any]) -> Dict[str, Any]:
        """Interactive selection process (simulated for now)"""
        selected_actions = []
        
        # Auto-select safe, high-impact actions
        for action_dict in plan["prioritized_actions"]:
            if action_dict.get("safe", False) and action_dict.get("size_gb", 0) > 0.1:
                selected_actions.append(action_dict)
        
        return {
            "selected_actions": selected_actions,
            "total_selected": len(selected_actions),
            "estimated_space_gb": round(sum(a.get("size_gb", 0) for a in selected_actions), 2),
            "selection_method": "auto_safe_high_impact"
        }
    
    def _dict_to_action(self, suggestion: Dict) -> CleanupAction:
        """Convert dictionary suggestion to CleanupAction"""
        try:
            return CleanupAction(
                type=CleanupType(suggestion.get("type", "large_file")),
                priority=Priority(suggestion.get("priority", "low")),
                path=suggestion.get("path", ""),
                size_gb=float(suggestion.get("size_gb", 0)),
                description=suggestion.get("description", ""),
                command=suggestion.get("command", ""),
                safe=bool(suggestion.get("safe", False)),
                impact=suggestion.get("impact", "low"),
                category=suggestion.get("category", ""),
                estimated_time=suggestion.get("estimated_time", ""),
                dependencies=suggestion.get("dependencies", [])
            )
        except Exception as e:
            # Create default action for invalid suggestions
            return CleanupAction(
                type=CleanupType.LARGE_FILE,
                priority=Priority.LOW,
                path="",
                size_gb=0,
                description="Invalid action",
                command="",
                safe=False,
                impact="none"
            )
    
    def _action_to_dict(self, action: CleanupAction) -> Dict[str, Any]:
        """Convert CleanupAction to dictionary"""
        return {
            "type": action.type.value,
            "priority": action.priority.value,
            "path": action.path,
            "size_gb": action.size_gb,
            "description": action.description,
            "command": action.command,
            "safe": action.safe,
            "impact": action.impact,
            "category": action.category,
            "estimated_time": action.estimated_time,
            "dependencies": action.dependencies
        }
    
    def _get_category_for_action(self, action: CleanupAction) -> str:
        """Determine category for action based on type and path"""
        if action.type == CleanupType.CACHE:
            return "cache"
        elif action.type == CleanupType.LOG:
            return "logs"
        elif action.type == CleanupType.TEMP:
            return "temp"
        elif action.type == CleanupType.LARGE_FILE:
            return "large_files"
        elif "system" in action.path.lower() or action.path.startswith("/"):
            return "system"
        else:
            return "user"
    
    def _priority_score(self, priority: Priority) -> int:
        """Convert priority to numeric score"""
        scores = {
            Priority.CRITICAL: 4,
            Priority.HIGH: 3,
            Priority.MEDIUM: 2,
            Priority.LOW: 1
        }
        return scores.get(priority, 1)
    
    def _generate_recommendations(self, grouped: Dict[str, List[CleanupAction]], 
                                prioritized: List[CleanupAction]) -> List[Dict]:
        """Generate cleanup recommendations"""
        recommendations = []
        
        # High-impact safe actions
        safe_high_impact = [a for a in prioritized 
                          if a.safe and a.size_gb > 0.5 and a.priority in [Priority.HIGH, Priority.CRITICAL]]
        
        if safe_high_impact:
            total_safe = sum(a.size_gb for a in safe_high_impact)
            recommendations.append({
                "type": "safe_cleanup",
                "priority": "high",
                "title": f"Safe High-Impact Cleanup Available",
                "description": f"Can safely free {total_safe:.1f} GB with {len(safe_high_impact)} actions",
                "actions_count": len(safe_high_impact),
                "space_gb": round(total_safe, 2)
            })
        
        # Cache cleanup recommendation
        cache_actions = grouped.get("cache", [])
        if cache_actions:
            cache_size = sum(a.size_gb for a in cache_actions)
            if cache_size > 0.5:
                recommendations.append({
                    "type": "cache_cleanup",
                    "priority": "medium",
                    "title": "Cache Cleanup Recommended",
                    "description": f"Clear application cache to free {cache_size:.1f} GB",
                    "actions_count": len(cache_actions),
                    "space_gb": round(cache_size, 2)
                })
        
        # Log cleanup recommendation
        log_actions = grouped.get("logs", [])
        if log_actions:
            log_size = sum(a.size_gb for a in log_actions)
            if log_size > 0.2:
                recommendations.append({
                    "type": "log_cleanup", 
                    "priority": "low",
                    "title": "Log Files Can Be Cleaned",
                    "description": f"Clean old logs to free {log_size:.1f} GB",
                    "actions_count": len(log_actions),
                    "space_gb": round(log_size, 2)
                })
        
        # Manual review needed
        manual_review = [a for a in prioritized if not a.safe and a.size_gb > 1.0]
        if manual_review:
            manual_size = sum(a.size_gb for a in manual_review)
            recommendations.append({
                "type": "manual_review",
                "priority": "medium",
                "title": "Manual Review Required",
                "description": f"{len(manual_review)} large files ({manual_size:.1f} GB) need manual review",
                "actions_count": len(manual_review),
                "space_gb": round(manual_size, 2)
            })
        
        return recommendations


def main():
    """Test the cleanup planner"""
    # Sample data for testing
    sample_suggestions = [
        {
            "type": "cache_cleanup",
            "priority": "high",
            "path": "/home/user/.cache/npm",
            "size_gb": 2.5,
            "description": "Clear npm cache",
            "command": "npm cache clean --force",
            "safe": True,
            "impact": "high"
        },
        {
            "type": "log_cleanup",
            "priority": "medium", 
            "path": "/var/log",
            "size_gb": 0.8,
            "description": "Clean old system logs",
            "command": "find /var/log -name '*.log' -mtime +30 -delete",
            "safe": True,
            "impact": "medium"
        }
    ]
    
    planner = CleanupPlanner()
    plan = planner.create_cleanup_plan(sample_suggestions)
    print(json.dumps(plan, indent=2))


if __name__ == "__main__":
    main()
