import ast
import os

errors = []
for root, _, files in os.walk("app"):
    for f in files:
        if f.endswith(".py"):
            path = os.path.join(root, f)
            try:
                with open(path, encoding="utf-8") as fh:
                    ast.parse(fh.read())
            except SyntaxError as e:
                errors.append(f"{path}: line {e.lineno}: {e.msg}")

if errors:
    print(f"发现 {len(errors)} 个语法错误:")
    for e in errors:
        print(f"  - {e}")
else:
    print("所有Python文件语法检查通过！")
