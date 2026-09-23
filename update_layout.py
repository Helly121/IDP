import os

filepath = r"D:\EDI_IDP\frontend\src\components\Layout\Layout.jsx"
with open(filepath, "r", encoding="utf-8") as f:
    content = f.read()

target = "              Create Service\n            </Link>"

replacement = target + """
            <Link
              to="/agent"
              className={`layout-nav-link ${location.pathname === '/agent' ? 'active' : ''}`}
            >
              ? DevSecOps Mentor
            </Link>"""

if target in content:
    content = content.replace(target, replacement)
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)
    print("Updated Layout.jsx")
else:
    print("Target not found in Layout.jsx")
