import os
import cv2
import streamlit as st
import ffmpeg
import numpy as np
import yt_dlp as youtube_dl
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

# Function to extract the direct video URL using yt-dlp
def get_video_url(video_url):
    ydl_opts = {
        'format': 'best',
        'quiet': True,
    }
    with youtube_dl.YoutubeDL(ydl_opts) as ydl:
        info_dict = ydl.extract_info(video_url, download=False)
        video_url = info_dict.get('url', None)
    return video_url

# Function to clear the frames directory
def clear_frames_directory(output_path):
    if os.path.exists(output_path):
        for file in os.listdir(output_path):
            file_path = os.path.join(output_path, file)
            try:
                if os.path.isfile(file_path):
                    os.unlink(file_path)
            except Exception as e:
                st.error(f"Failed to delete {file_path}: {e}")

# Function to capture frames from the video stream
def capture_frames_from_stream(video_url, output_path, frame_rate=1):
    clear_frames_directory(output_path)  # Clear old frames before processing new video

    if not os.path.exists(output_path):
        os.makedirs(output_path)
        st.write(f"Created directory {output_path}")

    st.write("Starting video stream...")
    process = (
        ffmpeg
        .input(video_url)
        .output('pipe:', format='rawvideo', pix_fmt='rgb24')
        .run_async(pipe_stdout=True, pipe_stderr=True)
    )

    probe = ffmpeg.probe(video_url)
    video_info = next(s for s in probe['streams'] if s['codec_type'] == 'video')
    width = int(video_info['width'])
    height = int(video_info['height'])
    frame_size = width * height * 3  # Calculate the frame size
    video_frame_rate = eval(video_info['r_frame_rate'])  # Get the frame rate of the video
    st.write(f"Video width: {width}, height: {height}, frame rate: {video_frame_rate}")

    count = 0
    frame_number = 0

    while True:
        in_bytes = process.stdout.read(frame_size)  # Read the frame data
        if len(in_bytes) != frame_size:
            break  # Exit if the frame data is not complete
        frame = np.frombuffer(in_bytes, np.uint8).reshape([height, width, 3])  # Convert the frame data to an image
        if count % int(video_frame_rate) == 0:
            frame_path = os.path.join(output_path, f"frame{frame_number:04d}.jpg")
            cv2.imwrite(frame_path, frame)  # Save the frame as an image
            st.write(f"Saved frame {frame_number} to {frame_path}")
            frame_number += 1
        count += 1

    st.write("Finished capturing frames.")
    process.stdout.close()
    process.wait()

# Function to upload a file to Google Drive
def upload_to_drive(service, folder_id, file_path):
    try:
        file_metadata = {'name': os.path.basename(file_path), 'parents': [folder_id]}
        media = MediaFileUpload(file_path, mimetype='image/jpeg')
        file = service.files().create(body=file_metadata, media_body=media, fields='id').execute()
        st.write(f"Uploaded {file_path} to Google Drive with file ID: {file.get('id')}")
    except Exception as e:
        st.error(f"Failed to upload {file_path} to Google Drive: {e}")

def main():
    st.title("Video Frame Capture and Upload to Google Drive")

    # Input fields for user to provide necessary information
    video_url = st.text_input("Enter the video URL:")
    google_credentials_file = "videotoframeassistant-dfd9146af136.json"
    # st.text_input("Enter the path to your Google service account credentials JSON file:")
    google_drive_folder_id = "1EXIWUgij5eHSYAL4Dh2-SgUZMljJrZL8"
    # st.text_input("Enter your Google Drive folder ID:")
    frames_output_path = 'frames'

    if st.button("Process Video"):
        if video_url and google_credentials_file and google_drive_folder_id:
            try:
                st.write("Extracting video URL...")
                direct_video_url = get_video_url(video_url)
                st.write("Capturing frames from stream...")
                capture_frames_from_stream(direct_video_url, frames_output_path)
                
                st.write("Uploading frames to Google Drive...")
                creds = service_account.Credentials.from_service_account_file(google_credentials_file)
                service = build('drive', 'v3', credentials=creds)
                
                for frame_file in os.listdir(frames_output_path):
                    file_path = os.path.join(frames_output_path, frame_file)
                    upload_to_drive(service, google_drive_folder_id, file_path)
                
                st.success("Frames captured and uploaded successfully!")
            except Exception as e:
                st.error(f"An error occurred: {e}")
        else:
            st.error("Please provide all the required inputs.")

if __name__ == "__main__":
    main()
