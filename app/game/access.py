import ctypes
import json
import os
import platform
from pathlib import Path
from typing import Dict, Any, List

# ==========================================
# 1. 路径与动态库加载配置 (修正版)
# ==========================================

# 定义 Docker 容器内的绝对路径 (这是最稳健的，不受代码目录深度影响)
DOCKER_EXAM_PATH = Path("/app/world/entrance_exam.json")

# 定义本地开发时的相对路径 (作为备用)
# app/game/access.py -> app/game -> app -> root
LOCAL_BASE_DIR = Path(__file__).resolve().parent.parent.parent
LOCAL_EXAM_PATH = LOCAL_BASE_DIR / "world" / "entrance_exam.json"

# 智能判断当前环境
if DOCKER_EXAM_PATH.exists():
    EXAM_FILE_PATH = DOCKER_EXAM_PATH
    # print("[INFO] Loading exam from Docker path") # 调试用
else:
    EXAM_FILE_PATH = LOCAL_EXAM_PATH
    # print(f"[INFO] Loading exam from Local path: {EXAM_FILE_PATH}") # 调试用

# 动态库路径配置
# 同样优先检查 Docker 标准路径
DOCKER_LIB_PATH = Path("/app/lib/libjudge.so")

if DOCKER_LIB_PATH.exists():
    LIB_PATH = DOCKER_LIB_PATH
    LIB_LOADED = True
else:
    # 本地开发环境的回退逻辑
    system_name = platform.system()
    lib_name = "judge.dll" if system_name == "Windows" else "libjudge.so"
    # 假设本地编译在 c_modules/build
    LIB_PATH = LOCAL_BASE_DIR / "c_modules" / "build" / lib_name
    LIB_LOADED = False # 先默认 False，下面 try 加载成功再改

# 加载逻辑保持不变...
try:
    if os.path.exists(LIB_PATH):
        _lib = ctypes.CDLL(str(LIB_PATH))
        _lib.calculate_score.argtypes = [ctypes.c_char_p, ctypes.c_char_p, ctypes.c_int]
        _lib.calculate_score.restype = ctypes.c_int
        LIB_LOADED = True
        print(f"[INFO] C Grading Library loaded successfully from {LIB_PATH}")
    else:
        print(f"[WARNING] Library not found at {LIB_PATH}")
        _lib = None
        LIB_LOADED = False
except OSError as e:
    print(f"[WARNING] Failed to load C library: {e}")
    _lib = None
    LIB_LOADED = False

# ==========================================
# 2. 核心功能实现
# ==========================================

def _load_questions() -> List[Dict[str, Any]]:
    """
    加载试卷 JSON 文件
    """
    if not EXAM_FILE_PATH.exists():
        print(f"[ERROR] Exam file not found: {EXAM_FILE_PATH}")
        return []
    
    try:
        with open(EXAM_FILE_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
            # 兼容 JSON 根节点是列表或字典的情况
            if isinstance(data, list):
                return data
            elif isinstance(data, dict) and "questions" in data:
                return data["questions"]
            else:
                return []
    except json.JSONDecodeError:
        print(f"[ERROR] Invalid JSON format in {EXAM_FILE_PATH}")
        return []

def _call_c_judge(user_ans: str, correct_ans: str, score: int) -> int:
    """
    调用 C 函数进行单题判卷
    """
    if not LIB_LOADED or _lib is None:
        return 0
    
    # Python 字符串转 C 字节串 (UTF-8)
    # 处理 None 输入
    b_user = user_ans.encode('utf-8') if user_ans else b""
    b_correct = correct_ans.encode('utf-8') if correct_ans else b""
    
    return _lib.calculate_score(b_user, b_correct, score)

def _calculate_tier(score: int) -> str:
    """
    根据分数计算档位 (60分及格)
    """
    if score < 60:
        return "FAIL"
    elif 60 <= score < 70:
        return "TIER_4"  # 60-70
    elif 70 <= score < 80:
        return "TIER_3"  # 70-80
    elif 80 <= score < 90:
        return "TIER_2"  # 80-90
    else:
        return "TIER_1"  # 90-100+

def grade_entrance_exam(user_submission: Dict[str, str]) -> Dict[str, Any]:
    """
    [主入口] 批改入学考试
    
    Args:
        user_submission: 用户提交的答案字典 {"1": "答案A", "2": "答案B"}，key为题目ID(str)
        
    Returns:
        Dict 包含:
        - passed (bool): 是否及格
        - total_score (int): 总分
        - max_score (int): 卷面满分
        - tier (str): 档位 (TIER_1 ~ TIER_4, 或 FAIL)
        - details (list): 每道题的判卷详情 (可选，用于前端展示错题)
    """
    questions = _load_questions()
    
    total_score = 0
    max_score = 0
    details = []
    
    for q in questions:
        # 兼容 JSON 中的 id 可能是 int 或 str
        q_id = str(q.get("id"))
        correct_ans = q.get("answer", "")
        points = q.get("score", 0)
        
        max_score += points
        
        # 获取用户答案，去除两端空白
        user_ans = user_submission.get(q_id, "").strip()
        
        # 调用 C 动态库判分
        obtained_score = _call_c_judge(user_ans, correct_ans, points)
        total_score += obtained_score
        
        details.append({
            "id": q_id,
            "question": q.get("content", ""), # 可选：返回题目内容方便前端回顾
            "user_answer": user_ans,
            "correct": obtained_score > 0,
            "score": obtained_score
        })
        
    tier = _calculate_tier(total_score)
    passed = total_score >= 60

    return {
        "passed": passed,
        "total_score": total_score,
        "max_score": max_score,
        "tier": tier,
        "details": details # 包含详细的对错情况
    }

# 用于调试
if __name__ == "__main__":
    # 模拟测试
    print(f"Loading exam from: {EXAM_FILE_PATH}")
    # 假设你手动创建了一个 submission
    mock_submission = {
        "1": "Zhejiang University", # 假设答案正确
        "2": "Wrong Answer",        # 假设答案错误
    }
    result = grade_entrance_exam(mock_submission)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    
def get_questions_for_frontend() -> List[Dict[str, Any]]:
    """
    给前端返回题目列表（剥离答案字段，防止作弊）
    """
    all_questions = _load_questions()
    safe_questions = []
    
    for q in all_questions:
        safe_questions.append({
            "id": str(q.get("id")),
            "content": q.get("content"),
            "score": q.get("score", 0)
        })
    
    return safe_questions