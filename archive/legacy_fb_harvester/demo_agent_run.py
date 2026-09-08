import sys
import logging

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from fb_harvester.agent_runner import AutonomousAgent

def main():
    agent = AutonomousAgent()
    
    print("\n" + "=" * 60)
    print("🤖 THỰC HIỆN LƯỢT 2: ĐỀ NGHỊ ĐỒNG BỘ CRAWL4AI LÊN NOTEBOOKLM")
    print("=" * 60)
    
    prompt2 = "Được, hãy đóng gói và đẩy repo unclecode/crawl4ai lên NotebookLM giúp tôi ngay bây giờ."
    print(f"\n👤 NGƯỜI DÙNG: {prompt2}\n")
    
    answer2 = agent.chat(prompt2)
    print("=" * 60)
    print("🤖 CÂU TRẢ LỜI CỦA AGENT:")
    print("=" * 60)
    print(answer2)

if __name__ == "__main__":
    main()
