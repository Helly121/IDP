import os

layout_path = r"D:\EDI_IDP\frontend\src\components\Layout\Layout.jsx"
with open(layout_path, "r", encoding="utf-8") as f:
    content = f.read()
content = content.replace("? DevSecOps Mentor", "DevSecOps Mentor")
with open(layout_path, "w", encoding="utf-8") as f:
    f.write(content)

agent_path = r"D:\EDI_IDP\frontend\src\pages\AgentPage.jsx"
with open(agent_path, "r", encoding="utf-8") as f:
    content = f.read()

svg = """<svg width="32" height="32" viewBox="0 0 32 32" fill="none" xmlns="http://www.w3.org/2000/svg">
            <circle cx="16" cy="16" r="14" stroke="#ffffff" strokeWidth="2.5" />
            <path d="M16 4C9.37258 4 4 9.37258 4 16C4 22.6274 9.37258 28 16 28C22.6274 28 28 22.6274 28 16C28 12.5 26.5 9 24 6.5C21.5 4 18.5 4 16 4Z" fill="#ffffff" />
            <circle cx="18.5" cy="14.5" r="9.5" fill="#000000" />
          </svg>"""

big_svg = """<svg width="64" height="64" viewBox="0 0 32 32" fill="none" xmlns="http://www.w3.org/2000/svg">
            <circle cx="16" cy="16" r="14" stroke="#ffffff" strokeWidth="2.5" />
            <path d="M16 4C9.37258 4 4 9.37258 4 16C4 22.6274 9.37258 28 16 28C22.6274 28 28 22.6274 28 16C28 12.5 26.5 9 24 6.5C21.5 4 18.5 4 16 4Z" fill="#ffffff" />
            <circle cx="18.5" cy="14.5" r="9.5" fill="#000000" />
          </svg>"""

content = content.replace('<div className="agent-page-avatar">??</div>', f'<div className="agent-page-avatar">{svg}</div>')
content = content.replace('<div className="agent-empty-icon">??</div>', f'<div className="agent-empty-icon">{big_svg}</div>')

with open(agent_path, "w", encoding="utf-8") as f:
    f.write(content)
