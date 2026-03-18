#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
docs目录同步工具
在执行前，请先修改 sync_config.json 文件，填入正确的路径
注意，该脚本是项目特定脚本，无通用性
当前版本的脚本仅能同步docs目录，无法同步此目录之外的其他配置文件或覆写模板，如有mkdocs.yml等文件，需要进入文档仓库手动修改。
"""

import os
import sys
import json
import shutil
import hashlib
import fnmatch
import time
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional, Tuple
import argparse

class Colors:
    """控制台颜色"""
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    CYAN = '\033[96m'
    END = '\033[0m'
    BOLD = '\033[1m'

class DocSync:
    """docs目录同步类"""
    
    def __init__(self, config_path: str):
        """
        初始化同步器
        
        Args:
            config_path: 配置文件路径
        """
        self.config_path = config_path
        self.config = self._load_config()
        self.stats = {
            'copied': 0,
            'updated': 0,
            'skipped': 0,
            'deleted': 0,
            'failed': 0,
            'total_size': 0
        }
        self.start_time = None
        self.end_time = None
        self.log_messages = []
        
    def _load_config(self) -> Dict:
        """加载配置文件"""
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
            
            # 验证必要配置
            required_fields = ['projects_dir', 'source_folder', 'target_folder']
            for field in required_fields:
                if field not in config:
                    raise ValueError(f"配置文件中缺少必要字段: {field}")
            
            # 设置默认值
            config.setdefault('docs_subdir', 'docs')
            config.setdefault('sync_options', {})
            config.setdefault('exclude_patterns', [])
            config.setdefault('include_patterns', [])
            config.setdefault('backup', {})
            config.setdefault('logging', {})
            config.setdefault('notifications', {})
            config.setdefault('filters', {})
            
            return config
            
        except FileNotFoundError:
            print(f"{Colors.RED}错误: 配置文件不存在: {config_path}{Colors.END}")
            sys.exit(1)
        except json.JSONDecodeError as e:
            print(f"{Colors.RED}错误: 配置文件格式错误: {e}{Colors.END}")
            sys.exit(1)
        except Exception as e:
            print(f"{Colors.RED}错误: 无法加载配置文件: {e}{Colors.END}")
            sys.exit(1)
    
    def _get_paths(self) -> Tuple[Path, Path]:
        """获取源路径和目标路径"""
        projects_dir = Path(self.config['projects_dir'])
        source_folder = self.config['source_folder']
        target_folder = self.config['target_folder']
        docs_subdir = self.config['docs_subdir']
        
        source_path = projects_dir / source_folder / docs_subdir
        target_path = projects_dir / target_folder / docs_subdir
        
        return source_path, target_path
    
    def _should_exclude(self, path: Path, rel_path: str) -> bool:
        """
        检查文件/目录是否应该被排除
        
        Args:
            path: 完整路径
            rel_path: 相对路径
            
        Returns:
            True表示应该排除，False表示应该包含
        """
        name = path.name
        str_path = str(path)
        rel_str = rel_path.replace('\\', '/')
        
        # 检查排除模式
        for pattern in self.config['exclude_patterns']:
            if fnmatch.fnmatch(name, pattern) or fnmatch.fnmatch(rel_str, pattern):
                return True
        
        # 检查包含模式（如果指定了包含模式，只有匹配的才会被包含）
        include_patterns = self.config['include_patterns']
        if include_patterns:
            for pattern in include_patterns:
                if fnmatch.fnmatch(name, pattern) or fnmatch.fnmatch(rel_str, pattern):
                    return False
            return True  # 没有匹配任何包含模式，排除
        
        # 检查隐藏文件
        if not self.config['filters'].get('include_hidden', False):
            if name.startswith('.'):
                return True
        
        # 检查文件大小
        if path.is_file():
            min_size = self.config['filters'].get('min_file_size', 0)
            max_size = self.config['filters'].get('max_file_size', 0)
            
            file_size = path.stat().st_size
            if min_size > 0 and file_size < min_size:
                return True
            if max_size > 0 and file_size > max_size:
                return True
        
        return False
    
    def _calculate_md5(self, file_path: Path, chunk_size: int = 8192) -> str:
        """计算文件的MD5值"""
        hash_md5 = hashlib.md5()
        try:
            with open(file_path, "rb") as f:
                for chunk in iter(lambda: f.read(chunk_size), b""):
                    hash_md5.update(chunk)
            return hash_md5.hexdigest()
        except Exception as e:
            self._log(f"计算MD5失败 {file_path}: {e}", 'ERROR')
            return ""
    
    def _log(self, message: str, level: str = 'INFO'):
        """记录日志"""
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        log_entry = f"[{timestamp}] [{level}] {message}"
        
        if self.config['logging'].get('enabled', True):
            self.log_messages.append(log_entry)
            
            if level == 'ERROR':
                print(f"{Colors.RED}{message}{Colors.END}")
            elif level == 'WARNING':
                print(f"{Colors.YELLOW}{message}{Colors.END}")
            elif level == 'INFO' and self.config['notifications'].get('show_progress', True):
                print(f"{Colors.CYAN}{message}{Colors.END}")
    
    def _save_log(self):
        """保存日志到文件"""
        log_file = self.config['logging'].get('log_file', 'sync_log.txt')
        log_path = Path(self.config['projects_dir']) / self.config['source_folder'] / 'scripts' / log_file
        
        try:
            with open(log_path, 'a', encoding='utf-8') as f:
                f.write('\n'.join(self.log_messages))
                f.write('\n' + '='*50 + '\n')
        except Exception as e:
            print(f"{Colors.RED}无法保存日志: {e}{Colors.END}")
    
    def _create_backup(self, source_path: Path) -> Optional[Path]:
        """创建备份"""
        if not self.config['backup'].get('enabled', False):
            return None
        
        backup_dir = self.config['backup'].get('backup_dir', 'backups')
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_path = Path(self.config['projects_dir']) / backup_dir / f"{self.config['source_folder']}_docs_{timestamp}"
        
        try:
            backup_path.mkdir(parents=True, exist_ok=True)
            self._log(f"创建备份: {backup_path}")
            
            # 复制源目录到备份
            if source_path.exists():
                shutil.copytree(source_path, backup_path / 'docs', 
                              symlinks=self.config['sync_options'].get('follow_symlinks', True))
                self._log("备份完成")
                
                # 清理旧备份
                self._cleanup_old_backups()
                return backup_path
                
        except Exception as e:
            self._log(f"备份失败: {e}", 'ERROR')
        
        return None
    
    def _cleanup_old_backups(self):
        """清理旧备份"""
        backup_dir = self.config['backup'].get('backup_dir', 'backups')
        max_backups = self.config['backup'].get('max_backups', 5)
        
        backup_base = Path(self.config['projects_dir']) / backup_dir
        if not backup_base.exists():
            return
        
        # 获取所有备份并按时间排序
        backups = sorted(backup_base.glob(f"{self.config['source_folder']}_docs_*"), 
                        key=os.path.getmtime, reverse=True)
        
        # 删除多余的备份
        for backup in backups[max_backups:]:
            try:
                shutil.rmtree(backup)
                self._log(f"删除旧备份: {backup}")
            except Exception as e:
                self._log(f"删除备份失败 {backup}: {e}", 'WARNING')
    
    def _sync_file(self, source_file: Path, target_file: Path, rel_path: str):
        """同步单个文件"""
        try:
            # 检查是否应该排除
            if self._should_exclude(source_file, rel_path):
                self.stats['skipped'] += 1
                self._log(f"[跳过-排除] {rel_path}")
                return
            
            # 检查目标文件是否存在
            if not target_file.exists():
                # 复制文件
                shutil.copy2(source_file, target_file)
                self.stats['copied'] += 1
                self.stats['total_size'] += source_file.stat().st_size
                self._log(f"[复制] {rel_path}")
                return
            
            # 比较文件
            compare_content = self.config['sync_options'].get('compare_content', False)
            
            if compare_content:
                # 基于内容比较
                source_md5 = self._calculate_md5(source_file)
                target_md5 = self._calculate_md5(target_file)
                
                if source_md5 and source_md5 != target_md5:
                    shutil.copy2(source_file, target_file)
                    self.stats['updated'] += 1
                    self._log(f"[更新-内容变化] {rel_path}")
                else:
                    self.stats['skipped'] += 1
                    self._log(f"[跳过-内容相同] {rel_path}")
            else:
                # 基于修改时间比较
                source_mtime = source_file.stat().st_mtime
                target_mtime = target_file.stat().st_mtime
                
                if source_mtime > target_mtime:
                    shutil.copy2(source_file, target_file)
                    self.stats['updated'] += 1
                    self._log(f"[更新-较新版本] {rel_path}")
                else:
                    self.stats['skipped'] += 1
                    self._log(f"[跳过-已是最新] {rel_path}")
                    
        except Exception as e:
            self.stats['failed'] += 1
            self._log(f"[失败] {rel_path}: {e}", 'ERROR')
    
    def _sync_directory(self, source_dir: Path, target_dir: Path):
        """递归同步目录"""
        try:
            # 确保目标目录存在
            target_dir.mkdir(parents=True, exist_ok=True)
            
            # 获取源目录中的所有项目
            for item in source_dir.iterdir():
                rel_path = str(item.relative_to(self.config['projects_dir']))
                
                # 检查是否应该排除
                if self._should_exclude(item, rel_path):
                    continue
                
                target_item = target_dir / item.name
                
                if item.is_file():
                    self._sync_file(item, target_item, rel_path)
                elif item.is_dir():
                    self._sync_directory(item, target_item)
                    
        except Exception as e:
            self._log(f"处理目录失败 {source_dir}: {e}", 'ERROR')
    
    def _cleanup_target(self, source_dir: Path, target_dir: Path):
        """清理目标目录中多余的文件"""
        if not self.config['sync_options'].get('delete_extra_files', False):
            return
        
        try:
            for item in target_dir.iterdir():
                rel_path = str(item.relative_to(self.config['projects_dir']))
                source_item = source_dir / item.name
                
                # 检查是否应该排除
                if self._should_exclude(item, rel_path):
                    continue
                
                if not source_item.exists():
                    if item.is_file():
                        item.unlink()
                        self.stats['deleted'] += 1
                        self._log(f"[删除] {rel_path}")
                    elif item.is_dir():
                        shutil.rmtree(item)
                        self.stats['deleted'] += 1
                        self._log(f"[删除目录] {rel_path}")
                        
        except Exception as e:
            self._log(f"清理目标目录失败: {e}", 'ERROR')
    
    def _show_header(self):
        """显示标题"""
        print(f"{Colors.CYAN}{'='*60}{Colors.END}")
        print(f"{Colors.GREEN}{Colors.BOLD}      docs目录同步工具 (纯Python实现){Colors.END}")
        print(f"{Colors.CYAN}{'='*60}{Colors.END}")
        print()
    
    def _show_config(self, source_path: Path, target_path: Path):
        """显示配置信息"""
        print(f"{Colors.BLUE}配置信息:{Colors.END}")
        print(f"  配置文件: {self.config_path}")
        print(f"  源目录: {source_path}")
        print(f"  目标目录: {target_path}")
        print(f"  删除多余文件: {self.config['sync_options'].get('delete_extra_files', False)}")
        print(f"  比较内容: {self.config['sync_options'].get('compare_content', False)}")
        
        if self.config['exclude_patterns']:
            print(f"  排除模式: {', '.join(self.config['exclude_patterns'][:5])}")
            if len(self.config['exclude_patterns']) > 5:
                print(f"           ... 等 {len(self.config['exclude_patterns'])} 个模式")
        
        if self.config['backup'].get('enabled', False):
            print(f"  备份: 启用 (最大备份数: {self.config['backup'].get('max_backups', 5)})")
        
        print()
    
    def _show_summary(self):
        """显示摘要"""
        duration = self.end_time - self.start_time
        
        print(f"\n{Colors.CYAN}{'='*60}{Colors.END}")
        if self.stats['failed'] == 0:
            print(f"{Colors.GREEN}✅ 同步成功完成！{Colors.END}")
        else:
            print(f"{Colors.RED}❌ 同步完成，但有 {self.stats['failed']} 个错误{Colors.END}")
        
        print(f"\n{Colors.BOLD}统计信息:{Colors.END}")
        print(f"  {Colors.GREEN}复制文件: {self.stats['copied']}{Colors.END}")
        print(f"  {Colors.YELLOW}更新文件: {self.stats['updated']}{Colors.END}")
        print(f"  {Colors.BLUE}跳过文件: {self.stats['skipped']}{Colors.END}")
        if self.config['sync_options'].get('delete_extra_files', False):
            print(f"  {Colors.RED}删除文件: {self.stats['deleted']}{Colors.END}")
        print(f"  {Colors.RED}失败文件: {self.stats['failed']}{Colors.END}")
        
        # 计算总大小
        total_mb = self.stats['total_size'] / (1024 * 1024)
        print(f"  总传输: {total_mb:.2f} MB")
        
        print(f"\n  {Colors.CYAN}耗时: {duration:.2f} 秒{Colors.END}")
        print(f"  {Colors.CYAN}完成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}{Colors.END}")
        print(f"{Colors.CYAN}{'='*60}{Colors.END}")
    
    def run(self):
        """执行同步"""
        self.start_time = time.time()
        
        # 显示标题
        self._show_header()
        
        # 获取路径
        source_path, target_path = self._get_paths()
        
        # 显示配置
        self._show_config(source_path, target_path)
        
        # 检查源目录
        if not source_path.exists():
            self._log(f"错误: 源目录不存在: {source_path}", 'ERROR')
            return False
        
        # 检查是否是dry run
        dry_run = self.config['sync_options'].get('dry_run', False)
        if dry_run:
            self._log("【模拟运行】不会实际修改文件", 'WARNING')
        
        # 确认同步
        response = input(f"{Colors.YELLOW}是否开始同步？(y/n): {Colors.END}")
        if response.lower() != 'y':
            self._log("操作已取消", 'WARNING')
            return False
        
        # 创建目标目录
        target_path.mkdir(parents=True, exist_ok=True)
        
        # 创建备份
        if self.config['backup'].get('backup_before_sync', True):
            backup_path = self._create_backup(source_path)
        
        # 执行同步
        self._log("开始同步...")
        if not dry_run:
            self._sync_directory(source_path, target_path)
            self._cleanup_target(source_path, target_path)
        
        self.end_time = time.time()
        
        # 显示摘要
        if self.config['notifications'].get('show_summary', True):
            self._show_summary()
        
        # 保存日志
        if self.config['logging'].get('enabled', True):
            self._save_log()
        
        # 播放提示音
        if self.config['notifications'].get('sound_on_complete', False):
            print('\a')  # 终端响铃
        
        return self.stats['failed'] == 0

def main():
    """主函数"""
    # 获取脚本所在目录
    script_dir = Path(__file__).parent
    default_config = script_dir / 'sync_config.json'
    
    # 命令行参数解析
    parser = argparse.ArgumentParser(description='docs目录同步工具')
    parser.add_argument('-c', '--config', default=str(default_config),
                       help='配置文件路径 (默认: ./sync_config.json)')
    parser.add_argument('-s', '--source', help='覆盖源文件夹名')
    parser.add_argument('-t', '--target', help='覆盖目标文件夹名')
    parser.add_argument('--delete', action='store_true', help='删除目标中多余文件')
    parser.add_argument('--dry-run', action='store_true', help='模拟运行，不实际修改')
    parser.add_argument('--compare-content', action='store_true', 
                       help='比较文件内容而不是修改时间')
    
    args = parser.parse_args()
    
    # 创建同步器
    syncer = DocSync(args.config)
    
    # 命令行参数覆盖配置
    if args.source:
        syncer.config['source_folder'] = args.source
    if args.target:
        syncer.config['target_folder'] = args.target
    if args.delete:
        syncer.config['sync_options']['delete_extra_files'] = True
    if args.dry_run:
        syncer.config['sync_options']['dry_run'] = True
    if args.compare_content:
        syncer.config['sync_options']['compare_content'] = True
    
    # 运行同步
    success = syncer.run()
    
    # 返回退出码
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()