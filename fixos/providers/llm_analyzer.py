#!/usr/bin/env python3
"""
LLM Analyzer for fixOS - Fallback analysis when heuristics aren't sufficient
"""

import json
from typing import Dict, List, Any, Optional
from dataclasses import dataclass


@dataclass
class LLMAnalysis:
    """Result of LLM analysis"""
    suggestions: List[Dict[str, Any]]
    confidence: float
    reasoning: str
    fallback_used: bool


class LLMAnalyzer:
    """Uses LLM to analyze disk issues when heuristics aren't sufficient"""
    
    def __init__(self, llm_client):
        self.llm_client = llm_client
        self.analysis_prompts = {
            "disk_analysis": """
You are a system cleanup expert. Analyze this disk usage data and provide cleanup suggestions.

Disk Analysis Data:
{disk_data}

Provide response in JSON format:
{{
    "analysis": {{
        "overall_assessment": "critical|warning|moderate|healthy",
        "main_issues": ["issue1", "issue2", ...],
        "space_recovery_potential": "high|medium|low"
    }},
    "suggestions": [
        {{
            "type": "cache_cleanup|log_cleanup|temp_cleanup|large_file|system_cleanup",
            "priority": "critical|high|medium|low", 
            "path": "/path/to/cleanup",
            "size_gb": 0.0,
            "description": "Human readable description",
            "command": "command to execute",
            "safe": true,
            "impact": "high|medium|low",
            "reasoning": "Why this action is recommended"
        }}
    ],
    "confidence": 0.8,
    "reasoning": "Explanation of the analysis approach"
}}
""",
            "failed_action_analysis": """
A cleanup action failed. Please analyze and suggest alternatives.

Failed Action:
- Description: {description}
- Command: {command}
- Path: {path}
- Error: {error}

Provide response in JSON format:
{{
    "failure_analysis": {{
        "likely_cause": "permission_denied|file_in_use|path_not_found|command_error|other",
        "alternative_approaches": [
            {{
                "approach": "description of alternative",
                "commands": ["cmd1", "cmd2"],
                "safety_level": "high|medium|low",
                "expected_success_rate": 0.8
            }}
        ]
    }},
    "confidence": 0.7,
    "reasoning": "Why these alternatives are suggested"
}}
""",
            "complex_disk_pattern": """
Analyze this complex disk usage pattern that heuristics couldn't categorize.

Pattern Data:
{pattern_data}

Provide response in JSON format:
{{
    "pattern_analysis": {{
        "pattern_type": "docker_images|vm_disks|database_files|backup_accumulation|other",
        "severity": "critical|high|medium|low",
        "growth_trend": "rapid|moderate|stable"
    }},
    "suggestions": [
        {{
            "type": "pattern_specific_cleanup",
            "priority": "critical|high|medium|low",
            "description": "Human readable description",
            "commands": ["cmd1", "cmd2"],
            "safe": true,
            "impact": "high|medium|low",
            "estimated_recovery_gb": 0.0
        }}
    ],
    "confidence": 0.75,
    "reasoning": "Pattern recognition explanation"
}}
"""
        }
    
    def analyze_disk_issues(self, disk_data: Dict[str, Any]) -> LLMAnalysis:
        """Use LLM to analyze disk issues when heuristics are insufficient"""
        try:
            prompt = self.analysis_prompts["disk_analysis"].format(
                disk_data=json.dumps(disk_data, indent=2, default=str)
            )
            
            response = self.llm_client.chat([
                {"role": "user", "content": prompt}
            ], max_tokens=1000, temperature=0.3)
            
            # Parse JSON response
            try:
                llm_result = json.loads(response)
                
                suggestions = []
                for suggestion in llm_result.get("suggestions", []):
                    # Validate and sanitize suggestion
                    clean_suggestion = self._sanitize_suggestion(suggestion)
                    if clean_suggestion:
                        suggestions.append(clean_suggestion)
                
                return LLMAnalysis(
                    suggestions=suggestions,
                    confidence=llm_result.get("confidence", 0.5),
                    reasoning=llm_result.get("reasoning", ""),
                    fallback_used=True
                )
                
            except json.JSONDecodeError:
                # Fallback if JSON parsing fails
                return self._create_fallback_analysis("Failed to parse LLM response")
                
        except Exception as e:
            return self._create_fallback_analysis(f"LLM analysis failed: {str(e)}")
    
    def analyze_failed_action(self, action: Dict[str, Any], error: str) -> LLMAnalysis:
        """Analyze failed cleanup action and suggest alternatives"""
        try:
            prompt = self.analysis_prompts["failed_action_analysis"].format(
                description=action.get("description", ""),
                command=action.get("command", ""),
                path=action.get("path", ""),
                error=error
            )
            
            response = self.llm_client.chat([
                {"role": "user", "content": prompt}
            ], max_tokens=500, temperature=0.3)
            
            try:
                llm_result = json.loads(response)
                
                # Convert alternative approaches to suggestions format
                suggestions = []
                for approach in llm_result.get("failure_analysis", {}).get("alternative_approaches", []):
                    suggestion = {
                        "type": "llm_fallback",
                        "priority": "medium",
                        "path": action.get("path", ""),
                        "size_gb": action.get("size_gb", 0),
                        "description": approach.get("approach", ""),
                        "command": approach.get("commands", [""])[0],
                        "safe": approach.get("safety_level", "low") == "high",
                        "impact": "medium",
                        "reasoning": f"LLM suggested alternative for failed: {action.get('description', '')}"
                    }
                    suggestions.append(suggestion)
                
                return LLMAnalysis(
                    suggestions=suggestions,
                    confidence=llm_result.get("confidence", 0.5),
                    reasoning=llm_result.get("reasoning", ""),
                    fallback_used=True
                )
                
            except json.JSONDecodeError:
                return self._create_fallback_analysis("Failed to parse LLM failure analysis")
                
        except Exception as e:
            return self._create_fallback_analysis(f"LLM failure analysis failed: {str(e)}")
    
    def analyze_complex_pattern(self, pattern_data: Dict[str, Any]) -> LLMAnalysis:
        """Analyze complex disk usage patterns that heuristics can't categorize"""
        try:
            prompt = self.analysis_prompts["complex_disk_pattern"].format(
                pattern_data=json.dumps(pattern_data, indent=2, default=str)
            )
            
            response = self.llm_client.chat([
                {"role": "user", "content": prompt}
            ], max_tokens=800, temperature=0.3)
            
            try:
                llm_result = json.loads(response)
                
                suggestions = []
                for suggestion in llm_result.get("suggestions", []):
                    clean_suggestion = self._sanitize_suggestion(suggestion)
                    if clean_suggestion:
                        suggestions.append(clean_suggestion)
                
                return LLMAnalysis(
                    suggestions=suggestions,
                    confidence=llm_result.get("confidence", 0.5),
                    reasoning=llm_result.get("reasoning", ""),
                    fallback_used=True
                )
                
            except json.JSONDecodeError:
                return self._create_fallback_analysis("Failed to parse LLM pattern analysis")
                
        except Exception as e:
            return self._create_fallback_analysis(f"LLM pattern analysis failed: {str(e)}")
    
    def _sanitize_suggestion(self, suggestion: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Sanitize and validate LLM suggestion"""
        try:
            # Required fields
            required_fields = ["type", "priority", "description", "command"]
            for field in required_fields:
                if field not in suggestion:
                    return None
            
            # Validate priority
            valid_priorities = ["critical", "high", "medium", "low"]
            if suggestion["priority"] not in valid_priorities:
                suggestion["priority"] = "medium"
            
            # Validate type
            valid_types = ["cache_cleanup", "log_cleanup", "temp_cleanup", "large_file", 
                          "system_cleanup", "llm_fallback", "pattern_specific_cleanup"]
            if suggestion["type"] not in valid_types:
                suggestion["type"] = "system_cleanup"
            
            # Ensure numeric fields
            if "size_gb" not in suggestion:
                suggestion["size_gb"] = 0.0
            else:
                try:
                    suggestion["size_gb"] = float(suggestion["size_gb"])
                except (ValueError, TypeError):
                    suggestion["size_gb"] = 0.0
            
            # Ensure boolean fields
            if "safe" not in suggestion:
                suggestion["safe"] = False
            else:
                suggestion["safe"] = bool(suggestion["safe"])
            
            # Validate impact
            valid_impacts = ["high", "medium", "low"]
            if "impact" not in suggestion or suggestion["impact"] not in valid_impacts:
                suggestion["impact"] = "medium"
            
            # Add reasoning if missing
            if "reasoning" not in suggestion:
                suggestion["reasoning"] = "LLM generated suggestion"
            
            return suggestion
            
        except Exception:
            return None
    
    def _create_fallback_analysis(self, error_message: str) -> LLMAnalysis:
        """Create fallback analysis when LLM fails"""
        return LLMAnalysis(
            suggestions=[],
            confidence=0.0,
            reasoning=f"LLM analysis unavailable: {error_message}",
            fallback_used=False
        )
    
    def enhance_heuristics_with_llm(self, heuristic_suggestions: List[Dict], 
                                  disk_data: Dict[str, Any]) -> List[Dict]:
        """Enhance heuristic suggestions with LLM insights"""
        if not heuristic_suggestions:
            # No heuristics available, use full LLM analysis
            llm_analysis = self.analyze_disk_issues(disk_data)
            return llm_analysis.suggestions
        
        # Check if heuristics found significant issues
        total_size = sum(s.get("size_gb", 0) for s in heuristic_suggestions)
        high_priority_count = sum(1 for s in heuristic_suggestions if s.get("priority") in ["critical", "high"])
        
        # If heuristics found good results, just use them
        if total_size > 1.0 or high_priority_count > 2:
            return heuristic_suggestions
        
        # Heuristics were insufficient, enhance with LLM
        try:
            llm_analysis = self.analyze_disk_issues(disk_data)
            
            if llm_analysis.confidence > 0.6 and llm_analysis.suggestions:
                # Combine heuristics and LLM suggestions
                combined = heuristic_suggestions.copy()
                
                # Add LLM suggestions that aren't duplicates
                heuristic_paths = {s.get("path", "") for s in heuristic_suggestions}
                
                for llm_suggestion in llm_analysis.suggestions:
                    if llm_suggestion.get("path", "") not in heuristic_paths:
                        combined.append(llm_suggestion)
                
                return combined
            else:
                # LLM confidence low, stick with heuristics
                return heuristic_suggestions
                
        except Exception:
            # LLM failed, use heuristics
            return heuristic_suggestions


def main():
    """Test the LLM analyzer"""
    # This would require actual LLM client setup
    print("LLM Analyzer requires actual LLM client configuration for testing")


if __name__ == "__main__":
    main()
