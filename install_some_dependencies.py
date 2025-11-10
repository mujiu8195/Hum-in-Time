import subprocess
import sys
import importlib

def check_and_install_package(package_name, install_name=None):
    if install_name is None:
        install_name = package_name
    
    try:
        importlib.import_module(package_name)
        print(f"✓ {package_name} 已安装")
    except ImportError:
        print(f"✗ 未找到 {package_name}，正在安装...")
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", install_name])
            print(f"✓ {package_name} 安装成功")
        except Exception as e:
            print(f"✗ 安装 {install_name} 失败: {str(e)}")
            return False
    return True

def install_some_dependencies():
    print("开始安装SOME所需的依赖...")
    
    dependencies = [
        ("torch", "torch"),
        ("mido", "mido"),
        ("lightning", "lightning"),
        ("librosa", "librosa"),
        ("yaml", "pyyaml"),
        ("click", "click"),
        ("pretty_midi", "pretty_midi"),
        ("numpy", "numpy"),
        ("scipy", "scipy")
    ]
    
    all_success = True
    for package, install_name in dependencies:
        success = check_and_install_package(package, install_name)
        all_success = all_success and success
    
    if all_success:
        print("\n所有SOME依赖已成功安装！现在您应该能够运行SOME了。")
    else:
        print("\n部分依赖安装失败，请手动检查并安装缺失的依赖。")

if __name__ == "__main__":
    install_some_dependencies()