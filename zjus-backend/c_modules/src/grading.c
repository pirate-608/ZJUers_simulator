#include "grader_common.h"
#include <ctype.h>
#include <string.h>
#include <stdlib.h>

#define MIN(a,b) (((a)<(b))?(a):(b))
#define MIN3(a,b,c) MIN(MIN(a,b),c)

// 内部辅助：标准化字符串 (转小写 + 去除首尾空格 + 合并中间空格)
// 标记为 static，不对外暴露
static void normalize_string(char* dest, const char* src, size_t dest_size) {
    size_t i = 0, j = 0;
    int space_seen = 0;

    // 1. 跳过开头的空格
    while (src[i] && isspace((unsigned char)src[i])) {
        i++;
    }

    while (src[i] && j < dest_size - 1) {
        unsigned char c = (unsigned char)src[i];
        
        if (isspace(c)) {
            if (!space_seen) {
                dest[j++] = ' ';
                space_seen = 1;
            }
        } else {
            dest[j++] = tolower(c);
            space_seen = 0;
        }
        i++;
    }

    // 2. 去除末尾可能的空格
    if (j > 0 && dest[j-1] == ' ') {
        j--;
    }
    
    dest[j] = '\0';
}

// Levenshtein Distance (编辑距离) 算法 - 空间优化版
static int levenshtein_distance(const char *s1, const char *s2) {
    int len1 = strlen(s1);
    int len2 = strlen(s2);
    
    if (len1 > MAX_STR_LEN) len1 = MAX_STR_LEN;
    if (len2 > MAX_STR_LEN) len2 = MAX_STR_LEN;

    int v0[MAX_STR_LEN + 1];
    int v1[MAX_STR_LEN + 1];

    for (int i = 0; i <= len2; i++) v0[i] = i;

    for (int i = 0; i < len1; i++) {
        v1[0] = i + 1;
        for (int j = 0; j < len2; j++) {
            int cost = (s1[i] == s2[j]) ? 0 : 1;
            v1[j + 1] = MIN3(
                v1[j] + 1,       // insertion
                v0[j + 1] + 1,   // deletion
                v0[j] + cost     // substitution
            );
        }
        memcpy(v0, v1, (len2 + 1) * sizeof(int));
    }

    return v0[len2];
}

// 导出函数实现
EXPORT int calculate_score(const char* user_ans, const char* correct_ans, int full_score) {
    if (!user_ans || !correct_ans) {
        return 0;
    }

    char u_norm[MAX_STR_LEN + 1];
    char c_norm[MAX_STR_LEN + 1];

    // 1. 预处理
    normalize_string(u_norm, user_ans, sizeof(u_norm));
    normalize_string(c_norm, correct_ans, sizeof(c_norm));

    // 2. 精确匹配
    if (strcmp(u_norm, c_norm) == 0) {
        return full_score;
    }

    // 3. 模糊匹配 (入学考试配置)
    int len = strlen(c_norm);
    int dist = levenshtein_distance(u_norm, c_norm);

    int allowed_errors = 0;
    
    // 配置调整：
    // 短词 (<=3): 如 "GPA", "ZJU" 必须精确匹配
    if (len <= 3) {
        allowed_errors = 0;
    } 
    // 中等词 (4-8): 如 "Score", "Campus" 允许 1 个错字
    else if (len <= 8) {
        allowed_errors = 1;
    } 
    // 长句 (>8): 允许 25% 的错误率 (稍微放宽一点，原为20%)
    else {
        allowed_errors = (int)(len * 0.25); 
    }

    // 安全阈值：编辑距离不能超过长度的一半 (防止 "ABC" 匹配上 "ABDE")
    if (dist > len / 2) {
        return 0;
    }

    if (dist <= allowed_errors) {
        return full_score;
    }

    return 0;
}