# 这是一个快速部署此预发布版本的方案，部署本服务前，请按以下步骤操作：
## 确认本地有Python环境
*（可选，跳过则部署时环境变量中除API KEY外的密钥均为硬编码默认值）*

打开终端（Windows：CMD/PowerShell；macOS/Linux：Terminal(Bash/Shell)）并运行：
```bash
python --version
```
*如果显示 Python 3.8 或更高版本，您可跳过安装。如果版本低于3.8或提示“未找到命令”，请继续。*

### Windows / macOS
1.  推荐访问 [Python官网下载页](https://www.python.org/downloads/)

2.  点击页面中央醒目的黄色按钮下载最新版安装程序。

3.  运行安装程序，务必勾选 Add Python to PATH (Windows) 或 Install Certificates (macOS) 选项。

4.  点击“Install Now”完成安装。

### Linux
大多数发行版已预装Python。如需安装或更新，请在终端运行：
```bash
# Ubuntu/Debian
sudo apt update && sudo apt install python3 python3-pip

# CentOS/RHEL/Fedora
sudo yum install python3 python3-pip  # 或使用 dnf
```
安装完成后，请重启终端，再次运行 python --version（Linux/macOS可能需要使用 python3）。应显示类似 Python 3.12.3 的版本信息。

---
## 在阿里云百炼平台开通服务并获取密钥(确保AI功能可用)
1.  【开通平台】访问 [阿里云百炼](https://bailian.console.aliyun.com)，登录/注册阿里云账号，可能需要实名认证。同意协议后会自动开通大模型百炼服务，阿里云为每个新用户提供了丰厚的免费额度。
2.  【获取密钥】点击进入左下角“密钥管理”页面，创建一个新的API Key，并**妥善保存**。
3.  【选择模型】在同一平台查看“模型服务”列表，记下您想调用的模型名称（如 `qwen-max`、`qwen-plus`、qwen-turbo）。
4.  【配置启动】将获得的 `API Key` 和 `模型名称` 填入配置文件或作为环境变量提供给本服务。

注意：API Key 是您的个人密钥，请勿泄露。

## 快速开始：
### Windows：
双击运行该目录（scripts/）下的[deploy.bat](deploy.bat)（Windows批处理文件），跟随指引操作即可。

### Linux/MacOS:
双击运行该目录（scripts/）下的[deploy.sh](deploy.sh)，跟随指引操作即可。