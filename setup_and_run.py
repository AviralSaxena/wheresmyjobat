#!/usr/bin/env python3
"""
WheresMyJobAt Setup and Run Script
Cross-platform script to set up virtual environment, install dependencies, and start the application
"""
import os
import sys
import subprocess
import platform
import time
import signal
import socket

from pathlib import Path

class WheresMyJobAtLauncher:
    def __init__(self):
        self.system = platform.system().lower()
        self.project_root = Path(__file__).parent
        self.venv_path = self.project_root / "venv"
        self.processes = []

        os.environ.setdefault("FRONTEND_URL", "http://localhost")
        os.environ.setdefault("BACKEND_URL", "http://localhost")

        os.environ.setdefault("HOST", "localhost")

        # Will be dynamically set
        self.frontend_port = None
        self.backend_port = None
        
        # Platform-specific commands
        if self.system == "windows":
            self.python_cmd = "python"
            self.pip_cmd = "pip"
            self.venv_activate = self.venv_path / "Scripts" / "activate.bat"
            self.venv_python = self.venv_path / "Scripts" / "python.exe"
            self.venv_pip = self.venv_path / "Scripts" / "pip.exe"
            self.venv_uv = self.venv_path / "Scripts" / "uv.exe"
        else:  # Linux/Mac
            self.python_cmd = "python3"
            self.pip_cmd = "pip3"
            self.venv_activate = self.venv_path / "bin" / "activate"
            self.venv_python = self.venv_path / "bin" / "python"
            self.venv_pip = self.venv_path / "bin" / "pip"
            self.venv_uv = self.venv_path / "bin" / "uv"

    def get_free_port(self, start=5000, end=9000):
        for port in range(start, end):
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                try:
                    s.bind((os.getenv('HOST'), port))
                    return port
                except OSError:
                    continue
        raise RuntimeError("No available port found in range.")

    def run_command(self, command, cwd=None, shell=True):
        try:
            result = subprocess.run(
                command, 
                shell=shell, 
                check=True, 
                capture_output=True, 
                text=True,
                cwd=cwd
            )
            return True, result.stdout
        except subprocess.CalledProcessError as e:
            return False, e.stderr
        except FileNotFoundError:
            return False, f"Command not found: {command}"

    def check_python(self):
        print("🔍 Checking Python installation...")
        success, output = self.run_command(f"{self.python_cmd} --version")
        if success:
            print(f"✅ Python found: {output.strip()}")
            return True
        else:
            print("❌ Python not found. Please install Python 3.8+ first.")
            return False

    def create_venv(self):
        if self.venv_path.exists():
            print(f"📁 Virtual environment already exists at {self.venv_path}")
            return True
        
        print("🔨 Creating virtual environment...")
        success, output = self.run_command(f"{self.python_cmd} -m venv venv")
        if success:
            print("✅ Virtual environment created successfully")
            return True
        else:
            print(f"❌ Failed to create virtual environment: {output}")
            return False

    def check_and_install_uv(self):
        if self.venv_uv.exists():
            print("✅ uv is already installed in virtual environment")
            return True
        
        success, _ = self.run_command("uv --version")
        if success:
            print("✅ uv found globally")
            return True
        
        print("📦 Installing uv for faster package management...")
        
        success, output = self.run_command(f'"{self.venv_pip}" install uv')
        if success:
            print("✅ uv installed successfully")
            return True
        else:
            print(f"⚠️ Failed to install uv, will fall back to pip: {output}")
            return False

    def update_env_variable(self, key, value):
        env_path = self.project_root / ".env"
        lines = []
        found = False

        # Read and modify or append key
        if env_path.exists():
            with open(env_path, "r") as f:
                for line in f:
                    if line.strip().startswith(f"{key}="):
                        lines.append(f"{key}='{value}'\n")
                        found = True
                    else:
                        lines.append(line)
        if not found:
            lines.append(f"{key}='{value}'\n")

        # Write back to .env
        with open(env_path, "w") as f:
            f.writelines(lines)

    def install_requirements(self):
        requirements_file = self.project_root / "requirements.txt"
        if not requirements_file.exists():
            print("❌ requirements.txt not found!")
            return False
        
        print("📦 Installing requirements...")
        
        # Try to use uv first (much faster)
        if self.check_and_install_uv():
            print("🚀 Using uv for super-fast package installation...")
            
            uv_command = f'"{self.venv_uv}" pip install -r requirements.txt --python "{self.venv_python}"'
            
            success, output = self.run_command(uv_command)
            if success:
                print("✅ Requirements installed successfully with uv")
                return True
            else:
                print(f"⚠️ uv installation failed, falling back to pip: {output}")
        
        # Fallback to pip
        print("📦 Using pip for package installation...")
        success, output = self.run_command(f'"{self.venv_pip}" install -r requirements.txt')
        if success:
            print("✅ Requirements installed successfully with pip")
            return True
        else:
            print(f"❌ Failed to install requirements: {output}")
            return False

    def check_env_file(self):
        env_file = self.project_root / ".env"
        env_example = self.project_root / ".env-example"
        
        if not env_file.exists():
            print("❌ .env file not found in root directory")
            if env_example.exists():
                print(f"💡 Copy {env_example} to .env and add the three API keys")
            else:
                print("💡 Create .env with the three API keys")
            print("🛑 Application cannot start without proper environment configuration")
            return False

        env_vars = {}
        try:
            with open(env_file, 'r') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#') and '=' in line:
                        key, value = line.split('=', 1)
                        value = value.strip().strip('"').strip("'")
                        env_vars[key.strip()] = value
        except Exception as e:
            print(f"❌ Error reading .env file: {e}")
            return False
        
        required_vars = {
            'GMAIL_CLIENT_ID': 'Gmail OAuth Client ID',
            'GMAIL_CLIENT_SECRET': 'Gmail OAuth Client Secret', 
            'GEMINI_API_KEY': 'Google Gemini API Key'
        }

        missing_vars = []
        for var_name, description in required_vars.items():
            value = env_vars.get(var_name, '').strip()
            if not value or value == "''":
                missing_vars.append(f"  - {var_name}: {description}")
        
        if missing_vars:
            print("❌ Required environment variables are missing or empty:")
            for var in missing_vars:
                print(var)
            print(f"\n💡 Please edit {env_file} and set all required values")
            print("🛑 Application cannot start without proper environment configuration")
            return False
        
        print("✅ All required environment variables are set")
        return True

    def start_backend(self):
        server_dir = self.project_root / "server"
        self.backend_port = self.get_free_port(5000, 6000)
        os.environ["BACKEND_PORT"] = str(self.backend_port)
        self.update_env_variable("BACKEND_PORT", self.backend_port)

        print(f"🚀 Starting Flask backend on {os.getenv("BACKEND_URL", "http://localhost")}:{self.backend_port}...")

        command = [
            str(self.venv_python),
            "app.py",
            f"--port={self.backend_port}"
        ]

        if self.system == "windows":
            process = subprocess.Popen(
                " ".join(command),
                shell=True,
                cwd=server_dir,
                creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if hasattr(subprocess, 'CREATE_NEW_PROCESS_GROUP') else 0
            )
        else:
            process = subprocess.Popen(
                command,
                cwd=server_dir
            )

        self.processes.append(("backend", process))
        return process

    def start_frontend(self):
        client_dir = self.project_root / "client"
        self.frontend_port = self.get_free_port(8501, 8600)
        os.environ["FRONTEND_PORT"] = str(self.frontend_port)
        self.update_env_variable("FRONTEND_PORT", self.frontend_port)
        print(f"🚀 Starting Streamlit frontend on {os.getenv("FRONTEND_URL", "http://localhost")}:{self.frontend_port}...")

        command = [
            str(self.venv_python),
            "-m",
            "streamlit",
            "run",
            "client.py",
            f"--server.port={self.frontend_port}"
        ]

        if self.system == "windows":
            process = subprocess.Popen(
                " ".join(command),
                shell=True,
                cwd=client_dir,
                creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if hasattr(subprocess, 'CREATE_NEW_PROCESS_GROUP') else 0
            )
        else:
            process = subprocess.Popen(
                command,
                cwd=client_dir
            )

        self.processes.append(("frontend", process))
        return process

    def wait_for_services(self):
        print("⏳ Waiting for services to start...")
        time.sleep(3)

        # Check if backend is running
        try:
            import urllib.request
            urllib.request.urlopen(f"{os.getenv("FRONTEND_URL", "http://localhost")}:{self.backend_port}/api/health", timeout=5)
            print(f"✅ Backend is running on {os.getenv("BACKEND_URL", "http://localhost")}:{self.backend_port}")
        except:
            print("⚠️  Backend might still be starting...")

        print(f"✅ Frontend should be available at {os.getenv("FRONTEND_URL", "http://localhost")}:{self.frontend_port}")

    def cleanup(self):
        print("\n🛑 Shutting down services...")
        for name, process in self.processes:
            try:
                if self.system == "windows":
                    process.send_signal(signal.CTRL_BREAK_EVENT)
                else:
                    process.terminate()
                try:
                    process.wait(timeout=5)
                    print(f"✅ {name} stopped gracefully")
                except subprocess.TimeoutExpired:
                    process.kill()
                    print(f"🔴 {name} force killed after timeout")
            except Exception as e:
                print(f"⚠️ Could not stop {name}: {e}")


    def setup_signal_handlers(self):
        def signal_handler(signum, frame):
            self.cleanup()
            sys.exit(0)
        
        signal.signal(signal.SIGINT, signal_handler)
        if hasattr(signal, 'SIGTERM'):
            signal.signal(signal.SIGTERM, signal_handler)

    def run(self):
        print("🚀 WheresMyJobAt - Auto Job Application Tracker")
        print("=" * 50)

        self.setup_signal_handlers()

        if not self.check_python(): return False
        if not self.create_venv(): return False
        if not self.install_requirements(): return False
        if not self.check_env_file(): return False

        print("\n🎯 Starting WheresMyJobAt services...")
        print("-" * 30)

        self.start_backend()
        time.sleep(2)
        self.start_frontend()
        self.wait_for_services()

        print("\n🎉 WheresMyJobAt is now running!")
        print(f"📊 Dashboard: {os.getenv("FRONTEND_URL", "http://localhost")}:{self.frontend_port}")
        print(f"🔧 API: {os.getenv("BACKEND_URL", "http://localhost")}:{self.backend_port}")
        print("\n💡 To stop the application, press Ctrl+C")

        try:
            while True:
                time.sleep(1)
                for name, process in self.processes:
                    if process.poll() is not None:
                        print(f"⚠️  {name} process stopped unexpectedly")
                        return False
        except KeyboardInterrupt:
            pass
        finally:
            self.cleanup()

        return True

if __name__ == "__main__":
    launcher = WheresMyJobAtLauncher()
    success = launcher.run()
    sys.exit(0 if success else 1)
