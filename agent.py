import ast
import os
import sys
from openai import OpenAI

# Only files inside this directory may be patched
ALLOWED_BASE_DIR = os.path.realpath(os.path.dirname(__file__))
MAX_INPUT_LEN = 8192


def _safe_path(file_name: str) -> str:
    """Resolve path and reject anything outside the project root."""
    candidate = os.path.realpath(os.path.join(ALLOWED_BASE_DIR, file_name))
    if not candidate.startswith(ALLOWED_BASE_DIR + os.sep) and candidate != ALLOWED_BASE_DIR:
        print("Error: file_name is outside the allowed project directory.")
        sys.exit(1)
    return candidate


def _validate_python(source: str) -> bool:
    try:
        ast.parse(source)
        return True
    except SyntaxError as e:
        print(f"Syntax validation failed: {e}")
        return False


def fix_code(file_name: str, error_message: str, traceback_text: str):
    file_path = _safe_path(file_name)

    if not os.path.isfile(file_path):
        print(f"File {file_path} does not exist.")
        sys.exit(1)

    # Truncate untrusted inputs to prevent prompt injection / token abuse
    error_message = error_message[:MAX_INPUT_LEN]
    traceback_text = traceback_text[:MAX_INPUT_LEN]

    with open(file_path, "r") as f:
        code = f.read()

    client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

    prompt = (
        "You are an expert autonomous coding agent.\n"
        "A python application crashed with the following error:\n"
        f"Error Message: {error_message}\n"
        f"Traceback: {traceback_text}\n\n"
        f"Here is the source code of the file ({os.path.basename(file_path)}):\n"
        "```python\n"
        f"{code}\n"
        "```\n\n"
        "Write the corrected python code that fixes this error. "
        "Return ONLY the fully corrected python code, and nothing else. "
        "Do not include markdown formatting like ```python, just the raw code."
    )

    print(f"Sending prompt to OpenAI to fix {file_path}...")
    response = client.chat.completions.create(
        model="gpt-4o",
        temperature=0,
        messages=[{"role": "user", "content": prompt}],
    )

    fixed_code = response.choices[0].message.content.strip()

    # Strip markdown fences if the model included them anyway
    if fixed_code.startswith("```python"):
        fixed_code = fixed_code[9:]
    if fixed_code.endswith("```"):
        fixed_code = fixed_code[:-3]
    fixed_code = fixed_code.strip()

    # Reject the patch if it isn't valid Python
    if not _validate_python(fixed_code):
        print("Aborting: AI-generated code failed syntax validation.")
        sys.exit(1)

    with open(file_path, "w") as f:
        f.write(fixed_code)

    print(f"Successfully applied fix to {file_path}")
    # Print the resolved path so the workflow can commit exactly this file
    print(f"FIXED_FILE={os.path.relpath(file_path, ALLOWED_BASE_DIR)}")


if __name__ == "__main__":
    # Read from environment variables — NOT from argv — to prevent shell injection
    file_name = os.environ.get("FIX_FILE_NAME", "").strip()
    error_message = os.environ.get("FIX_ERROR_MESSAGE", "Unknown Error")
    traceback_text = os.environ.get("FIX_TRACEBACK", "No traceback")

    if not file_name:
        print("FIX_FILE_NAME environment variable is required.")
        sys.exit(1)

    fix_code(file_name, error_message, traceback_text)
