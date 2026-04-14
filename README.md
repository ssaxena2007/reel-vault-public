# 🎬 Reel Vault
**Turn your Instagram scrolls into an organized Obsidian brain.**

Reel Vault is an "engineer-first" automation tool that monitors your Instagram DMs, downloads the reels or posts you've shared with yourself, and uses **Gemini 2.5 Flash** to watch and analyze them. It then generates structured notes directly in your Obsidian vault.

## 🚀 Features
* **Automated Sync**: Scans your Instagram DMs for content.
* **AI Analysis**: Extracts summaries, key insights, and actionable items from videos and images.
* **Obsidian Ready**: Generates `.md` files with full YAML frontmatter and specific tags.
* **The "Star" System**: Send a reel to yourself twice to mark it as a high-priority "starred" note.

## 🛠️ Setup

### 1. Prerequisites
* **Python 3.10+**
* **Gemini API Key**: Get a free key from [Google AI Studio](https://aistudio.google.com/).
* **Instagram Account**: It is highly recommended to use a secondary "finsta" or bot account.

### 2. Installation
```bash
git clone [https://github.com/yourusername/reel-vault.git](https://github.com/yourusername/reel-vault.git)
cd reel-vault
pip install -r requirements.txt 
```

### 3. Configuration

1.  Copy .env.example to a new file named .env.
    
2.  Fill in your Instagram credentials and Gemini API key.
    
3.  Set OBSIDIAN\_VAULT\_PATH to the folder where you want your notes to appear.
    

### 4. Authenticate

Instagram requires a one-time login to verify your "device." Run:

`   python login.py   `
_Note: You may need to check your Instagram app and click "This was me" if a login notification appears._

### 5. Start Vaulting

`   python main.py   `


🧠 What Gemini Extracts
-----------------------

For every reel, the AI generates a JSON-structured note including:

*   **Category**: (Tech, Business, Life Advice, etc.)
    
*   **Summary**: A concise 2-3 sentence overview.
    
*   **Key Learnings**: 3 to 7 high-value insights.
    
*   **Action Items**: Concrete steps to take based on the content.
    
*   **Notable Quotes**: Memorable lines from the audio or on-screen text.
