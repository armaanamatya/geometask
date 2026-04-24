import os
import sys
from openai import OpenAI

def fix_code(file_path, error_message, traceback):
    if not os.path.exists(file_path):
        print(f"File {file_path} does not exist.")
        sys.exit(1)

    with open(file_path, "r") as f:
        code = f.read()

    client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

    prompt = f"""You are an expert autonomous coding agent.
A python application crashed with the following error:
Error Message: {error_message}
Traceback: {traceback}

Here is the source code of the file ({file_path}):
```python
{code}
```

Write the corrected python code that fixes this error. Return ONLY the fully corrected python code, and nothing else. Do not include markdown formatting like ```python, just the raw code.
"""

    print(f"Sending prompt to OpenAI to fix {file_path}...")
    response = client.chat.completions.create(
        model="gpt-4o",
        temperature=0,
        messages=[
            {"role": "user", "content": prompt}
        ]
    )

    fixed_code = response.choices[0].message.content.strip()
    
    # Strip markdown block if model still includes it
    if fixed_code.startswith("```python"):
        fixed_code = fixed_code[9:]
    if fixed_code.endswith("```"):
        fixed_code = fixed_code[:-3]
    fixed_code = fixed_code.strip()

    with open(file_path, "w") as f:
        f.write(fixed_code)
        
    print(f"Successfully applied fix to {file_path}")

if __name__ == "__main__":
    if len(sys.argv) < 4:
        print("Usage: python agent.py <file_path> <error_message> <traceback>")
        sys.exit(1)
        
    file_path = sys.argv[1]
    error_message = sys.argv[2]
    traceback = sys.argv[3]
    
    fix_code(file_path, error_message, traceback)
