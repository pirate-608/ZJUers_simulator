#!/usr/bin/env python3
"""
Docker一键部署脚本
支持 Windows/Linux/macOS，自动检测Docker环境并部署
"""

import os
import sys
import subprocess
import shutil
from pathlib import Path
import platform
import json
import time
import secrets
import string


class DockerDeployer:
    def __init__(self):
        self.root_dir = Path(__file__).parent.parent  # 回到项目根目录
        self.platform = platform.system().lower()

    def log(self, message):
        print(f"[部署] {message}")

    def check_docker(self):
        """检查Docker环境"""
        self.log("检查Docker环境...")

        try:
            result = subprocess.run(
                ["docker", "--version"], capture_output=True, text=True
            )
            if result.returncode == 0:
                self.log(f"✅ {result.stdout.strip()}")
            else:
                raise subprocess.CalledProcessError(result.returncode, "docker")
        except (subprocess.CalledProcessError, FileNotFoundError):
            self.log("❌ Docker未安装或未启动")
            self.show_docker_install_guide()
            return False

        try:
            result = subprocess.run(
                ["docker", "compose", "--version"], capture_output=True, text=True
            )
            if result.returncode == 0:
                self.log(f"✅ {result.stdout.strip()}")
            else:
                # 尝试旧版本命令
                result = subprocess.run(
                    ["docker-compose", "--version"], capture_output=True, text=True
                )
                if result.returncode == 0:
                    self.log(f"✅ {result.stdout.strip()}")
                else:
                    raise subprocess.CalledProcessError(
                        result.returncode, "docker-compose"
                    )
        except (subprocess.CalledProcessError, FileNotFoundError):
            self.log("❌ Docker Compose未安装")
            return False

        return True

    def show_docker_install_guide(self):
        """显示Docker安装指南"""
        self.log("=" * 60)
        self.log("Docker安装指南:")

        if self.platform == "windows":
            self.log("Windows:")
            self.log("1. 下载 Docker Desktop")
            self.log("   https://www.docker.com/products/docker-desktop/")
            self.log("2. 安装并启动 Docker Desktop")
            self.log("3. 确保Docker正在运行（系统托盘有Docker图标）")
        elif self.platform == "darwin":
            self.log("macOS:")
            self.log("1. 下载 Docker Desktop for Mac")
            self.log("   https://www.docker.com/products/docker-desktop/")
            self.log("2. 安装并启动应用")
        else:
            self.log("Linux:")
            self.log("1. 安装Docker引擎:")
            self.log("   curl -fsSL https://get.docker.com -o get-docker.sh")
            self.log("   sh get-docker.sh")
            self.log("2. 启动Docker服务:")
            self.log("   sudo systemctl start docker")
            self.log("   sudo systemctl enable docker")

        self.log("=" * 60)

    def generate_random_password(self, length=16):
        """生成随机密码"""
        alphabet = string.ascii_letters + string.digits + "!@#$%^&*"
        return "".join(secrets.choice(alphabet) for _ in range(length))

    def generate_secret_key(self, length=50):
        """生成安全密钥"""
        return secrets.token_urlsafe(length)

    def get_llm_config(self):
        """获取用户LLM配置"""
        print()
        print("=" * 60)
        print("🤖 AI功能配置 (可选)")
        print("=" * 60)
        print("AI功能需要阿里云百炼平台的API密钥。")
        print("详细获取步骤请查看 scripts/README.md")
        print()

        # 询问是否配置AI功能
        while True:
            choice = input("是否现在配置AI功能？(y/n) [默认:n]: ").strip().lower()
            if choice in ["", "n", "no"]:
                return None, None
            elif choice in ["y", "yes"]:
                break
            else:
                print("请输入 y 或 n")

        print()
        print("📋 获取步骤：")
        print("1. 访问阿里云百炼: https://bailian.console.aliyun.com")
        print("2. 登录/注册并完成实名认证")
        print("3. 开通服务后，进入'密钥管理'创建API Key")
        print("4. 在'模型服务'中选择模型（如 qwen-max, qwen-plus, qwen-turbo）")
        print()

        # 获取API Key
        while True:
            api_key = input("请输入API Key (以sk-开头): ").strip()
            if not api_key:
                print("API Key不能为空")
                continue
            if not api_key.startswith("sk-"):
                print("警告：API Key通常以'sk-'开头，请确认输入正确")
            break

        # 获取模型名称
        print()
        print("💡 推荐模型：")
        print("  - qwen-max (最强能力，适合复杂任务)")
        print("  - qwen-plus (平衡性能与成本)")
        print("  - qwen-turbo (快速响应，低成本)")

        while True:
            model = input("请输入模型名称 [默认: qwen-turbo]: ").strip()
            if not model:
                model = "qwen-turbo"
            break

        return api_key, model

    def create_env_file(self):
        """创建环境变量文件"""
        env_file = self.root_dir / ".env"

        if env_file.exists():
            self.log(f"✅ 环境文件已存在: {env_file}")
            return

        self.log("创建环境变量文件...")

        # 生成随机密码和密钥
        db_password = self.generate_random_password(16)
        secret_key = self.generate_secret_key()

        # 获取LLM配置
        api_key, model = self.get_llm_config()

        # 构建环境变量内容
        env_content = f"""# ZJUers Simulator 环境配置
# 自动生成于 {time.strftime('%Y-%m-%d %H:%M:%S')}

# 数据库配置
DATABASE_URL=postgresql+asyncpg://zju:{db_password}@db/zjuers
POSTGRES_PASSWORD={db_password}

# 应用安全密钥
SECRET_KEY={secret_key}

# 大模型配置 (阿里云百炼)
LLM_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1"""

        if api_key and model:
            env_content += f"""
LLM_API_KEY={api_key}
LLM={model}
"""
        else:
            env_content += """
LLM_API_KEY=
LLM=qwen-turbo
"""

        env_content += """
# 其他配置
REDIS_URL=redis://redis:6379/0
"""

        # 保存文件
        with open(env_file, "w", encoding="utf-8") as f:
            f.write(env_content)

        self.log(f"✅ 环境文件已创建: {env_file}")

        # 显示配置摘要
        if api_key:
            self.log(f"✅ AI功能已配置 (模型: {model})")
        else:
            self.log("ℹ️ AI功能未配置，如需使用请编辑 .env 文件")

        # 安全提醒
        print()
        print("🔒 安全提醒:")
        print(f"   .env 文件包含敏感信息，请勿分享给他人")
        print(f"   数据库密码: {db_password[:4]}****")
        if api_key:
            print(f"   API Key: {api_key[:8]}****")

    def pull_or_build_images(self):
        """拉取或构建镜像"""
        self.log("准备Docker镜像...")

        # 尝试拉取预构建镜像（如果有的话）
        try:
            result = subprocess.run(
                ["docker", "pull", "zjuers/simulator:latest"], capture_output=True
            )

            if result.returncode == 0:
                self.log("✅ 成功拉取预构建镜像")
                return True
        except:
            pass

        # 本地构建镜像
        self.log("正在构建Docker镜像（首次运行需要几分钟）...")

        result = subprocess.run(
            ["docker", "compose", "build", "--no-cache"], cwd=self.root_dir
        )

        if result.returncode == 0:
            self.log("✅ 镜像构建完成")
            return True
        else:
            self.log("❌ 镜像构建失败")
            return False

    def deploy(self):
        """部署服务"""
        self.log("启动服务...")

        result = subprocess.run(["docker", "compose", "up", "-d"], cwd=self.root_dir)

        if result.returncode == 0:
            self.log("✅ 服务启动成功")
            return True
        else:
            self.log("❌ 服务启动失败")
            return False

    def wait_for_service(self):
        """等待服务就绪"""
        self.log("等待服务启动...")

        import time
        import urllib.request

        for i in range(30):  # 最多等待30秒
            try:
                with urllib.request.urlopen("http://localhost:8000") as response:
                    if response.getcode() == 200:
                        self.log("✅ 服务已就绪")
                        return True
            except:
                pass

            time.sleep(1)
            print(".", end="", flush=True)

        print()
        self.log("⚠️ 服务启动可能较慢，请稍后访问")
        return False

    def open_browser(self):
        """打开浏览器"""
        url = "http://localhost:8000"
        self.log(f"正在打开浏览器: {url}")

        try:
            if self.platform == "windows":
                os.startfile(url)
            elif self.platform == "darwin":
                subprocess.run(["open", url])
            else:
                subprocess.run(["xdg-open", url])
        except:
            self.log(f"请手动访问: {url}")

    def show_status(self):
        """显示服务状态"""
        self.log("=" * 60)
        self.log("🎉 部署完成！")
        self.log("=" * 60)
        self.log("📋 服务信息:")
        self.log("  🌐 访问地址: http://localhost:8000")
        self.log("  🗄️  数据库: PostgreSQL (端口5432)")
        self.log("  💾 缓存: Redis (端口6379)")
        self.log("")
        self.log("🔧 管理命令:")
        self.log("  查看状态: docker compose ps")
        self.log("  查看日志: docker compose logs -f")
        self.log("  停止服务: docker compose down")
        self.log("  重启服务: docker compose restart")
        self.log("=" * 60)

    def run(self):
        """执行完整部署流程"""
        self.log("🚀 开始部署 ZJUers Simulator...")

        # 1. 检查Docker环境
        if not self.check_docker():
            return False

        # 2. 创建环境文件
        self.create_env_file()

        # 3. 构建或拉取镜像
        if not self.pull_or_build_images():
            return False

        # 4. 部署服务
        if not self.deploy():
            return False

        # 5. 等待服务就绪
        self.wait_for_service()

        # 6. 显示状态信息
        self.show_status()

        # 7. 自动打开浏览器
        self.open_browser()

        return True


if __name__ == "__main__":
    deployer = DockerDeployer()

    try:
        success = deployer.run()
        if success:
            input("\n按回车键退出...")
        else:
            input("\n部署失败，按回车键退出...")
            sys.exit(1)
    except KeyboardInterrupt:
        print("\n用户取消部署")
        sys.exit(1)
    except Exception as e:
        print(f"\n部署异常: {e}")
        sys.exit(1)
