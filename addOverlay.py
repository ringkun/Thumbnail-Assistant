import re
import os
import shutil
import requests
from PIL import Image, ImageStat,ImageChops
from io import BytesIO


def crop_black_bars(img, tolerance=10):
    if img.mode != "RGB":
        img = img.convert("RGB")
    bg = Image.new("RGB", img.size, (0, 0, 0))
    diff = ImageChops.difference(img, bg)
    bbox = diff.getbbox()
    if bbox:
        left, upper, right, lower = bbox
        expand = 5  # optional margin to avoid tight crop
        left = max(left - expand, 0)
        upper = max(upper - expand, 0)
        right = min(right + expand, img.width)
        lower = min(lower + expand, img.height)
        return img.crop((left, upper, right, lower))
    return img  # no cropping if no black bars detected



def extract_video_id(url):
    match = re.search(r"(?:v=|youtu\.be/)([a-zA-Z0-9_-]{11})", url)
    return match.group(1) if match else None

def fetch_thumbnail_image(video_id):
    resolutions = [
        "maxresdefault", "sddefault", "hqdefault", "mqdefault", "default"
    ]
    headers = {'User-Agent': 'Mozilla/5.0'}
    for res in resolutions:
        url = f"https://i.ytimg.com/vi/{video_id}/{res}.jpg"
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            print(f"[✓] Using thumbnail: {url}")
            return Image.open(BytesIO(response.content)).convert("RGBA")
    return None

def fetch_video_title(video_url):
    headers = {'User-Agent': 'Mozilla/5.0'}
    try:
        response = requests.get(video_url, headers=headers)
        response.raise_for_status()
        # Extract <title>...</title>
        title_match = re.search(r"<title>(.*?)</title>", response.text, re.IGNORECASE | re.DOTALL)
        if title_match:
            title = title_match.group(1)
            # Titles often end with " - YouTube"
            title = title.replace(" - YouTube", "").strip()
            return title
    except Exception as e:
        print(f"[!] Failed to fetch title for {video_url}: {e}")
    return None

def crop_height_to_16_9(image):
    width, height = image.size
    target_height = int(width * 9 / 16)

    if height <= target_height:
        print("[!] Image is already 16:9 or wider.")
        return image

    top = (height - target_height) // 2
    bottom = top + target_height
    cropped = image.crop((0, top, width, bottom))
    print(f"[✓] Cropped height to 16:9: ({width}x{target_height})")
    return cropped
def get_dominant_color(image):
    # Resize to reduce noise and speed up analysis
    small = image.resize((50, 50))
    stat = ImageStat.Stat(small)
    return tuple(map(int, stat.mean))  # Average RGB

def standardize_thumbnail(img):
    original = img.copy()
    
    # Step 1: Crop to 16:9 by trimming height
    width, height = img.size
    target_height = int(width * 9 / 16)

    if height > target_height:
        top = (height - target_height) // 2
        img = img.crop((0, top, width, top + target_height))

    # Step 2: Resize to 1280x720
    img = img.resize((1280, 720), Image.Resampling.LANCZOS)

    # Step 3: Create background with dominant color
    dominant_color = get_dominant_color(original)
    print(dominant_color)
    background = Image.new("RGB", (1280, 720), dominant_color)

    # Step 4: Paste resized image on center (if needed, for transparency layer use RGBA)
    background.paste(img, (0, 0))

    return background

def process_thumbnail(video_url, output_dir, resize_ratio=0.9, overlay_color=(0, 0, 0, 100), overlay_image_path=None, append=""):
    video_id = extract_video_id(video_url)
    if not video_id:
        print(f"[!] Could not extract video ID from: {video_url}")
        return

    thumbnail = fetch_thumbnail_image(video_id)
    if thumbnail is None:
        print(f"[!] Could not find a valid thumbnail for: {video_url}")
        return
    # # Crop black bars first
    thumbnail = standardize_thumbnail(thumbnail)
    cropped = crop_black_bars(thumbnail)

    # Target canvas size (standard YouTube thumbnail size)
    canvas_size = (1280, 720)

    # Resize cropped image to fit within the canvas with padding
    target_size = (int(cropped.size[0] * resize_ratio), int(cropped.size[1] * resize_ratio))
    shrunken = cropped.resize(target_size, Image.Resampling.LANCZOS)

    # Create transparent canvas and paste shrunken image centered
    canvas = Image.new("RGBA", canvas_size, (0, 0, 0, 0))
    offset = ((canvas_size[0] - target_size[0]) // 2, (canvas_size[1] - target_size[1]) // 2)
    canvas.paste(shrunken, offset)
    # Apply overlay image if provided, else color overlay
    if overlay_image_path:
        try:
            overlay_img = Image.open(overlay_image_path).convert("RGBA").resize(canvas_size, Image.Resampling.LANCZOS)
            final_img = Image.alpha_composite(canvas, overlay_img)
        except Exception as e:
            print(f"[!] Failed to load overlay image: {e}")
            overlay = Image.new("RGBA", canvas_size, overlay_color)
            final_img = Image.alpha_composite(canvas, overlay)
    else:
        overlay = Image.new("RGBA", canvas_size, overlay_color)
        final_img = Image.alpha_composite(canvas, overlay)

    os.makedirs(output_dir, exist_ok=True)

    title = fetch_video_title(video_url)
    if not title:
        title = video_id
    VidTitle = re.sub(r'[\\/*?:"<>|]', "", title).strip()

    output_path = os.path.join(output_dir, f"{VidTitle} {append}".strip() + ".png")
    final_img.save(output_path)
    print(f"[✓] Saved: {output_path}")

def load_urls_from_file(file_path):
    with open(file_path, "r", encoding="utf-8") as f:
        return [line.strip() for line in f if line.strip()]

# 🧼 Clear folder before saving thumbnails
def clear_output_folder(folder_path):
    if os.path.exists(folder_path):
        shutil.rmtree(folder_path)
    os.makedirs(folder_path)

def batch_process_thumbnails(file_path, output_dir="thumbnails"):
    clear_output_folder(output_dir)
    urls = load_urls_from_file(file_path)
    scale = .955
    for url in urls:
        title = fetch_video_title(url)
        process_thumbnail(url, output_dir,resize_ratio=scale,overlay_image_path="RSVP Outline White.png",append = "White")
        process_thumbnail(url, output_dir,resize_ratio=scale,overlay_image_path="RSVP Outline Black.png",append = "Black")


# Run it
batch_process_thumbnails("urls.txt")
