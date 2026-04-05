import asyncio
import os
import shlex
import shutil
import subprocess
import sys
from datetime import datetime

import psutil
from dotenv import dotenv_values

from .database import get_project_by_id, update_project_execution_info


running_processes = {}

SAFEGUARD_PATH = "/opt/bytesupreme_safeguards"
IS_WINDOWS = os.name == "nt"
FIREJAIL_AVAILABLE = (not IS_WINDOWS) and shutil.which("firejail") is not None

FIREJAIL_PROFILE = [
    "firejail",
    "--quiet",
    "--noprofile",
    "--private={project_path}",
    "--whitelist={project_path}",
    "--read-only=/opt/bytesupreme_safeguards",
    "--rlimit-as={ram_in_bytes}",
    "--cpu={cpu_cores}",
]


def get_host_python() -> str:
    return sys.executable or shutil.which("python3") or shutil.which("python") or "python3"


def get_venv_python(project_path: str) -> str:
    if IS_WINDOWS:
        return os.path.join(project_path, ".venv", "Scripts", "python.exe")
    return os.path.join(project_path, ".venv", "bin", "python")


def get_venv_python_relative() -> str:
    if IS_WINDOWS:
        return os.path.join(".venv", "Scripts", "python.exe")
    return os.path.join(".venv", "bin", "python")


def _get_venv_bin(project_path: str) -> str:
    if IS_WINDOWS:
        return os.path.join(project_path, ".venv", "Scripts")
    return os.path.join(project_path, ".venv", "bin")


def _build_process_env(project: dict) -> dict:
    user_env_path = os.path.join(project["path"], ".env")
    user_env_vars = dotenv_values(user_env_path) if os.path.exists(user_env_path) else {}
    venv_bin = _get_venv_bin(project["path"])
    path_value = os.environ.get("PATH", "")
    env = {
        **os.environ,
        "PATH": f"{venv_bin}{os.pathsep}{path_value}" if path_value else venv_bin,
        "HOME": project["path"] if not IS_WINDOWS else os.environ.get("USERPROFILE", project["path"]),
        **user_env_vars,
    }
    if not IS_WINDOWS:
        env["PYTHONPATH"] = SAFEGUARD_PATH
    return env


def _normalize_run_command(project: dict) -> list[str]:
    raw_command = project.get("run_command", "python3 main.py").strip()
    tokens = shlex.split(raw_command)
    if not tokens:
        return [get_venv_python_relative(), "main.py"]

    first = tokens[0].lower()
    python_aliases = {"python", "python3", "python.exe", "py"}
    if first in python_aliases:
        return [get_venv_python_relative(), *tokens[1:]]
    if tokens[0].endswith(".py"):
        return [get_venv_python_relative(), *tokens]
    return tokens


async def install_project_dependencies(project_id, project):
    project_path = project["path"]
    venv_path = os.path.join(project_path, ".venv")
    requirements_path = os.path.join(project_path, "requirements.txt")

    if not os.path.exists(venv_path):
        create_venv_cmd = [get_host_python(), "-m", "venv", venv_path]
        process = await asyncio.create_subprocess_exec(
            *create_venv_cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        _, stderr = await process.communicate()
        if process.returncode != 0:
            return False, f"Failed to create virtual environment:\n{stderr.decode()}"

    if os.path.exists(requirements_path):
        venv_python_relative = get_venv_python_relative()
        pip_install_cmd = [venv_python_relative, "-m", "pip", "install", "--no-cache-dir", "-r", "requirements.txt"]
        full_cmd = await _build_execution_command(project, pip_install_cmd)

        process = await asyncio.create_subprocess_exec(
            *full_cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=project_path,
            close_fds=not IS_WINDOWS,
            env=_build_process_env(project),
        )
        _, stderr = await process.communicate()
        if process.returncode != 0:
            return False, f"Failed to install dependencies:\n{stderr.decode()}"

    return True, "Virtual environment is ready. Dependencies installed."


async def _build_execution_command(project: dict, base_command: list[str] | None = None) -> list[str]:
    project_path = project["path"]
    ram_limit_mb = project.get("resource_limits", {}).get("ram", 512)
    run_cmd = base_command or _normalize_run_command(project)

    script_candidate = None
    if len(run_cmd) >= 2 and run_cmd[0] == get_venv_python_relative() and run_cmd[1].endswith(".py"):
        script_candidate = run_cmd[1]
    elif run_cmd and run_cmd[0].endswith(".py"):
        script_candidate = run_cmd[0]

    if script_candidate and not os.path.exists(os.path.join(project_path, script_candidate)):
        raise FileNotFoundError(f"Main script '{script_candidate}' not found.")

    if not FIREJAIL_AVAILABLE:
        return run_cmd

    ram_in_bytes = ram_limit_mb * 1024 * 1024
    cpu_cores_list = "0"
    firejail_cmd = [
        part.format(project_path=project_path, ram_in_bytes=ram_in_bytes, cpu_cores=cpu_cores_list)
        for part in FIREJAIL_PROFILE
    ]
    return firejail_cmd + run_cmd


async def start_project(project_id: str, project: dict):
    if project_id in running_processes and running_processes[project_id].poll() is None:
        return False, "Project is already running."

    try:
        venv_python = get_venv_python(project["path"])
        if not os.path.exists(venv_python):
            return False, "Virtual environment not found. Please run Install Dependencies first."

        cmd_list = await _build_execution_command(project)
        log_file = open(project["execution_info"]["log_file"], "w", encoding="utf-8")
        process_env = _build_process_env(project)

        popen_kwargs = {
            "cwd": project["path"],
            "stdout": log_file,
            "stderr": log_file,
            "close_fds": not IS_WINDOWS,
            "env": process_env,
        }
        if IS_WINDOWS:
            popen_kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
        else:
            popen_kwargs["start_new_session"] = True

        process = subprocess.Popen(cmd_list, **popen_kwargs)
        running_processes[project_id] = process

        await update_project_execution_info(
            project_id,
            {
                "is_running": True,
                "pid": process.pid,
                "last_run_time": datetime.utcnow(),
                "status": "running",
            },
        )

        ram_allocated = project.get("resource_limits", {}).get("ram")
        return True, f"Process started with PID: {process.pid}. RAM allocated: {ram_allocated}MB."

    except FileNotFoundError as error:
        return False, f"Execution failed: required file missing. Details: {error}"
    except Exception as error:
        return False, f"Execution failed: {error}"


async def stop_project(project_id):
    if project_id not in running_processes:
        return False, "Project is not running or process not tracked."

    process = running_processes.pop(project_id)
    if process.poll() is not None:
        return False, "Process was already stopped."

    try:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()

        await update_project_execution_info(
            project_id,
            {"is_running": False, "pid": None, "status": "stopped"},
        )
        return True, "Process terminated successfully."
    except Exception as error:
        return False, f"Failed to stop process: {error}"


async def restart_project(project_id, project):
    await stop_project(project_id)
    await asyncio.sleep(1)
    return await start_project(project_id, project)


async def get_project_status(project_id, project, detailed=False):
    exec_info = project["execution_info"]
    is_running = False

    if project_id in running_processes and running_processes[project_id].poll() is None:
        is_running = True

    if is_running:
        status, pid = "🟢 Running", running_processes[project_id].pid
        try:
            process = psutil.Process(pid)
            uptime = datetime.now() - datetime.fromtimestamp(process.create_time())
            uptime_str = str(uptime).split(".")[0]
        except psutil.NoSuchProcess:
            status, pid, uptime_str = "🔴 Stopped (process missing)", "N/A", "N/A"
    else:
        status, pid, uptime_str = "🔴 Stopped", "N/A", "N/A"
        if exec_info.get("is_running"):
            await update_project_execution_info(
                project_id,
                {"is_running": False, "pid": None, "status": "crashed"},
            )
            status = "🟠 Crashed"

    if not detailed:
        return status

    last_run_str = "Never"
    if isinstance(exec_info.get("last_run_time"), datetime):
        last_run_str = exec_info["last_run_time"].strftime("%Y-%m-%d %H:%M:%S UTC")

    return (
        f"Status: {status}\n"
        f"PID: `{pid}`\n"
        f"Uptime: `{uptime_str}`\n"
        f"Last Run: `{last_run_str}`\n"
        f"Last Exit Code: `{exec_info.get('exit_code', 'N/A')}`\n"
        f"Run Command: `{project.get('run_command')}`"
    )


async def get_project_logs(project_id):
    project = await get_project_by_id(project_id)
    return project["execution_info"]["log_file"]


async def get_project_usage(project_id):
    if project_id not in running_processes:
        return "Project is not running."
    if running_processes[project_id].poll() is not None:
        return "Project is stopped."

    try:
        process = psutil.Process(running_processes[project_id].pid)
        cpu_usage = process.cpu_percent(interval=1)
        mem_info = process.memory_info()
        ram_usage = mem_info.rss / (1024 * 1024)
        return f"CPU: {cpu_usage:.2f}% | RAM: {ram_usage:.2f} MB"
    except psutil.NoSuchProcess:
        return "Process not found. It might have stopped."
    except Exception as error:
        return f"Could not retrieve usage: {error}"
