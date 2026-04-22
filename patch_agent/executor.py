import os
import re
import subprocess
import logging
import time
from .utils import logger, read_file

class Executor:
    def __init__(self, working_directory):
        self.working_directory = working_directory
        self.server_process = None

    def execute_actions(self, actions):
        """Executes the list of validated actions sequentially."""
        logger.info("Patch Agent: Starting execution of approved actions.")
        
        for action in actions:
            action_type = action["type"]
            logger.info(f"Executing: {action_type}")
            time.sleep(1)  # Short delay between actions for better UI
            
            try:
                if action_type == "stop_server":
                    self._stop_server()
                elif action_type == "code_edit":
                    self._apply_edit(action)
                elif action_type == "npm_install":
                    self._run_install("npm", action["packages"])
                # delete_path support removed
                elif action_type == "restart_server":
                    self._restart_server(action["command"])
            except Exception as e:
                logger.error(f"Execution failed on action {action_type}: {e}")
                raise

        logger.info("All actions executed successfully.")

    def _stop_server(self):
        """Stops the server by finding the process listening on port 3000."""
        logger.info("Attempting to stop server on port 3000...")
        
        # 1. Kill known child process if any
        if self.server_process:
            logger.info(f"Stopping tracked child process (PID: {self.server_process.pid})...")
            try:
                self.server_process.terminate()
                self.server_process.wait(timeout=2)
            except Exception as e:
                logger.warning(f"Failed to terminate tracked process: {e}")
            self.server_process = None

        # 2. Find any process on port 3000 (Windows specific)
        try:
            # netstat -ano | findstr :3000
            # output:   TCP    0.0.0.0:3000           0.0.0.0:0              LISTENING       1234
            cmd = "netstat -ano"
            result = subprocess.run(cmd, capture_output=True, text=True, shell=True)
            
            pids_to_kill = set()
            for line in result.stdout.splitlines():
                if ":3000" in line and "LISTENING" in line:
                    parts = line.split()
                    pid = parts[-1]
                    pids_to_kill.add(pid)
            
            if not pids_to_kill:
                logger.info("No process found listening on port 3000.")
                return

            for pid in pids_to_kill:
                if pid == "0": continue
                logger.info(f"Killing process {pid} found on port 3000...")
                subprocess.run(f"taskkill /F /PID {pid}", shell=True, capture_output=True)
                
        except Exception as e:
            logger.error(f"Error trying to kill process on port 3000: {e}")

    def _apply_edit(self, action):
        file_path = os.path.join(self.working_directory, action["file"])
        
        # Defense-in-depth: Path traversal check (redundant with validator, but critical)
        full_path_abs = os.path.abspath(file_path)
        working_dir_normalized = os.path.abspath(self.working_directory)
        if not full_path_abs.startswith(working_dir_normalized + os.sep) and full_path_abs != working_dir_normalized:
            raise ValueError(f"Security violation: Attempted path traversal blocked: {action['file']}")
        
        # Additional restriction: Only allow modifications within the 'app' folder
        app_folder = os.path.join(working_dir_normalized, "app")
        if not full_path_abs.startswith(app_folder + os.sep) and full_path_abs != app_folder:
            raise ValueError(f"Security violation: File modifications restricted to 'app' folder only: {action['file']}")
        
        edit_details = action["edit"]
        
        content = read_file(file_path)
        original = edit_details["original_snippet"]
        new_text = edit_details["new_snippet"]
        
        if original not in content:
            # Re-verify just in case
            raise ValueError(f"Concurrency Error: Original snippet not found in {file_path}")
            
        new_content = content.replace(original, new_text, 1) # Replace just the first occurrence or what? 
        # Ideally we'd use line numbers to be precise, but simple replace finding unique snippet constitutes "surgical" enough here.
        # Strict validation checked existence.
        
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(new_content)
        logger.info(f"Applied edit to {file_path}")

    def _run_install(self, tool, packages):
        if not packages:
            return
        # Construct command: npm install pkg1 pkg2 ...
        cmd = [tool, "install"] + packages
        
        # User requested fix: always use legacy peer deps for npm
        if tool == "npm":
            cmd.append("--legacy-peer-deps")
            
        logger.info(f"Running installation: {' '.join(cmd)}")
        # Shell=True on Windows for npm/pip usually needed or finding absolute path
        subprocess.run(cmd, check=True, cwd=self.working_directory, shell=True)



    def _restart_server(self, command):
        # User requested strict "npm run dev" regardless of LLM proposal
        fixed_command = "npm run dev"
        logger.info(f"Restarting server. Ignoring LLM command '{command}', forcing: {fixed_command}")
        
        # First, stop any running server (same logic as stop_server action)
        logger.info("Stopping existing server before restart...")
        self._stop_server()
        time.sleep(1)  # Brief pause to ensure port is freed
        
        # Spawn in a new console window so it doesn't block the agent UI or clutter stdout
        creation_flags = 0
        if os.name == 'nt':
            creation_flags = subprocess.CREATE_NEW_CONSOLE
            
        self.server_process = subprocess.Popen(
            fixed_command, 
            cwd=self.working_directory, 
            shell=True,
            creationflags=creation_flags
        )
        logger.info(f"Server started with PID: {self.server_process.pid}")
