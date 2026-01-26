cmake_minimum_required(VERSION 3.10)
project(ZjuJudge C)

# 设置 C 标准
set(CMAKE_C_STANDARD 99)

# 关键：生成位置无关代码 (PIC)，用于动态库
set(CMAKE_POSITION_INDEPENDENT_CODE ON)

# 包含头文件目录
include_directories(include)

# 定义源文件 (注意：这里不再包含 get_data.c，因为数据由 Python 加载)
set(SOURCE_FILES src/grading.c)

# 生成动态库 (SHARED)
# Linux 下生成 libjudge.so
add_library(judge SHARED ${SOURCE_FILES})

# 可选：生成测试用的可执行文件 (仅在非 Docker 环境调试用)
# add_executable(judge_test src/main_test.c ${SOURCE_FILES})
