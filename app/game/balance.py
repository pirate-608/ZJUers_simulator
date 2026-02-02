"""
游戏数值平衡配置管理
负责加载和管理 world/game_balance.json 中的游戏参数
与 app/core/config.py (系统配置) 职责分离
"""
from pathlib import Path
import json
from typing import Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)


class GameBalance:
    """游戏数值配置管理器（单例）"""
    _instance: Optional['GameBalance'] = None
    _config: Dict[str, Any] = {}
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if not self._config:
            self.load()
    
    def load(self, config_path: str = "world/game_balance.json"):
        """加载配置文件"""
        try:
            path = Path(config_path)
            if not path.exists():
                logger.error(f"配置文件不存在: {config_path}")
                raise FileNotFoundError(f"配置文件不存在: {config_path}")
            
            with open(path, 'r', encoding='utf-8') as f:
                self._config = json.load(f)
            
            logger.info(f"游戏配置已加载: version={self._config.get('version', 'unknown')}")
        except Exception as e:
            logger.error(f"加载游戏配置失败: {e}")
            raise
    
    def reload(self, config_path: str = "world/game_balance.json"):
        """热重载配置（用于调试/运维）"""
        self._config = {}
        self.load(config_path)
        logger.info("游戏配置已重载")
    
    @property
    def raw(self) -> Dict[str, Any]:
        """获取原始配置字典"""
        return self._config
    
    @property
    def version(self) -> str:
        """配置版本"""
        return self._config.get("version", "unknown")
    
    # ==========================================
    # Tick 相关配置
    # ==========================================
    
    @property
    def tick_interval(self) -> int:
        """Tick 间隔（秒）"""
        return self._config.get("tick", {}).get("interval_seconds", 3)
    
    @property
    def base_energy_drain(self) -> float:
        """基础精力消耗"""
        return self._config.get("tick", {}).get("base_energy_drain", 0.8)
    
    @property
    def base_mastery_growth(self) -> float:
        """基础擅长度增长"""
        return self._config.get("tick", {}).get("base_mastery_growth", 0.5)
    
    # ==========================================
    # 学期配置
    # ==========================================
    
    @property
    def semester_config(self) -> Dict:
        """学期配置"""
        return self._config.get("semester", {})
    
    def get_semester_duration(self, semester_index: int) -> int:
        """获取指定学期的时长（秒）"""
        duration_map = self.semester_config.get("duration_by_index", {})
        default_duration = self.semester_config.get("default_duration_seconds", 360)
        return duration_map.get(str(semester_index), default_duration)
    
    @property
    def speed_modes(self) -> Dict:
        """获取可用的速度模式"""
        return self.semester_config.get("speed_modes", {
            "1.0": {"label": "正常速度", "multiplier": 1.0}
        })
    
    # ==========================================
    # 课程状态配置
    # ==========================================
    
    @property
    def course_states(self) -> Dict[str, Dict]:
        """课程状态配置（摆/摸/卷）"""
        return self._config.get("course_states", {})
    
    def get_course_state_coeffs(self) -> Dict[int, Dict]:
        """获取课程状态系数（转换为int key）"""
        return {
            int(k): v 
            for k, v in self.course_states.items()
        }
    
    # ==========================================
    # 心态/压力修正配置
    # ==========================================
    
    @property
    def sanity_stress_modifiers(self) -> Dict:
        """心态/压力修正配置"""
        return self._config.get("sanity_stress_modifiers", {})
    
    def get_growth_modifiers(self) -> Dict:
        """获取学习效率修正参数"""
        return self.sanity_stress_modifiers.get("growth", {})
    
    def get_exam_modifiers(self) -> Dict:
        """获取考试修正参数"""
        return self.sanity_stress_modifiers.get("exam", {})
    
    # ==========================================
    # 摸鱼动作配置
    # ==========================================
    
    @property
    def relax_actions(self) -> Dict[str, Dict]:
        """摸鱼动作配置"""
        return self._config.get("relax_actions", {})
    
    def get_relax_action(self, action: str) -> Dict:
        """获取指定摸鱼动作配置"""
        return self.relax_actions.get(action, {})
    
    def get_cooldown(self, action: str) -> int:
        """获取动作冷却时间（秒）"""
        return self.relax_actions.get(action, {}).get("cooldown_seconds", 0)
    
    # ==========================================
    # 事件配置
    # ==========================================
    
    @property
    def events(self) -> Dict:
        """事件配置"""
        return self._config.get("events", {})
    
    def get_random_event_config(self) -> Dict:
        """随机事件配置"""
        return self.events.get("random_event", {})
    
    def get_dingtalk_config(self) -> Dict:
        """钉钉消息配置"""
        return self.events.get("dingtalk", {})
    
    # ==========================================
    # 考试配置
    # ==========================================
    
    @property
    def exam_config(self) -> Dict:
        """考试相关配置"""
        return self._config.get("exam", {})
    
    @property
    def fail_threshold(self) -> int:
        """挂科阈值"""
        return self.exam_config.get("fail_threshold", 60)
    
    @property
    def fail_sanity_penalty(self) -> int:
        """挂科心态惩罚（每门）"""
        return self.exam_config.get("fail_sanity_penalty_per_course", -10)
    
    @property
    def pass_all_bonus(self) -> int:
        """全部通过心态奖励"""
        return self.exam_config.get("pass_all_sanity_bonus", 10)
    
    # ==========================================
    # 游戏结束配置
    # ==========================================
    
    @property
    def game_over_config(self) -> Dict:
        """游戏结束配置"""
        return self._config.get("game_over", {})


# 全局单例
balance = GameBalance()
