import os
import subprocess
import requests
import google.generativeai as genai

# 1. Initialize Gemini API
genai.configure(api_key=os.environ["GEMINI_API_KEY"])
model = genai.GenerativeModel("gemini-2.5-flash")

def generate_scenes():
    prompt = (
        "Generate a creative architectural restoration theme for a backyard or home. "
        "Return 3 sequential visual descriptions separated by '---': "
        "Scene 1: Overgrown, dilapidated, abandoned state. "
        "Scene 2: Mid-renovation, construction, framing, or cleaning. "
        "Scene 3: Ultra-luxurious modern finished result at golden hour. "
        "Keep each description under 25 words, focusing purely on visual details."
    )
    response = model.generate_content(prompt)
    scenes = [s.strip() for s in response.text.split("---") if s.strip()]
    return scenes[:3]

def download_clip_frame(prompt_text, filename):
    # Using Pollinations.ai free image endpoint as high-res base frame generator
    encoded_prompt = requests.utils.quote(prompt_text + ", 9:16 vertical, photorealistic, architectural photography, 4k")
    url = f"https://image.pollinations.ai/prompt/{encoded_prompt}?width=1080&height=1920&nologo=true"
    
    res = requests.get(url)
    if res.status_code == 200:
        with open(filename, "wb") as f:
            f.write(res.content)
            
def create_video_clips(scenes):
    clip_files = []
    for i, scene in enumerate(scenes):
        img_name = f"frame_{i+1}.jpg"
        vid_name = f"clip_{i+1}.mp4"
        print(f"Generating frame {i+1}...")
        download_clip_frame(scene, img_name)
        
        # Convert static image into a 10-second smooth zoom video using FFmpeg
        cmd = [
            "ffmpeg", "-y",
            "-loop", "1", "-i", img_name,
            "-vf", "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,zoompan=z='min(zoom+0.0015,1.25)':d=300:x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s=1080x1920",
            "-c:v", "libx264", "-t", "10", "-pix_fmt", "yuv420p",
            "-r", "30",
            vid_name
        ]
        subprocess.run(cmd, check=True)
        clip_files.append(vid_name)
    return clip_files

def stitch_videos(clip_files):
    with open("clips.txt", "w") as f:
        for clip in clip_files:
            f.write(f"file '{clip}'\n")
            
    output_file = "final_30s_restoration.mp4"
    cmd = [
        "ffmpeg", "-y",
        "-f", "concat", "-safe", "0", "-i", "clips.txt",
        "-i", "background_music.mp3",
        "-c:v", "libx264", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-shortest",
        "-t", "30",
        output_file
    ]
    subprocess.run(cmd, check=True)
    return output_file

def upload_to_facebook_reel(video_path):
    page_id = os.environ["FB_PAGE_ID"]
    access_token = os.environ["FB_PAGE_ACCESS_TOKEN"]
    base_url = f"https://graph.facebook.com/v21.0/{page_id}/video_reels"
    description = "Unbelievable Backyard Transformation! 🏡✨ #HomeRestoration #BackyardMakeover #BeforeAndAfter #Reels"

    # Step 1: Initialize the Reel upload session
    init_res = requests.post(
        base_url,
        params={
            "upload_phase": "start",
            "access_token": access_token
        }
    ).json()

    if "video_id" not in init_res:
        raise RuntimeError(f"Facebook Reel init failed: {init_res}")

    video_id = init_res["video_id"]
    upload_url = init_res["upload_url"]

    # Step 2: Upload binary video file
    file_size = os.path.getsize(video_path)
    with open(video_path, "rb") as video_file:
        upload_res = requests.post(
            upload_url,
            headers={
                "Authorization": f"OAuth {access_token}",
                "offset": "0",
                "file_size": str(file_size)
            },
            data=video_file
        ).json()

    if not upload_res.get("success"):
        raise RuntimeError(f"Facebook Reel binary upload failed: {upload_res}")

    # Step 3: Publish the Reel to your Facebook Page
    publish_res = requests.post(
        base_url,
        params={
            "upload_phase": "finish",
            "video_id": video_id,
            "video_state": "PUBLISHED",
            "description": description,
            "access_token": access_token
        }
    ).json()

    if not publish_res.get("success"):
        raise RuntimeError(f"Facebook Reel publish failed: {publish_res}")

    print(f"Published Facebook Reel successfully! Video ID: {video_id}")

if __name__ == "__main__":
    print("Step 1: Generating AI Restoration Scenes...")
    scenes = generate_scenes()
    
    print("Step 2: Creating 3x 10s Motion Clips...")
    clips = create_video_clips(scenes)
    
    print("Step 3: Combining into 30s Final Video with Music...")
    final_video = stitch_videos(clips)
    
    print("Step 4: Publishing to Facebook Page as a Reel...")
    upload_to_facebook_reel(final_video)
