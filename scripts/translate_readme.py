#!/usr/bin/env python3
"""
Translate README.md to English using local Ollama model.
Output: README_en.md in project root.

Usage:
    python scripts/translate_readme.py
    python scripts/translate_readme.py -m qwen3.5:7b

Requirements:
    pip install ollama
    ollama pull qwen3.5:4b
"""

import ollama
import os
import re
import time
from pathlib import Path


def split_markdown(content, max_chars=4000):
    """
    智能分块：尽量在段落边界切分，保留代码块完整性
    """
    paragraphs = re.split(r"(\n\n)", content)

    chunks = []
    current_chunk = ""
    in_code_block = False

    for para in paragraphs:
        if para.strip().startswith("```"):
            in_code_block = not in_code_block

        if len(current_chunk) + len(para) < max_chars or in_code_block:
            current_chunk += para
        else:
            if current_chunk.strip():
                chunks.append(current_chunk.strip())
            current_chunk = para

    if current_chunk.strip():
        chunks.append(current_chunk.strip())

    return chunks


def translate_chunk(chunk, chunk_idx, total_chunks, max_retries=3):
    """
    翻译单个文本块，带重试机制
    """
    system_prompt = """You are a technical documentation translator. Translate the following Markdown content from Chinese to English.

Requirements:
1. Keep ALL Markdown formatting intact (code blocks, tables, links, headings, lists, etc.)
2. Keep ALL code unchanged - variable names, commands, file paths stay as-is
3. Keep technical terms accurate (e.g., WebSocket, JWT, Redis, ORM, etc.)
4. Make the English natural and fluent
5. Keep the original structure and line breaks
6. Do NOT add any extra explanation or notes"""

    for attempt in range(max_retries):
        try:
            print(
                f"  Chunk {chunk_idx}/{total_chunks} (attempt {attempt+1})...",
                end=" ",
                flush=True,
            )

            response = ollama.chat(
                model="qwen3.5:4b",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": chunk},
                ],
                options={"temperature": 0.1, "num_ctx": 8192},
            )

            print("✓")
            return response["message"]["content"]

        except Exception as e:
            print(f"✗ ({e})")
            if attempt < max_retries - 1:
                wait_time = (attempt + 1) * 5
                print(f"    Retrying in {wait_time}s...")
                time.sleep(wait_time)
            else:
                raise Exception(f"Failed after {max_retries} attempts: {e}")


def translate_readme():
    # 项目根目录（scripts 的上级）
    project_root = Path(__file__).parent.parent
    readme_path = project_root / "README.md"
    output_path = project_root / "README_en.md"

    if not readme_path.exists():
        print(f"✗ {readme_path} not found!")
        return

    # 读取源文件
    print(f"Reading {readme_path}...")
    with open(readme_path, "r", encoding="utf-8") as f:
        content = f.read()

    print(f"Source: {len(content)} chars")

    # 分块
    chunks = split_markdown(content, max_chars=4000)
    total_chunks = len(chunks)
    print(f"Split into {total_chunks} chunks\n")

    # 逐块翻译
    translated_chunks = []
    for i, chunk in enumerate(chunks, 1):
        translated = translate_chunk(chunk, i, total_chunks)
        translated_chunks.append(translated)

    # 合并并写入
    print(f"\nWriting {output_path}...")
    full_translation = "\n\n".join(translated_chunks)

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(full_translation)

    print(f"Done! Output: {len(full_translation)} chars")

    # 检查代码块数量是否一致
    orig_code_blocks = len(re.findall(r"```", content))
    trans_code_blocks = len(re.findall(r"```", full_translation))
    if orig_code_blocks != trans_code_blocks:
        print(
            f"\n⚠ Warning: Code block count mismatch (original: {orig_code_blocks}, translation: {trans_code_blocks})"
        )
        print("  Manual review recommended.")
    else:
        print(f"\n✓ Code blocks preserved correctly ({orig_code_blocks} blocks)")


if __name__ == "__main__":
    translate_readme()
