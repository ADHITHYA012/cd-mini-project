from flask import Flask, render_template, request
import subprocess
import tempfile
import os
import shutil

app = Flask(__name__)


def run_command(command, cwd, timeout=5):
    try:
        result = subprocess.run(
            command,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=timeout
        )

        return {
            "success": result.returncode == 0,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "returncode": result.returncode
        }

    except subprocess.TimeoutExpired:
        return {
            "success": False,
            "stdout": "",
            "stderr": "Program execution timed out.",
            "returncode": -1
        }

    except FileNotFoundError:
        return {
            "success": False,
            "stdout": "",
            "stderr": f"Required compiler/runtime not found: {command[0]}",
            "returncode": -1
        }


def compile_and_run(code, language):

    temp_dir = tempfile.mkdtemp()

    try:

        if language == "c":

            source_file = os.path.join(
                temp_dir,
                "program.c"
            )

            executable = os.path.join(
                temp_dir,
                "program"
            )

            with open(
                source_file,
                "w",
                encoding="utf-8"
            ) as file:
                file.write(code)

            compile_result = run_command(
                [
                    "gcc",
                    source_file,
                    "-o",
                    executable
                ],
                temp_dir
            )

            if not compile_result["success"]:

                return {
                    "status": "Compilation Error",
                    "output": compile_result["stderr"]
                }

            run_result = run_command(
                [executable],
                temp_dir
            )

            if not run_result["success"]:

                return {
                    "status": "Runtime Error",
                    "output": run_result["stderr"]
                }

            return {
                "status": "Compiled Successfully",
                "output": run_result["stdout"]
            }


        elif language == "cpp":

            source_file = os.path.join(
                temp_dir,
                "program.cpp"
            )

            executable = os.path.join(
                temp_dir,
                "program"
            )

            with open(
                source_file,
                "w",
                encoding="utf-8"
            ) as file:
                file.write(code)

            compile_result = run_command(
                [
                    "g++",
                    source_file,
                    "-o",
                    executable
                ],
                temp_dir
            )

            if not compile_result["success"]:

                return {
                    "status": "Compilation Error",
                    "output": compile_result["stderr"]
                }

            run_result = run_command(
                [executable],
                temp_dir
            )

            if not run_result["success"]:

                return {
                    "status": "Runtime Error",
                    "output": run_result["stderr"]
                }

            return {
                "status": "Compiled Successfully",
                "output": run_result["stdout"]
            }


        elif language == "python":

            source_file = os.path.join(
                temp_dir,
                "program.py"
            )

            with open(
                source_file,
                "w",
                encoding="utf-8"
            ) as file:
                file.write(code)

            python_command = shutil.which("python")

            if python_command is None:
                python_command = shutil.which("python3")

            if python_command is None:

                return {
                    "status": "Runtime Error",
                    "output": "Python is not installed."
                }

            run_result = run_command(
                [
                    python_command,
                    source_file
                ],
                temp_dir
            )

            if not run_result["success"]:

                return {
                    "status": "Runtime Error",
                    "output": run_result["stderr"]
                }

            return {
                "status": "Executed Successfully",
                "output": run_result["stdout"]
            }


        elif language == "java":

            source_file = os.path.join(
                temp_dir,
                "Main.java"
            )

            with open(
                source_file,
                "w",
                encoding="utf-8"
            ) as file:
                file.write(code)

            compile_result = run_command(
                [
                    "javac",
                    source_file
                ],
                temp_dir
            )

            if not compile_result["success"]:

                return {
                    "status": "Compilation Error",
                    "output": compile_result["stderr"]
                }

            run_result = run_command(
                [
                    "java",
                    "Main"
                ],
                temp_dir
            )

            if not run_result["success"]:

                return {
                    "status": "Runtime Error",
                    "output": run_result["stderr"]
                }

            return {
                "status": "Compiled Successfully",
                "output": run_result["stdout"]
            }


        else:

            return {
                "status": "Error",
                "output": "Unsupported language."
            }

    finally:

        shutil.rmtree(
            temp_dir,
            ignore_errors=True
        )


@app.route("/")
def home():

    return render_template(
        "index.html"
    )


@app.route(
    "/run",
    methods=["POST"]
)
def run_code():

    code = request.form.get(
        "code",
        ""
    )

    language = request.form.get(
        "language",
        ""
    )

    if not code.strip():

        return render_template(
            "index.html",
            error="Please enter some code."
        )

    result = compile_and_run(
        code,
        language
    )

    return render_template(
        "index.html",
        code=code,
        language=language,
        status=result["status"],
        output=result["output"]
    )


if __name__ == "__main__":

    app.run(
        debug=True
    )
