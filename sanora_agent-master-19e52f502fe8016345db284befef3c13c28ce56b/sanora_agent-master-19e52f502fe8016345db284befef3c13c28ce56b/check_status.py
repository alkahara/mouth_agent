#!/usr/bin/env python3
"""
项目状态检查脚本
检查配置、依赖和服务可用性
"""

import os
import sys
import yaml
import importlib.util
from pathlib import Path


def check_python_version():
    """检查 Python 版本"""
    print("=== Python 环境检查 ===")
    version = sys.version_info
    print(f"Python 版本: {version.major}.{version.minor}.{version.micro}")

    if version.major < 3 or (version.major == 3 and version.minor < 8):
        print("❌ 需要 Python 3.8 或更高版本")
        return False
    else:
        print("✅ Python 版本符合要求")
        return True


def check_dependencies():
    """检查依赖包"""
    print("\n=== 依赖包检查 ===")

    required_packages = [
        "fastapi",
        "uvicorn",
        "pydantic",
        "langgraph",
        "langchain",
        "python-dotenv",
        "yaml",
        "httpx",
    ]

    missing_packages = []

    for package in required_packages:
        try:
            if package == "yaml":
                package = "pyyaml"
            spec = importlib.util.find_spec(package.replace("-", "_"))
            if spec is None:
                missing_packages.append(package)
                print(f"❌ {package}")
            else:
                print(f"✅ {package}")
        except ImportError:
            missing_packages.append(package)
            print(f"❌ {package}")

    if missing_packages:
        print(f"\n缺少依赖包: {', '.join(missing_packages)}")
        print("运行: pip install -r requirements.txt")
        return False
    else:
        print("✅ 所有依赖包已安装")
        return True


def check_config_files():
    """检查配置文件"""
    print("\n=== 配置文件检查 ===")

    files_to_check = [("config.yaml", True), (".env", False), (".env.example", True)]

    all_good = True

    for filename, required in files_to_check:
        if os.path.exists(filename):
            print(f"✅ {filename}")
        else:
            if required:
                print(f"❌ {filename} (必需)")
                all_good = False
            else:
                print(f"⚠️  {filename} (建议)")

    return all_good


def check_langgraph_config():
    """检查 LangGraph 配置"""
    print("\n=== LangGraph 配置检查 ===")

    try:
        with open("config.yaml", 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)

        langgraph_apps = config.get("langgraph_apps", {})

        if not langgraph_apps:
            print("❌ 没有配置 LangGraph 应用")
            return False

        print(f"发现 {len(langgraph_apps)} 个 LangGraph 应用:")

        enabled_count = 0
        for app_id, app_config in langgraph_apps.items():
            enabled = app_config.get("enabled", True)
            status = "启用" if enabled else "禁用"
            print(f"  - {app_id}: {app_config.get('name', 'N/A')} ({status})")
            print(f"    API Key: {app_config.get('api_key', 'N/A')}")
            print(f"    模型: {app_config.get('model_provider', 'N/A')}")

            if enabled:
                enabled_count += 1

        if enabled_count == 0:
            print("⚠️  没有启用的 LangGraph 应用")
            return False
        else:
            print(f"✅ {enabled_count} 个应用已启用")
            return True

    except Exception as e:
        print(f"❌ 配置文件解析错误: {e}")
        return False


def check_env_vars():
    """检查环境变量"""
    print("\n=== 环境变量检查 ===")

    if not os.path.exists(".env"):
        print("⚠️  .env 文件不存在，将使用系统环境变量")

    required_vars = [
        "OPENAI_API_KEY",
        "QWEN_API_KEY",
        "ANTHROPIC_API_KEY",
        "MOONSHOT_API_KEY",
    ]

    from dotenv import load_dotenv

    load_dotenv()

    found_keys = 0
    for var in required_vars:
        value = os.getenv(var)
        if value and value != "your_" + var.lower() + "_here":
            print(f"✅ {var}")
            found_keys += 1
        else:
            print(f"❌ {var}")

    if found_keys == 0:
        print("❌ 没有找到有效的 API 密钥")
        return False
    else:
        print(f"✅ 找到 {found_keys} 个 API 密钥")
        return True


def main():
    """主检查函数"""
    print("OpenAI Compatible API Server - 项目状态检查")
    print("=" * 50)

    checks = [
        check_python_version(),
        check_dependencies(),
        check_config_files(),
        check_langgraph_config(),
        check_env_vars(),
    ]

    print("\n" + "=" * 50)
    print("=== 检查结果汇总 ===")

    passed = sum(checks)
    total = len(checks)

    print(f"通过: {passed}/{total}")

    if passed == total:
        print("✅ 所有检查通过，可以启动服务器！")
        print("\n启动命令:")
        print("  python run_server.py")
        print("  # 或者")
        print("  ./start.sh  (Linux/Mac)")
        print("  start.bat   (Windows)")
    else:
        print("❌ 存在问题，请修复后再启动服务器")
        print("\n建议:")
        if not checks[1]:  # 依赖检查失败
            print("  1. 安装依赖: pip install -r requirements.txt")
        if not checks[4]:  # 环境变量检查失败
            print("  2. 配置 API 密钥: 编辑 .env 文件")


if __name__ == "__main__":
    main()
