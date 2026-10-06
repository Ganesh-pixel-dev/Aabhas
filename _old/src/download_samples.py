import os
import yt_dlp

def download_videos(search_query, class_name, num_videos=5):
    # Save into our downloads folder
    save_dir = os.path.abspath(os.path.join("downloads", class_name))
    os.makedirs(save_dir, exist_ok=True)
    
    ydl_opts = {
        'format': 'best[ext=mp4]/best',
        'outtmpl': os.path.join(save_dir, f'{class_name}_%(autonumber)s.%(ext)s'),
        'max_downloads': num_videos,
        'noplaylist': True,
        'quiet': False,
        'ignoreerrors': True,
        # Try to only download short videos to save time and space (< 3 mins)
        'match_filter': yt_dlp.utils.match_filter_func("duration < 180")
    }
    
    print(f"Downloading {num_videos} videos for '{class_name}'...")
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        try:
            # We search for slightly more videos than we need in case some are filtered out
            ydl.download([f"ytsearch{num_videos * 4}:{search_query}"])
        except Exception as e:
            print(f"Error downloading {class_name}: {e}")

if __name__ == "__main__":
    print("Starting automated download of sample datasets...")
    download_videos("person walking down street cctv", "Normal", 5)
    download_videos("person fainting collapsing cctv", "Collapse", 5)
    print("\nDownload complete! The videos are in the 'downloads' folder.")
    print("You can now process them by running:")
    print("  python src/process_videos.py downloads/Normal Normal")
    print("  python src/process_videos.py downloads/Collapse Collapse")
