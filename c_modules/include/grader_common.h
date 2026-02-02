#ifndef GRADER_COMMON_H
#define GRADER_COMMON_H

#include <stddef.h>

// --- 动态库导出宏 ---
#ifdef _WIN32
    #define EXPORT __declspec(dllexport)
#else
    #define EXPORT __attribute__((visibility("default")))
#endif

#ifdef __cplusplus
extern "C" {
#endif

// 定义最大字符串长度（用于内部栈分配）
#define MAX_STR_LEN 256

/**
 * 计算单题得分
 * @param user_ans 用户提交的答案
 * @param correct_ans 标准答案
 * @param full_score 该题满分
 * @return 获得的分数 (0 或 full_score)
 */
EXPORT int calculate_score(const char* user_ans, const char* correct_ans, int full_score);

/**
 * (可选) 暴露批量判卷接口，如果需要一次传入所有答案
 * 这里我们保持简单，采用单题调用的方式，灵活性更高
 */

#ifdef __cplusplus
}
#endif

#endif // GRADER_COMMON_H