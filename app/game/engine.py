import asyncio
import random
import json
import logging
from pathlib import Path
from sqlalchemy import update

from app.core.llm import (
    generate_cc98_post,
    generate_random_event,
    generate_dingtalk_message,
)
from app.models.user import User
from app.core.database import AsyncSessionLocal
from app.game.state import RedisState
from app.game.balance import balance  # 游戏数值配置
from app.websockets.manager import ConnectionManager
from app.api.cache import RedisCache

# 配置日志记录
logger = logging.getLogger(__name__)


class GameEngine:
    def resume(self):
        if not self.is_running:
            # 注意：不要提前设置 is_running = True，让 run_loop() 自己设置
            # 否则 run_loop() 第一行检查会直接返回
            asyncio.create_task(self.run_loop())
            # 推送最新状态和通知消息
            asyncio.create_task(self._push_update())
            asyncio.create_task(
                self.manager.send_personal_message(
                    {"type": "resumed", "msg": "游戏已继续。"}, self.user_id
                )
            )

    def pause(self):
        self.is_running = False
        # 可选：通知前端已暂停
        asyncio.create_task(
            self.manager.send_personal_message(
                {"type": "paused", "msg": "游戏已暂停，可随时继续。"}, self.user_id
            )
        )

    def __init__(self, user_id: str, state: RedisState, manager: ConnectionManager):
        self.user_id = user_id
        self.state = state
        self.manager = manager
        self.is_running = False
        self._ttl_refresh_interval_seconds = 600
        self._last_ttl_refresh = 0.0

        # 预设成就路径
        self.achievement_path = Path("/app/world/achievements.json")
        if not self.achievement_path.exists():
            self.achievement_path = (
                Path(__file__).resolve().parent.parent.parent
                / "world"
                / "achievements.json"
            )

        # ========== 从配置文件加载数值参数 ==========
        # 状态定义: 0=摆(Lay Flat), 1=摸(Chill), 2=卷(Hardcore)
        self.COURSE_STATE_COEFFS = balance.get_course_state_coeffs()
        self.BASE_ENERGY_DRAIN = balance.base_energy_drain
        self.BASE_MASTERY_GROWTH = balance.base_mastery_growth

    async def check_and_trigger_gameover(self) -> bool:
        """检测精力/心态是否归零并触发game over"""
        stats = await self.state.get_stats()
        if not stats:
            return False
        try:
            # 使用 get(..., 100) 确保即便 Key 不存在也能逻辑运行
            sanity = int(stats.get("sanity", 100))
            energy = int(stats.get("energy", 100))

            reason = ""
            if sanity <= 0:
                reason = "心态崩了，天台风好大..."
            elif energy <= 0:
                reason = "精力耗尽，远去的救护车..."

            if reason:
                await self.manager.send_personal_message(
                    {"type": "game_over", "reason": reason, "restartable": True},
                    self.user_id,
                )
                self.stop()
                return True
        except (ValueError, TypeError):
            pass
        return False

    def _sanity_stress_growth_factor(self, sanity, stress):
        """
        心态修正：50为基准，低于50负面影响，极低(<20)最大-40%；高于50正面提升，最佳(80+)+20%
        压力修正：40-70为最佳区间，区间内+30%，区间外-15%，极端（<20或>90）-40%
        """
        # 从配置加载参数
        growth_mod = balance.get_growth_modifiers()
        sanity_cfg = growth_mod.get("sanity", {})
        stress_cfg = growth_mod.get("stress", {})

        # 心态修正
        critical_threshold = sanity_cfg.get("critical_low", {}).get("threshold", 20)
        critical_factor = sanity_cfg.get("critical_low", {}).get("factor", 0.6)
        low_slope = sanity_cfg.get("low_slope", 0.013)
        high_slope = sanity_cfg.get("high_slope", 0.007)
        excellent_threshold = sanity_cfg.get("excellent", {}).get("threshold", 80)
        excellent_factor = sanity_cfg.get("excellent", {}).get("factor", 1.2)

        if sanity < critical_threshold:
            sanity_factor = critical_factor
        elif sanity < 50:
            sanity_factor = 1 - (50 - sanity) * low_slope
        elif sanity >= excellent_threshold:
            sanity_factor = excellent_factor
        elif sanity > 50:
            sanity_factor = 1 + (sanity - 50) * high_slope
        else:
            sanity_factor = 1.0

        # 压力修正
        optimal_range = stress_cfg.get("optimal_range", [40, 70])
        optimal_factor = stress_cfg.get("optimal_factor", 1.3)
        suboptimal_factor = stress_cfg.get("suboptimal_factor", 0.85)
        extreme_factor = stress_cfg.get("extreme_factor", 0.6)

        if optimal_range[0] <= stress <= optimal_range[1]:
            stress_factor = optimal_factor
        elif 20 <= stress < optimal_range[0] or optimal_range[1] < stress <= 90:
            stress_factor = suboptimal_factor
        else:
            stress_factor = extreme_factor

        return sanity_factor * stress_factor

    def _sanity_stress_exam_factor(self, sanity, stress):
        """
        心态修正：50为基准，低于50分数线性下滑，最低-15分，高于50最多+6分
        压力修正：40-70区间+6分，区间外-5分，极端（<20或>90）-10分
        """
        # 从配置加载参数
        exam_mod = balance.get_exam_modifiers()
        sanity_cfg = exam_mod.get("sanity", {})
        stress_cfg = exam_mod.get("stress", {})

        # 心态
        low_slope = sanity_cfg.get("low_slope", 0.3)
        high_slope = sanity_cfg.get("high_slope", 0.12)
        excellent_bonus = sanity_cfg.get("excellent_bonus", 6)

        if sanity < 50:
            sanity_bonus = (sanity - 50) * low_slope
        elif sanity >= 80:
            sanity_bonus = excellent_bonus
        elif sanity > 50:
            sanity_bonus = (sanity - 50) * high_slope
        else:
            sanity_bonus = 0

        # 压力
        optimal_bonus = stress_cfg.get("optimal_bonus", 6)
        suboptimal_penalty = stress_cfg.get("suboptimal_penalty", -5)
        extreme_penalty = stress_cfg.get("extreme_penalty", -10)

        if 40 <= stress <= 70:
            stress_bonus = optimal_bonus
        elif 20 <= stress < 40 or 70 < stress <= 90:
            stress_bonus = suboptimal_penalty
        else:
            stress_bonus = extreme_penalty

        return sanity_bonus + stress_bonus

    async def run_loop(self):
        """核心循环：基于状态的资源分配计算"""
        if self.is_running:
            return
        self.is_running = True
        logger.info(f"State-based Game loop started for {self.user_id}")

        tick_count = 0
        try:
            while self.is_running:
                await asyncio.sleep(3)  # 3秒一个Tick
                tick_count += 1

                # 低频 TTL 刷新：仅对活跃玩家做防线更新
                now_ts = asyncio.get_running_loop().time()
                if (
                    now_ts - self._last_ttl_refresh
                    >= self._ttl_refresh_interval_seconds
                ):
                    await RedisCache.touch_ttl(
                        RedisCache.build_player_keys(self.user_id),
                        self.state.player_ttl_seconds,
                    )
                    self._last_ttl_refresh = now_ts

                # 1. 基础检查
                if await self.check_and_trigger_gameover():
                    break

                # 2. 获取计算所需数据 (并行获取以提升性能)
                stats, course_states_raw = await asyncio.gather(
                    self.state.get_stats(), self.state.get_all_course_states()
                )

                # 解析课程信息
                try:
                    course_info = json.loads(stats.get("course_info_json", "[]"))
                except:
                    course_info = []

                # 如果没有课程（如假期），只自然恢复或轻微消耗
                if not course_info:
                    await self.state.update_stat_safe("energy", 1)  # 假期回血
                    await self._push_update()
                    continue

                # 3. 核心算法：加权计算
                # -------------------------------------------------
                total_credits = sum(c.get("credits", 1.0) for c in course_info)
                if total_credits <= 0:
                    total_credits = 1.0

                total_drain_factor = 0.0
                mastery_updates = {}

                # 遍历每门课，计算这一跳的进度和对总精力的负担
                for course in course_info:
                    c_id = str(course.get("id"))
                    credits = float(course.get("credits", 1.0))
                    # 获取该课当前状态 (默认1:摸)
                    state_val = int(course_states_raw.get(c_id, 1))
                    coeffs = self.COURSE_STATE_COEFFS.get(
                        state_val, self.COURSE_STATE_COEFFS[1]
                    )
                    # A. 计算擅长度增量
                    iq_buff = (int(stats.get("iq", 100)) - 100) * 0.01
                    # 仅在摸/卷状态下引入心态压力修正
                    if state_val in (1, 2):
                        sanity = int(stats.get("sanity", 80))
                        stress = int(stats.get("stress", 40))
                        factor = self._sanity_stress_growth_factor(sanity, stress)
                    else:
                        factor = 1.0
                    actual_growth = (
                        self.BASE_MASTERY_GROWTH
                        * coeffs["growth"]
                        * (1 + iq_buff)
                        * factor
                    )
                    if actual_growth > 0:
                        mastery_updates[c_id] = actual_growth
                    # B. 计算精力消耗权重
                    weight = credits / total_credits
                    total_drain_factor += weight * coeffs["drain"]

                # 4. 执行更新
                # -------------------------------------------------
                # 批量更新课程进度
                if mastery_updates:
                    await self.state.batch_update_course_mastery(mastery_updates)

                # 结算总精力消耗
                # 最终消耗 = 基础消耗 * 加权系数（保留浮点数精度）
                final_energy_cost_float = self.BASE_ENERGY_DRAIN * total_drain_factor

                # 修复：只有drain系数真正接近0（全摆烂）才回血
                # 避免"全摸"状态因int截断误判为摆烂
                if final_energy_cost_float < 0.3:  # 真正的摆烂阈值
                    await self.state.update_stat_safe("energy", 2)
                    await self.state.update_stat_safe("stress", -2)  # 摆烂降压
                else:
                    # 向上取整，确保至少消耗1点精力
                    import math

                    final_energy_cost = max(1, math.ceil(final_energy_cost_float))
                    await self.state.update_stat_safe("energy", -final_energy_cost)
                    # 卷多了压力大：如果消耗系数高，增加压力
                    if total_drain_factor > 1.5:
                        await self.state.update_stat_safe("stress", 1)

                # 5. 随机事件与成就 (从配置读取频率) - 仅在游戏运行时触发
                if self.is_running:
                    event_cfg = balance.get_random_event_config()
                    event_interval = event_cfg.get("check_interval_ticks", 5)
                    event_probability = event_cfg.get("trigger_probability", 0.4)

                    if tick_count % event_interval == 0:
                        if random.random() < event_probability:
                            asyncio.create_task(self._trigger_random_event())
                        await self._check_achievements()

                    # [新增] 6. 钉钉消息 (从配置读取频率) - 仅在游戏运行时触发
                    dingtalk_cfg = balance.get_dingtalk_config()
                    dingtalk_interval = dingtalk_cfg.get("check_interval_ticks", 10)
                    dingtalk_probability = dingtalk_cfg.get("trigger_probability", 0.3)

                    if (
                        tick_count % dingtalk_interval == 0
                        and random.random() < dingtalk_probability
                    ):
                        asyncio.create_task(self._trigger_dingtalk_message())

                await self._push_update()

        except Exception as e:
            logger.error(f"Engine Loop Error: {e}")
            self.stop()

    async def process_action(self, action_data: dict):
        action = action_data.get("action")
        target = action_data.get("target")  # 通常是 course_id
        value = action_data.get("value")  # 新增: 状态值 0/1/2
        if action == "pause":
            self.pause()
            return
        if action == "resume":
            self.resume()
            return
        if action == "restart":
            self.stop()
            await self.state.clear_all()
            stats = await self.state.get_stats()  # 获取旧数据还是需要先取一下
            # 这里简化逻辑，实际可能需要前端传参或默认
            initial_stats = await self.state.init_game("ZJUer", "TIER_1")
            await self.manager.send_personal_message(
                {"type": "init", "data": initial_stats}, self.user_id
            )
            asyncio.create_task(self.run_loop())
            return

        # [新增] 切换课程状态指令
        if action == "change_course_state":
            if target and value is not None:
                # 更新 Redis 状态
                await self.state.set_course_state(target, int(value))
                # 立即推送一次更新，让前端看到精力预估变化(可选，run_loop也会推)
                await self._push_update()
            return

        # [保留] 其它一次性动作 (Relax/Event)
        try:
            if action == "relax":
                await self._handle_relax(target)
            elif action == "exam":
                await self._handle_final_exam()
            elif action == "event_choice":
                await self._handle_event_choice(action_data)
            elif action == "next_semester":
                await self._next_semester()

            await self.check_and_trigger_gameover()
        except Exception as e:
            logger.error(f"Action Error {action}: {e}")

    async def _handle_final_exam(self):
        """期末考试结算逻辑"""
        stats = await self.state.get_stats()
        course_mastery = await self.state.get_courses_mastery()

        try:
            course_info = json.loads(stats.get("course_info_json", "[]"))
        except:
            course_info = []

        total_credits, total_gp, failed_count = 0, 0, 0
        transcript = []

        sanity = int(stats.get("sanity", 50))
        luck = int(stats.get("luck", 50))

        for course in course_info:
            c_id = str(course.get("id"))
            mastery = float(course_mastery.get(c_id, 0))
            credits = course.get("credits", 1)
            # 考试表现计算公式：擅长度占大头，心态和运气波动
            # 新增：心态压力修正
            sanity = int(stats.get("sanity", 50))
            stress = int(stats.get("stress", 40))
            exam_bonus = self._sanity_stress_exam_factor(sanity, stress)
            luck_bonus = random.uniform(-2, 5) + (luck - 50) / 20
            final_score = max(0, min(100, mastery * 0.9 + exam_bonus + luck_bonus + 10))

            # 5分制绩点计算：绩点 = 分数 / 10 - 5，最低0分
            gp = max(0.0, round(final_score / 10 - 5, 2))
            # 挂科阈值从配置读取
            fail_threshold = balance.fail_threshold
            if final_score < fail_threshold:
                failed_count += 1

            total_credits += credits
            total_gp += gp * credits
            transcript.append(
                {
                    "name": course.get("name", "未知课程"),
                    "score": round(final_score, 1),
                    "gp": round(gp, 2),
                }
            )

        gpa = round(total_gp / total_credits, 2) if total_credits > 0 else 0.0

        # 结果反馈（从配置读取惩罚/奖励）
        msg = f"期末考试结束！GPA: {gpa}"
        if failed_count > 0:
            penalty = balance.fail_sanity_penalty * failed_count
            await self.state.update_stat_safe("sanity", penalty)
            msg += f" | 挂了 {failed_count} 门！"
        else:
            bonus = balance.pass_all_bonus
            await self.state.update_stat_safe("sanity", bonus)

        # 异步更新持久化数据库
        asyncio.create_task(self._update_db_highest_gpa(gpa))

        # 发送结算弹窗和通知
        await self.manager.send_personal_message(
            {
                "type": "semester_summary",
                "data": {
                    "gpa": str(gpa),
                    "failed_count": failed_count,
                    "details": transcript,
                },
            },
            self.user_id,
        )

        await self._push_update(msg)

    async def _update_db_highest_gpa(self, gpa: float):
        """内部方法：持久化最高 GPA 到数据库"""
        try:
            async with AsyncSessionLocal() as db:
                stmt = (
                    update(User)
                    .where(User.id == int(self.user_id))
                    .values(highest_gpa=str(gpa))
                )
                await db.execute(stmt)
                await db.commit()
        except Exception as e:
            logger.error(f"DB Update Failed: {e}")

    async def _handle_study_action(self, action_type: str, course_id: str):
        stats = await self.state.get_stats()
        iq = int(stats.get("iq", 90))

        try:
            course_info = json.loads(stats.get("course_info_json", "[]"))
        except:
            course_info = []

        difficulty = 1.0
        for c in course_info:
            if str(c.get("id")) == str(course_id):
                difficulty = float(c.get("difficulty", 1.0))
                break

        mastery_delta = 0
        if action_type == "study":
            # 提升了学习收益率
            efficiency = 4.0 + (iq - 100) * 0.1
            mastery_delta = max(1.0, efficiency / (1 + difficulty))
            await self.state.update_stat_safe("energy", -5)
            await self.state.update_stat_safe("stress", 2)
            await self.state.update_stat_safe("sanity", -1)
            msg = f"你埋头苦读，感觉知识暴涨！(擅长度 +{mastery_delta:.1f}%)"
        elif action_type == "fish":
            mastery_delta = 0.2
            await self.state.update_stat_safe("energy", -1)
            await self.state.update_stat_safe("stress", -1)
            await self.state.update_stat_safe("sanity", 1)
            msg = "你在课上摸鱼，虽然学得慢，但心情不错。"
        elif action_type == "skip":
            await self.state.update_stat_safe("energy", 2)
            await self.state.update_stat_safe("stress", -3)
            await self.state.update_stat_safe("sanity", 2)
            msg = "逃课一时爽，一直逃课一直爽！"

        if mastery_delta > 0:
            await self.state.update_course_mastery(course_id, mastery_delta)

        await self._push_update(msg)

    async def _handle_relax(self, target: str):
        # 检查冷却时间
        remaining_cd = await self.state.check_cooldown(target)
        if remaining_cd > 0:
            msg = f"该操作还在冷却中，请等待 {remaining_cd} 秒后再试。"
            await self._push_update(msg)
            return

        # 从配置读取摸鱼动作参数
        action_cfg = balance.get_relax_action(target)
        if not action_cfg:
            msg = f"未知的休闲动作: {target}"
            await self._push_update(msg)
            return

        msg = ""
        if target == "gym":
            stats = await self.state.get_stats()
            current_energy = int(stats.get("energy", 0))
            min_energy = action_cfg.get("min_energy_required", 50)

            if current_energy < min_energy:
                msg = "你太累了，现在去健身只会晕过去..."
            else:
                # 从配置读取数值
                energy_cost = action_cfg.get("energy_cost", -50)
                energy_gain = action_cfg.get("energy_gain", 60)
                sanity_gain = action_cfg.get("sanity_gain", 5)
                stress_change = action_cfg.get("stress_change", -5)

                await self.state.update_stat_safe("energy", energy_cost)
                await self.state.update_stat_safe("energy", energy_gain)
                await self.state.update_stat_safe("sanity", sanity_gain)
                await self.state.update_stat_safe("stress", stress_change)
                await self.state.set_cooldown(target)
                msg = "在风雨操场挥汗如雨，感觉整个人都升华了！"
        elif target == "game":
            energy_cost = action_cfg.get("energy_cost", -5)
            sanity_gain = action_cfg.get("sanity_gain", 20)

            await self.state.update_stat_safe("energy", energy_cost)
            await self.state.update_stat_safe("sanity", sanity_gain)
            await self.state.set_cooldown(target)
            msg = "宿舍开黑连胜，这就是电子竞技的魅力吗？"
        elif target == "walk":
            stress_change = action_cfg.get("stress_change", -10)

            await self.state.update_stat_safe("stress", stress_change)
            await self.state.set_cooldown(target)
            msg = "启真湖畔的黑天鹅还是那么高傲..."
        elif target == "cc98":
            # CC98随机效果从配置读取
            effects = action_cfg.get("effects", [])
            if not effects:
                # 兜底默认值
                effects = [
                    {"weight": 0.5, "sanity": 8, "stress": -5},
                    {"weight": 0.3, "sanity": -10, "stress": 8},
                    {"weight": 0.2, "sanity": -15, "stress": 15},
                ]

            # 根据权重随机选择效果
            total_weight = sum(e.get("weight", 0) for e in effects)
            roll = random.uniform(0, total_weight)
            cumulative = 0
            selected_effect = effects[0]  # 默认

            for effect in effects:
                cumulative += effect.get("weight", 0)
                if roll <= cumulative:
                    selected_effect = effect
                    break

            # 应用效果
            if "sanity" in selected_effect:
                await self.state.update_stat_safe("sanity", selected_effect["sanity"])
            if "stress" in selected_effect:
                await self.state.update_stat_safe("stress", selected_effect["stress"])

            # 生成对应效果描述
            effect_type = (
                "positive" if selected_effect.get("sanity", 0) > 0 else "negative"
            )
            roll = random.randint(1, 100)  # 用于触发词

            if effect_type == "positive":
                trigger_words = [
                    "校友糗事分享",
                    "今日开怀",
                    "难绷瞬间",
                    "幽默段子",
                    "校园梗",
                    "甜蜜爱情故事",
                ]
            else:
                trigger_words = [
                    "凡尔赛GPA",
                    "郁闷小屋",
                    "烂坑",
                    "情侣秀恩爱",
                    "渣男渣女",
                ]

            trigger = random.choice(trigger_words)
            stats = await self.state.get_stats()
            post_content, feedback = await generate_cc98_post(
                stats, effect_type, trigger
            )
            await self.state.set_cooldown(target)
            msg = f"你在CC98刷到了：\n{post_content}\n{feedback}"

        await self._push_update(msg)

    # app/game/engine.py

    async def _trigger_random_event(self):
        """触发 LLM 驱动的随机事件（带去重逻辑）"""
        # 再次检查游戏是否暂停（防止暂停时已创建的任务执行）
        if not self.is_running:
            return

        try:
            # 1. 从 Redis 获取该玩家的事件历史
            history = await self.state.get_event_history()

            # 2. 获取当前状态
            stats = await self.state.get_stats()

            # 3. 调用 LLM（传入历史记录进行避雷）
            event_data = await generate_random_event(stats, history)

            if event_data:
                # 4. 记录本次事件标题到历史中
                await self.state.add_event_to_history(event_data["title"])

                # 5. 推送给前端
                await self.manager.send_personal_message(
                    {"type": "random_event", "data": event_data}, self.user_id
                )
        except Exception as e:
            logger.error(f"Random event error: {e}", exc_info=True)

    async def _handle_event_choice(self, data):
        """处理随机事件的选择结果"""
        effects = data.get("effects", {})
        desc = effects.get("desc", "")
        for key, val in effects.items():
            if key != "desc":
                try:
                    # 使用 safe 方法确保数值更新合法
                    await self.state.update_stat_safe(key, int(val))
                except:
                    continue
        await self._push_update(f"事件：{desc}")

    async def _trigger_dingtalk_message(self):
        """触发钉钉消息推送"""
        # 再次检查游戏是否暂停
        if not self.is_running:
            return

        try:
            stats = await self.state.get_stats()

            # 简单的上下文判断逻辑
            context = "random"
            sanity = int(stats.get("sanity", 50))
            stress = int(stats.get("stress", 0))
            gpa = float(stats.get("gpa", 0))

            if sanity < 30:
                context = "low_sanity"
            elif stress > 80:
                context = "high_stress"
            elif gpa > 0 and gpa < 2.0:
                context = "low_gpa"

            msg_data = await generate_dingtalk_message(stats, context)

            if msg_data:
                await self.manager.send_personal_message(
                    {"type": "dingtalk_message", "data": msg_data},  # 新的消息类型
                    self.user_id,
                )

        except Exception as e:
            logger.error(f"DingTalk trigger error: {e}", exc_info=True)

    async def _check_achievements(self):
        """成就系统判定逻辑"""
        try:
            stats = await self.state.get_stats()
            action_counts = await self.state.get_action_counts()

            # 防御性转换
            gpa = float(stats.get("highest_gpa") or 0)
            sanity = int(stats.get("sanity") or 50)
            eq = int(stats.get("eq") or 50)
            study_count = int(action_counts.get("study") or 0)

            if not self.achievement_path.exists():
                return
            with open(self.achievement_path, "r", encoding="utf-8") as f:
                ach_config = json.load(f)

            unlocked = await self.state.get_unlocked_achievements()

            for code, item in ach_config.items():
                if code in unlocked:
                    continue

                passed = False
                if code == "gpa_king" and gpa >= 4.0:
                    passed = True
                elif code == "broken_heart" and sanity < 10:
                    passed = True
                elif code == "social_butterfly" and eq >= 95:
                    passed = True
                elif code == "library_ghost" and study_count > 50:
                    passed = True

                if passed:
                    await self.state.unlock_achievement(code)
                    await self.manager.send_personal_message(
                        {"type": "achievement_unlocked", "data": item}, self.user_id
                    )
        except Exception as e:
            logger.error(f"Achievement check error: {e}")

    async def _next_semester(self):
        """进入下一学期逻辑"""
        current_semester_idx = await self.state.increment_semester()

        # 自动保存：学期结束时保存进度
        try:
            from app.api.game import save_game_to_db

            await save_game_to_db(self.user_id, self.state)
            logger.info(
                f"Auto-save triggered at end of semester for user {self.user_id}"
            )
        except Exception as e:
            logger.error(f"Auto-save failed for user {self.user_id}: {e}")

        # 毕业判定
        if current_semester_idx > 8:
            stats = await self.state.get_stats()
            achievements = list(await self.state.get_unlocked_achievements())
            stats["achievements"] = achievements
            # 调用AI生成文言文结业总结
            from app.core.llm import generate_wenyan_report

            wenyan_report = await generate_wenyan_report(stats)
            await self.manager.send_personal_message(
                {
                    "type": "graduation",
                    "data": {
                        "msg": "恭喜你从折姜大学毕业！",
                        "final_stats": stats,
                        "wenyan_report": wenyan_report,
                    },
                },
                self.user_id,
            )
            self.stop()
            return

        # 重置课程并设置学期开始时间
        await self.state.reset_courses_for_new_semester(current_semester_idx)
        holiday_event = await generate_random_event(
            {"context": "假期", "semester": current_semester_idx}
        )

        await self.manager.send_personal_message(
            {
                "type": "new_semester",
                "data": {
                    "semester_name": f"第 {current_semester_idx} 学期",
                    "holiday_event": holiday_event,
                },
            },
            self.user_id,
        )
        await self._push_update("新学期开始了，加油！")

    async def _push_update(self, msg: str = None):
        """统一数据推送接口"""
        try:
            # 并发获取 stats、courses 和 course_states 减少等待
            new_stats, course_mastery, course_states = await asyncio.gather(
                self.state.get_stats(),
                self.state.get_courses_mastery(),
                self.state.get_all_course_states(),
            )

            # 计算学期剩余时间
            semester_idx = int(new_stats.get("semester_idx", 1))
            semester_config = balance.semester_config
            base_duration = semester_config.get("durations", {}).get(
                str(semester_idx), semester_config.get("default_duration", 360)
            )
            semester_time_left = await self.state.get_semester_time_left(base_duration)

            await self.manager.send_personal_message(
                {
                    "type": "tick",
                    "stats": new_stats,
                    "courses": course_mastery,
                    "course_states": course_states,
                    "semester_time_left": semester_time_left,
                },
                self.user_id,
            )

            if msg:
                await self.manager.send_personal_message(
                    {"type": "event", "data": {"desc": msg}}, self.user_id
                )
        except Exception as e:
            logger.error(f"Push failed: {e}")

    def stop(self):
        """安全停止游戏循环"""
        self.is_running = False
