from flask import Flask, render_template_string, request, jsonify
import os
import requests
import random
import threading
from gtts import gTTS
from moviepy.editor import VideoFileClip, AudioFileClip
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

app = Flask(__name__)

# --- AGENT SKILLS ARCHITECTURE (Inspired by YouTube Agent Skill) ---

# 1. /yt-script skill: Generates hooks and script
def skill_yt_script(topic, custom_prompt=""):
    print("Executing /yt-script skill...")
    openai_key = os.environ.get("OPENAI_API_KEY")
    if openai_key:
        try:
            headers = {"Authorization": f"Bearer {openai_key}", "Content-Type": "application/json"}
            prompt_text = custom_prompt if custom_prompt else f"Write a viral YouTube Shorts script with a strong first 3-second hook for: {topic}. Keep it under 45 words in Hinglish."
            payload = {"model": "gpt-3.5-turbo", "messages": [{"role": "user", "content": prompt_text}], "max_tokens": 100}
            res = requests.post("https://api.openai.com/v1/chat/completions", json=payload, headers=headers, timeout=30)
            if res.status_code == 200:
                return res.json()["choices"][0]["message"]["content"]
        except Exception as e:
            print(f"Script error: {e}")
    return f"Kya aapko pata hai {topic} ka yeh bada raaz? Dekhiye yeh video!"

# 2. /yt-package skill: Generates optimized title and package info
def skill_yt_package(topic):
    print("Executing /yt-package skill...")
    return f"{topic} | Mind-Bending Facts #Shorts"

# 3. /yt-seo skill: Generates SEO tags and description
def skill_yt_seo(topic):
    print("Executing /yt-seo skill...")
    description = f"Dive deep into {topic}. Learn amazing facts and secrets in this quick short!\n\n#shorts #trending #viral #ai #facts"
    tags = ["shorts", "trending", "viral", topic.lower().replace(" ", ""), "facts"]
    return description, tags

# 4. /yt-edit skill: Prepares asset and editing rules
def skill_yt_edit(genre):
    print("Executing /yt-edit skill (Fetching stock video)...")
    pixabay_key = os.environ.get("PIXABAY_API_KEY")
    if not pixabay_key:
        return "https://www.w3schools.com/html/mov_bbb.mp4"
    try:
        url = f"https://pixabay.com/api/videos/?key={pixabay_key}&q=cinematic&per_page=10"
        res = requests.get(url, timeout=15)
        if res.status_code == 200:
            hits = res.json().get("hits", [])
            if hits:
                selected = random.choice(hits)
                v_files = selected.get("videos", {})
                return v_files.get("medium", {}).get("url")
    except Exception as e:
        print(f"Edit/Pixabay error: {e}")
    return "https://www.w3schools.com/html/mov_bbb.mp4"

# 5. /yt-plan & Upload Pipeline Execution
def run_agent_pipeline(topic, custom_prompt=""):
    # Step-by-step agent workflow execution
    script_text = skill_yt_script(topic, custom_prompt)
    title = skill_yt_package(topic)
    description, tags = skill_yt_seo(topic)
    video_url = skill_yt_edit(topic)
    
    # Video compilation (9:16 format + Voiceover)
    if video_url:
        temp_video = "temp_agent_v.mp4"
        temp_audio = "temp_agent_a.mp3"
        final_output = "final_agent_out.mp4"
        try:
            v_res = requests.get(video_url, stream=True, timeout=30)
            with open(temp_video, "wb") as f:
                for chunk in v_res.iter_content(chunk_size=8192):
                    f.write(chunk)
            
            tts = gTTS(text=script_text, lang='hi', slow=False)
            tts.save(temp_audio)
            
            video_clip = VideoFileClip(temp_video)
            audio_clip = AudioFileClip(temp_audio)
            
            w, h = video_clip.size
            if w > h:
                new_w = int(h * (9 / 16))
                x1 = (w - new_w) // 2
                video_clip = video_clip.crop(x1=x1, y1=0, x2=x1 + new_w, y2=h)
                
            final_clip = video_clip.set_audio(audio_clip).subclip(0, min(video_clip.duration, audio_clip.duration))
            final_clip.write_videofile(final_output, fps=20, codec="libx264", audio_codec="aac", preset="ultrafast", logger=None)
            
            video_clip.close()
            audio_clip.close()
            final_clip.close()
            
            # YouTube API Upload Step
            upload_to_youtube_channel(final_output, title, description, tags)
        except Exception as e:
            print(f"Pipeline processing error: {e}")

def upload_to_youtube_channel(video_filename, title, description, tags):
    client_id = os.environ.get("YOUTUBE_CLIENT_ID")
    client_secret = os.environ.get("YOUTUBE_CLIENT_SECRET")
    refresh_token = os.environ.get("YOUTUBE_REFRESH_TOKEN")
    
    if not client_id or not client_secret or not refresh_token:
        print("YouTube tokens missing for auto-upload.")
        return

    try:
        credentials = Credentials(
            token=None, refresh_token=refresh_token,
            client_id=client_id, client_secret=client_secret,
            token_uri="https://oauth2.googleapis.com/token"
        )
        youtube = build("youtube", "v3", credentials=credentials)
        
        body = {
            "snippet": {
                "title": title[:100],
                "description": description[:5000],
                "tags": tags,
                "categoryId": "24"
            },
            "status": {"privacyStatus": "public", "selfDeclaredMadeForKids": False}
        }
        
        media = MediaFileUpload(video_filename, chunksize=-1, resumable=True)
        response = youtube.videos().insert(part="snippet,status", body=body, media_body=media).execute()
        print(f"Agent successfully uploaded Short! ID: {response.get('id')}")
        
        for f in ["temp_agent_v.mp4", "temp_agent_a.mp3", "final_agent_out.mp4"]:
            if os.path.exists(f):
                os.remove(f)
    except Exception as e:
        print(f"YouTube upload error: {e}")

# --- WEB DASHBOARD INTERFACE ---
DASHBOARD_UI = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>YouTube Agent Skill Dashboard</title>
    <style>
        body { font-family: sans-serif; background: #0f172a; color: #f8fafc; padding: 20px; display: flex; justify-content: center; align-items: center; height: 100vh; margin: 0; }
        .card { background: #1e293b; padding: 30px; border-radius: 12px; width: 100%; max-width: 500px; box-shadow: 0 10px 25px rgba(0,0,0,0.5); }
        h2 { color: #38bdf8; text-align: center; margin-top: 0; }
        .group { margin-bottom: 15px; }
        label { display: block; margin-bottom: 5px; font-weight: bold; color: #cbd5e1; }
        input, textarea { width: 100%; padding: 10px; background: #0f172a; border: 1px solid #475569; color: #fff; border-radius: 6px; box-sizing: border-box; }
        button { background: #0284c7; color: white; border: none; padding: 12px; width: 100%; border-radius: 6px; font-size: 16px; font-weight: bold; cursor: pointer; margin-top: 10px; }
        button:hover { background: #0369a1; }
        #status { margin-top: 15px; text-align: center; color: #34d399; font-weight: 500; }
    </style>
</head>
<body>
    <div class="card">
        <h2>🤖 YouTube Agent Skill Hub</h2>
        <div class="group">
            <label>Topic / Movie Name:</label>
            <input type="text" id="topicInput" placeholder="e.g., Interstellar Black Hole Paradox">
        </div>
        <div class="group">
            <label>Custom Instructions (/yt-script hook):</label>
            <textarea id="promptInput" rows="3" placeholder="Enter special script guidance..."></textarea>
        </div>
        <button onclick="runAgent()">Trigger Agent Pipeline</button>
        <div id="status"></div>
    </div>
    <script>
        function runAgent() {
            let topic = document.getElementById('topicInput').value;
            let prompt = document.getElementById('promptInput').value;
            let status = document.getElementById('status');
            status.innerText = "Agent skills active: Processing workflow...";
            
            fetch('/run-agent', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({topic: topic, prompt: prompt})
            })
            .then(res => res.json())
            .then(data => { status.innerText = data.message; })
            .catch(err => { status.innerText = "Error executing agent skills!"; });
        }
    </script>
</body>
</html>
"""

@app.route('/')
def home():
    return render_template_string(DASHBOARD_UI)

@app.route('/run-agent', methods=['POST'])
def trigger_agent():
    data = request.get_json() or {}
    topic = data.get('topic', 'Viral Movie Secret')
    prompt = data.get('prompt', '')
    
    # Run the modular agent workflow in background thread
    threading.Thread(target=run_agent_pipeline, args=(topic, prompt)).start()
    return jsonify({"status": "success", "message": "✅ Agent skills triggered! Script, SEO, Edit & Upload running in background."})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)