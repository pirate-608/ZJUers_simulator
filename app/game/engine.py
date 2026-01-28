import asyncio
import random
import json
import logging
from pathlib import Path
from sqlalchemy import update

from app.core.llm import generate_cc98_post, generate_random_event
from app.models.user import User
from app.core.database import AsyncSessionLocal
from app.game.state import RedisState
from app.websockets.manager import ConnectionManager

# 配置日志记录
logger = logging.getLogger(__name__)

class GameEngine:
    def __init__(self, user_id: str, state: RedisState, manager: ConnectionManager):
        self.user_id = user_id
        self.state = state
        self.manager = manager
        self.is_running = False
        
        # 预设成就路径
        self.achievement_path = Path("/app/world/achievements.json")
        if not self.achievement_path.exists():
            self.achievement_path = Path(__file__).resolve().parent.parent.parent / "world" / "achievements.json"

        # ========== 新增：数值平衡参数 ==========
        # 状态定义: 0=摆(Lay Flat), 1=摸(Chill), 2=卷(Hardcore)
        self.COURSE_STATE_COEFFS = {
            0: {"growth": 0.0, "drain": 0.0},   # 摆: 不学，不累
            1: {"growth": 0.5, "drain": 0.8},   # 摸: 学得慢，消耗低
            2: {"growth": 2.5, "drain": 3.0}    # 卷: 学得极快，消耗极大
        }
        self.BASE_ENERGY_DRAIN = 2.0  # 基础每Tick精力消耗 (当所有课都处于标准"摸"状态时的基准)
        self.BASE_MASTERY_GROWTH = 0.5 # 基础每Tick擅长度增长

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
                await self.manager.send_personal_message({
                    "type": "game_over",
                    "reason": reason,
                    "restartable": True
                }, self.user_id)
                self.stop()
                return True
        except (ValueError, TypeError):
            pass
        return False

    async def run_loop(self):
        """核心循环：基于状态的资源分配计算"""
        if self.is_running: return
        self.is_running = True
        logger.info(f"State-based Game loop started for {self.user_id}")
        
        tick_count = 0
        try:
            while self.is_running:
                await asyncio.sleep(3) # 3秒一个Tick
                tick_count += 1

                # 1. 基础检查
                if await self.check_and_trigger_gameover(): break

                # 2. 获取计算所需数据 (并行获取以提升性能)
                stats, course_states_raw = await asyncio.gather(
                    self.state.get_stats(),
                    self.state.get_all_course_states()
                )
                
                # 解析课程信息
                try:
                    course_info = json.loads(stats.get("course_info_json", "[]"))
                except: course_info = []

                # 如果没有课程（如假期），只自然恢复或轻微消耗
                if not course_info:
                    await self.state.update_stat_safe("energy", 1) # 假期回血
                    await self._push_update()
                    continue

                # 3. 核心算法：加权计算
                # -------------------------------------------------
                total_credits = sum(c.get("credits", 1.0) for c in course_info)
                if total_credits <= 0: total_credits = 1.0

                total_drain_factor = 0.0
                mastery_updates = {}
                
                # 遍历每门课，计算这一跳的进度和对总精力的负担
                for course in course_info:
                    c_id = str(course.get("id"))
                    credits = float(course.get("credits", 1.0))
                    
                    # 获取该课当前状态 (默认1:摸)
                    state_val = int(course_states_raw.get(c_id, 1)) 
                    coeffs = self.COURSE_STATE_COEFFS.get(state_val, self.COURSE_STATE_COEFFS[1])
                    
                    # A. 计算擅长度增量
                    # 公式: 基础增速 * 状态系数 * 难度修正(未实现，可扩展)
                    # 可以在这里加入 IQ 对 growth 的修正
                    iq_buff = (int(stats.get("iq", 100)) - 100) * 0.01
                    actual_growth = self.BASE_MASTERY_GROWTH * coeffs["growth"] * (1 + iq_buff)
                    
                    if actual_growth > 0:
                        mastery_updates[c_id] = actual_growth

                    # B. 计算精力消耗权重
                    # 公式: 学分占比 * 状态消耗系数
                    weight = credits / total_credits
                    total_drain_factor += weight * coeffs["drain"]

                # 4. 执行更新
                # -------------------------------------------------
                # 批量更新课程进度
                if mastery_updates:
                    await self.state.batch_update_course_mastery(mastery_updates)

                # 结算总精力消耗
                # 最终消耗 = 基础消耗 * 加权系数
                final_energy_cost = int(self.BASE_ENERGY_DRAIN * total_drain_factor)
                
                # 如果完全摆烂(系数0)，不仅不扣，还可以回一点血
                if final_energy_cost == 0:
                    await self.state.update_stat_safe("energy", 2)
                    await self.state.update_stat_safe("stress", -2) # 摆烂降压
                else:
                    await self.state.update_stat_safe("energy", -final_energy_cost)
                    # 卷多了压力大：如果消耗系数高，增加压力
                    if total_drain_factor > 1.5:
                        await self.state.update_stat_safe("stress", 1)

                # 5. 随机事件与成就 (保持原有逻辑)
                if tick_count % 10 == 0:
                    if random.random() < 0.3:
                        asyncio.create_task(self._trigger_random_event())
                    await self._check_achievements()

                await self._push_update()

        except Exception as e:
            logger.error(f"Engine Loop Error: {e}")
            self.stop()

    async def process_action(self, action_data: dict):
        """处理前端指令"""
        action = action_data.get("action")
        target = action_data.get("target") # 通常是 course_id
        value = action_data.get("value")   # 新增: 状态值 0/1/2

        if action == "restart":
            self.stop()
            await self.state.clear_all()
            stats = await self.state.get_stats() # 获取旧数据还是需要先取一下
            # 这里简化逻辑，实际可能需要前端传参或默认
            initial_stats = await self.state.init_game("ZJUer", "TIER_1")
            await self.manager.send_personal_message({"type": "init", "data": initial_stats}, self.user_id)
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
            sanity_bonus = (sanity - 50) / 10
            luck_bonus = random.uniform(-2, 5) + (luck - 50) / 20
            final_score = max(0, min(100, mastery * 0.9 + sanity_bonus + luck_bonus + 10))
            
            # 浙江大学标准 GPA 映射近似逻辑
            if final_score >= 85: gp = 4.0
            elif final_score >= 60: gp = 1.5 + (final_score - 60) * 0.1
            else:
                gp = 0.0
                failed_count += 1
                
            total_credits += credits
            total_gp += gp * credits
            transcript.append({
                "name": course.get("name", "未知课程"),
                "score": round(final_score, 1),
                "gp": round(gp, 2)
            })

        gpa = round(total_gp / total_credits, 2) if total_credits > 0 else 0.0
        
        # 结果反馈
        msg = f"期末考试结束！GPA: {gpa}"
        if failed_count > 0:
            await self.state.update_stat_safe("sanity", -20 * failed_count)
            msg += f" | 挂了 {failed_count} 门！"
        else:
            await self.state.update_stat_safe("sanity", 10)

        # 异步更新持久化数据库
        asyncio.create_task(self._update_db_highest_gpa(gpa))

        # 发送结算弹窗和通知
        await self.manager.send_personal_message({
            "type": "semester_summary",
            "data": {"gpa": str(gpa), "failed_count": failed_count, "details": transcript}
        }, self.user_id)
        
        await self._push_update(msg)

    async def _update_db_highest_gpa(self, gpa: float):
        """内部方法：持久化最高 GPA 到数据库"""
        try:
            async with AsyncSessionLocal() as db:
                stmt = update(User).where(User.id == int(self.user_id)).values(highest_gpa=str(gpa))
                await db.execute(stmt)
                await db.commit()
        except Exception as e:
            logger.error(f"DB Update Failed: {e}")

    async def _handle_study_action(self, action_type: str, course_id: str):
        stats = await self.state.get_stats()
        iq = int(stats.get("iq", 90))
        
        try:
            course_info = json.loads(stats.get("course_info_json", "[]"))
        except: course_info = []
            
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
        msg = ""
        if target == "gym":
            stats = await self.state.get_stats()
            if int(stats.get("energy", 0)) < 50:
                msg = "你太累了，现在去健身只会晕过去..."
            else:
                await self.state.update_stat_safe("energy", 10)
                await self.state.update_stat_safe("sanity", 5)
                await self.state.update_stat_safe("stress", -5)
                msg = "在风雨操场挥汗如雨，感觉整个人都升华了！"
        elif target == "game":
            await self.state.update_stat_safe("energy", -10)
            await self.state.update_stat_safe("sanity", 15) # 游戏提升心态较多
            msg = "宿舍开黑连胜，这就是电子竞技的魅力吗？"
        elif target == "walk":
            await self.state.update_stat_safe("stress", -10)
            msg = "启真湖畔的黑天鹅还是那么高傲..."
        elif target == "cc98":
            roll = random.randint(1, 100)
            if roll > 80:
                effect = "positive"
                await self.state.update_stat_safe("sanity", 5)
                trigger_words = ["校友糗事分享", "今日开怀", "难绷瞬间", "幽默段子", "校园梗", "甜蜜爱情故事"]
            elif roll < 20:
                effect = "negative"
                await self.state.update_stat_safe("sanity", -5)
                trigger_words = ["凡尔赛GPA", "郁闷小屋", "烂坑", "情侣秀恩爱", "渣男渣女"]
            else:
                effect = "neutral"
                trigger_words = ["吐槽食堂", "询问选课", "二手交易", "校园信息"]
            trigger = random.choice(trigger_words)
            stats = await self.state.get_stats()
            post_content, feedback = await generate_cc98_post(stats, effect, trigger)
            msg = f"你在CC98刷到了：\n“{post_content}”\n{feedback}"
        await self._push_update(msg)

    async def _trigger_random_event(self):
        """触发 LLM 驱动的随机事件"""
        try:
            stats = await self.state.get_stats()
            event_data = await generate_random_event(stats)
            if event_data:
                await self.manager.send_personal_message({
                    "type": "random_event",
                    "data": event_data
                }, self.user_id)
        except Exception as e:
            logger.error(f"Random event error: {e}")

    async def _handle_event_choice(self, data):
        """处理随机事件的选择结果"""
        effects = data.get("effects", {})
        desc = effects.get("desc", "")
        for key, val in effects.items():
            if key != "desc":
                try:
                    # 使用 safe 方法确保数值更新合法
                    await self.state.update_stat_safe(key, int(val))
                except: continue
        await self._push_update(f"事件：{desc}")

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
            
            if not self.achievement_path.exists(): return
            with open(self.achievement_path, "r", encoding="utf-8") as f:
                ach_config = json.load(f)
            
            unlocked = await self.state.get_unlocked_achievements()
            
            for code, item in ach_config.items():
                if code in unlocked: continue
                
                passed = False
                if code == "gpa_king" and gpa >= 4.0: passed = True
                elif code == "broken_heart" and sanity < 10: passed = True
                elif code == "social_butterfly" and eq >= 95: passed = True
                elif code == "library_ghost" and study_count > 50: passed = True
                
                if passed:
                    await self.state.unlock_achievement(code)
                    await self.manager.send_personal_message({
                        "type": "achievement_unlocked",
                        "data": item
                    }, self.user_id)
        except Exception as e:
            logger.error(f"Achievement check error: {e}")

    async def _next_semester(self):
        """进入下一学期逻辑"""
        current_semester_idx = await self.state.increment_semester()
        
        # 毕业判定
        if current_semester_idx > 8:
            stats = await self.state.get_stats()
            achievements = list(await self.state.get_unlocked_achievements())
            stats["achievements"] = achievements
            # 调用AI生成文言文结业总结
            from app.core.llm import generate_wenyan_report
            wenyan_report = await generate_wenyan_report(stats)
            await self.manager.send_personal_message({
                "type": "graduation",
                "data": {
                    "msg": "恭喜你从折姜大学毕业！",
                    "final_stats": stats,
                    "wenyan_report": wenyan_report
                }
            }, self.user_id)
            self.stop()
            return
            
        await self.state.reset_courses_for_new_semester(current_semester_idx)
        holiday_event = await generate_random_event({"context": "假期", "semester": current_semester_idx})
        
        await self.manager.send_personal_message({
            "type": "new_semester",
            "data": {
                "semester_name": f"第 {current_semester_idx} 学期",
                "holiday_event": holiday_event
            }
        }, self.user_id)
        await self._push_update("新学期开始了，加油！")

    async def _push_update(self, msg: str = None):
        """统一数据推送接口"""
        try:
            # 并发获取 stats 和 courses 减少等待
            new_stats, course_mastery = await asyncio.gather(
                self.state.get_stats(),
                self.state.get_courses_mastery()
            )
            
            await self.manager.send_personal_message({
                "type": "tick",
                "stats": new_stats,
                "courses": course_mastery
            }, self.user_id)

            if msg:
                await self.manager.send_personal_message({
                    "type": "event",
                    "data": {"desc": msg}
                }, self.user_id)
        except Exception as e:
            logger.error(f"Push failed: {e}")

    def stop(self):
        """安全停止游戏循环"""
        self.is_running = False