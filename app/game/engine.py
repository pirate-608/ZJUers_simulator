from app.core.llm import generate_cc98_post, generate_random_event # 导入LLM
from pathlib import Path

# 加载成就配置
ACHIEVEMENT_PATH = Path("/app/world/achievements.json")
if not ACHIEVEMENT_PATH.exists():
    ACHIEVEMENT_PATH = Path(__file__).resolve().parent.parent.parent / "world" / "achievements.json"
from app.models.user import User
from app.core.database import AsyncSessionLocal
from sqlalchemy import update
import asyncio
import random
import json
from app.game.state import RedisState
from app.websockets.manager import ConnectionManager

class GameEngine:
    def __init__(self, user_id: str, state: RedisState, manager: ConnectionManager):
        self.user_id = user_id
        self.state = state
        self.manager = manager
        self.is_running = False

    async def run_loop(self):
        self.is_running = True
        tick_count = 0
        while self.is_running:
            await asyncio.sleep(3)
            tick_count += 1
            # 原有自然衰减和Game Over逻辑
            current_stats = await self.state.get_stats()
            if not current_stats:
                break
            sanity = int(current_stats.get("sanity", 0))
            energy = int(current_stats.get("energy", 0))
            if sanity <= 0:
                await self.manager.send_personal_message({"type": "game_over", "reason": "心态崩了，天台风好大..."}, self.user_id)
                self.stop()
                break
            if energy <= 0:
                await self.manager.send_personal_message({"type": "game_over", "reason": "精力耗尽，远去的救护车..."}, self.user_id)
                self.stop()
                break
            await self.state.update_stat("energy", -1)
            await self._push_update(msg=None)
            # --- 新增：随机事件触发 (每10tick概率30%) ---
            if tick_count % 10 == 0 and random.random() < 0.3:
                asyncio.create_task(self._trigger_random_event())
            # --- 新增：成就检查 ---
            await self._check_achievements()

    async def process_action(self, action_data: dict):
        action = action_data.get("action")
        # 统计玩家动作次数 (用于成就系统)
        if action in ["study", "fish", "skip", "relax"]:
            await self.state.increment_action_count(action)
        # 原有分发逻辑
        if action == "relax":
            await self._handle_relax(action_data.get("target"))
        elif action in ["study", "fish", "skip"]:
            await self._handle_study_action(action, action_data.get("target"))
        elif action == "exam":
            await self._handle_final_exam()
        elif action == "event_choice":
            await self._handle_event_choice(action_data)
        elif action == "next_semester":
            await self._next_semester()

    async def _handle_final_exam(self):
        """处理期末考试结算"""
        # 1. 获取所有数据
        stats = await self.state.get_stats()
        course_mastery = await self.state.get_courses_mastery()
        import json
        course_info = json.loads(stats.get("course_info_json", "[]"))

        # 2. 计算成绩
        total_credits = 0
        total_gp = 0
        failed_count = 0
        transcript = []
        sanity = int(stats.get("sanity", 50))
        luck = int(stats.get("luck", 50))
        for course in course_info:
            c_id = course["id"]
            mastery = float(course_mastery.get(c_id, 0))
            credits = course["credits"]
            # 最终分数公式：擅长度(70%) + 心态(20%) + 运气(10%)
            sanity_bonus = (sanity - 50) / 10
            luck_bonus = random.uniform(-2, 5) + (luck - 50) / 20
            final_score = mastery * 0.9 + sanity_bonus + luck_bonus + 10
            final_score = max(0, min(100, final_score))
            if final_score >= 85:
                gp = 4.0
            elif final_score >= 60:
                gp = 1.5 + (final_score - 60) * 0.1
            else:
                gp = 0.0
                failed_count += 1
            total_credits += credits
            total_gp += gp * credits
            transcript.append({
                "name": course["name"],
                "score": final_score,
                "gp": gp
            })
        gpa = round(total_gp / total_credits, 2) if total_credits > 0 else 0.0
        # 3. 挂科惩罚 / 奖励
        msg = f"期末考试结束！GPA: {gpa}"
        if failed_count > 0:
            await self.state.update_stat("sanity", -20 * failed_count)
            msg += f" | 挂了 {failed_count} 门！"
        else:
            await self.state.update_stat("sanity", 10)
        # 4. 持久化到数据库 (User表)
        async with AsyncSessionLocal() as db:
            stmt = update(User).where(User.id == int(self.user_id)).values(highest_gpa=str(gpa))
            await db.execute(stmt)
            await db.commit()
        # 5. 推送结算单
        await self.manager.send_personal_message({
            "type": "semester_summary",
            "data": {
                "gpa": str(gpa),
                "failed_count": failed_count,
                "details": transcript
            }
        }, self.user_id)
        # 推送日志
        await self.manager.send_personal_message({
            "type": "event",
            "data": {"desc": msg}
        }, self.user_id)

    async def _handle_study_action(self, action_type: str, course_id: str):
        """处理学业交互逻辑"""
        stats = await self.state.get_stats()
        iq = int(stats.get("iq", 90))
        
        msg = ""
        mastery_delta = 0
        
        if action_type == "study":
            # 卷：效率受智商影响
            efficiency = 2.0 + (iq - 100) * 0.05
            mastery_delta = max(0.5, efficiency)
            await self.state.update_stat("energy", -5)
            await self.state.update_stat("stress", 2)
            await self.state.update_stat("sanity", -1)
            msg = f"你埋头苦读，感觉知识增加了！(擅长度 +{mastery_delta:.1f}%)"

        elif action_type == "fish":
            # 摸
            mastery_delta = 0.1
            await self.state.update_stat("energy", -1)
            await self.state.update_stat("stress", -1)
            await self.state.update_stat("sanity", 1)
            msg = "你坐在教室后排摸鱼，老师讲的什么完全没听见。(擅长度 +0.1%)"

        elif action_type == "skip":
            # 翘
            mastery_delta = 0
            await self.state.update_stat("energy", 2)
            await self.state.update_stat("stress", -3)
            await self.state.update_stat("sanity", 2)
            msg = "你逃课去了，空气真香！"

        if mastery_delta > 0:
            await self.state.update_course_mastery(course_id, mastery_delta)
        
        # 统一推送
        await self._push_update(msg)

    async def _handle_relax(self, target: str):
        msg = ""
        if target == "gym":
            await self.state.update_stat("energy", 10)
            await self.state.update_stat("sanity", 5)
            await self.state.update_stat("stress", -5)
            msg = "你在风雨操场挥汗如雨，感觉充满了力量！(精力+10, 心态+5)"
        elif target == "game":
            await self.state.update_stat("energy", -10)
            await self.state.update_stat("sanity", 10)
            msg = "你在宿舍连赢三把，心情大好！(心态+10, 精力-10)"
        elif target == "walk":
            await self.state.update_stat("stress", -10)
            msg = "你在启真湖畔散步，看着黑天鹅，内心平静了许多。(压力-10)"
        elif target == "cc98":
            roll = random.randint(1, 100)
            msg = ""
            if roll > 80:
                await self.state.update_stat("sanity", 5)
                msg = "(心态+5)"
            elif roll < 20:
                await self.state.update_stat("sanity", -5)
                msg = "(心态-5)"
            stats = await self.state.get_stats()
            post_content = await generate_cc98_post(stats)
            final_msg = f"你在CC98刷到了：\n“{post_content}”\n{msg}"
            await self._push_update(final_msg)
            return
        await self._push_update(msg)

    async def _trigger_random_event(self):
        stats = await self.state.get_stats()
        event_data = await generate_random_event(stats)
        if event_data:
            await self.manager.send_personal_message({
                "type": "random_event",
                "data": event_data
            }, self.user_id)

    async def _handle_event_choice(self, data):
        effects = data.get("effects", {})
        desc = effects.get("desc", "")
        for key, val in effects.items():
            if key != "desc":
                await self.state.update_stat(key, int(val))
        await self._push_update(f"事件结果：{desc}")

    async def _check_achievements(self):
        stats = await self.state.get_stats()
        action_counts = await self.state.get_action_counts()
        gpa = float(stats.get("gpa", 0))
        sanity = int(stats.get("sanity", 50))
        eq = int(stats.get("eq", 50))
        failed_count = int(stats.get("failed_count", 0))
        with open(ACHIEVEMENT_PATH, "r") as f:
            ach_config = json.load(f)
        unlocked = await self.state.get_unlocked_achievements()
        new_unlocks = []
        for code, item in ach_config.items():
            if code in unlocked:
                continue
            passed = False
            if code == "gpa_king" and gpa >= 4.0: passed = True
            if code == "broken_heart" and sanity < 10: passed = True
            if code == "social_butterfly" and eq >= 95: passed = True
            if code == "library_ghost" and action_counts.get("study", 0) > 50: passed = True
            if passed:
                await self.state.unlock_achievement(code)
                new_unlocks.append(item)
        for ach in new_unlocks:
            await self.manager.send_personal_message({
                "type": "achievement_unlocked",
                "data": ach
            }, self.user_id)

    async def _next_semester(self):
        current_semester_idx = await self.state.increment_semester()
        if current_semester_idx > 8:
            await self._graduation_ceremony()
            self.stop()
            return
        await self.state.reset_courses_for_new_semester(current_semester_idx)
        holiday_event = await generate_random_event({"context": "寒暑假", "semester": current_semester_idx})
        await self.manager.send_personal_message({
            "type": "new_semester",
            "data": {
                "semester_name": f"第 {current_semester_idx} 学期",
                "holiday_event": holiday_event
            }
        }, self.user_id)
        await self._push_update("新学期开始了！")

    async def _push_update(self, msg: str = None):
        """
        辅助函数：统一推送数值、课程进度和日志
        """
        # 1. 获取最新数值
        new_stats = await self.state.get_stats()
        # 2. 获取最新课程进度 (这是关键，无论什么操作，都把课程进度带上，保证前端显示同步)
        course_mastery = await self.state.get_courses_mastery()
        
        # 合并数据推给前端
        payload = {
            "type": "tick",
            "stats": new_stats,
            "courses": course_mastery
        }
        await self.manager.send_personal_message(payload, self.user_id)

        # 3. 推送日志 (如果有)
        if msg:
            await self.manager.send_personal_message({
                "type": "event",
                "data": {"desc": msg}
            }, self.user_id)

    def stop(self):
        self.is_running = False