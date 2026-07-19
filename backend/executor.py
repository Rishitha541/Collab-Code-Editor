import subprocess
import tempfile
import os
import uuid


class CodeExecutor:
    """
    Safely executes user-submitted Python code inside an isolated Docker container.

    Safety measures:
    - Code runs as non-root user inside container (set in Dockerfile)
    - Timeout enforced so infinite loops can't hang the server
    - Memory limit enforced so a script can't exhaust host RAM
    - Network disabled inside the container so code can't make external calls
    - Container is auto-removed after execution (--rm), nothing persists
    """

    def __init__(self, image_name: str = "code-sandbox", timeout_seconds: int = 5, memory_limit: str = "128m"):
        self.image_name = image_name
        self.timeout_seconds = timeout_seconds
        self.memory_limit = memory_limit

    def run_python_code(self, code: str) -> dict:
        # Write the submitted code to a temporary file on the HOST machine,
        # which we then mount into the container (read-only) so the
        # container has no way to modify anything outside itself.
        run_id = str(uuid.uuid4())[:8]
        temp_dir = tempfile.mkdtemp(prefix=f"sandbox_{run_id}_")
        script_path = os.path.join(temp_dir, "user_code.py")

        with open(script_path, "w") as f:
            f.write(code)

        docker_cmd = [
            "docker", "run",
            "--rm",
            "--network", "none",
            "--memory", self.memory_limit,
            "--cpus", "0.5",
            "--read-only",                                    # entire container filesystem is read-only
            "--tmpfs", "/tmp:size=16m",                        # small writable scratch space only, wiped on exit
            "-v", f"{script_path}:/sandbox/user_code.py:ro",
            self.image_name,
            "python3", "/sandbox/user_code.py"
        ]

        try:
            result = subprocess.run(
                docker_cmd,
                capture_output=True,
                text=True,
                timeout=self.timeout_seconds
            )
            return {
                "success": result.returncode == 0,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "exit_code": result.returncode
            }
        except subprocess.TimeoutExpired:
            return {
                "success": False,
                "stdout": "",
                "stderr": f"Execution timed out after {self.timeout_seconds} seconds (possible infinite loop).",
                "exit_code": -1
            }
        finally:
            # Clean up the temp file/folder from the host machine
            try:
                os.remove(script_path)
                os.rmdir(temp_dir)
            except OSError:
                pass


executor = CodeExecutor()