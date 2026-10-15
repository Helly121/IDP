import os

agent_path = r"D:\EDI_IDP\frontend\src\pages\AgentPage.jsx"
with open(agent_path, "r", encoding="utf-8") as f:
    content = f.read()

send_svg = '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><line x1="22" y1="2" x2="11" y2="13"></line><polygon points="22 2 15 22 11 13 2 9 22 2"></polygon></svg>'

spin_svg = '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" style={{animation: "pulse-dot 1.2s infinite"}}><circle cx="12" cy="12" r="10"></circle><path d="M12 2a10 10 0 0 1 10 10"></path></svg>'

target = "{isStreaming ? '?' : '?'}"
replacement = "{isStreaming ? (" + spin_svg + ") : (" + send_svg + ")}"

if target in content:
    content = content.replace(target, replacement)
    with open(agent_path, "w", encoding="utf-8") as f:
        f.write(content)
    print("Replaced icons.")
else:
    print("Target not found.")

