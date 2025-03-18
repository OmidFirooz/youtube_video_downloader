import os
import json
from django.shortcuts import render
from django.http import FileResponse, JsonResponse
import yt_dlp
from django.conf import settings
import uuid

download_status = {}

def download_progress_hook(d):
    if d['status'] == 'downloading':
        task_id = d.get('task_id')
        if task_id:
            percentage = d.get('downloaded_bytes', 0) / d.get('total_bytes', 1) * 100
            download_status[task_id] = {'progress': percentage, 'filename': d.get('filename')}

def download_video(request):
    if request.method == 'POST':
        video_url = request.POST.get('video_url')
        download_type = request.POST.get('download_type')
        if not video_url:
            return render(request, 'downloader/index.html', {'error': 'Please enter a valid URL'})

        task_id = str(uuid.uuid4())
        download_status[task_id] = {'progress': 0, 'filename': None}

        try:
            ffmpeg_path = os.path.join(settings.BASE_DIR, 'venv', 'ffmpeg', 'ffmpeg.exe')
            ydl_opts = {
                'outtmpl': os.path.join(settings.MEDIA_ROOT, f'{task_id}_%(title)s.%(ext)s'),
                'ffmpeg_location': ffmpeg_path if os.path.exists(ffmpeg_path) else None,
                'progress_hooks': [lambda d: download_progress_hook({**d, 'task_id': task_id})],
            }

            if download_type == 'hd_video':
                ydl_opts.update({
                    'format': 'bestvideo+bestaudio/best',
                    'merge_output_format': 'mp4',
                })
            elif download_type == 'low_video':
                ydl_opts.update({'format': 'best'})
            elif download_type == 'mp3':
                ydl_opts.update({
                    'format': 'bestaudio/best',
                    'postprocessors': [{
                        'key': 'FFmpegExtractAudio',
                        'preferredcodec': 'mp3',
                        'preferredquality': '192',
                    }],
                })
            else:
                return render(request, 'downloader/index.html', {'error': 'Invalid download type'})

            import threading
            def download_task():
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    ydl.download([video_url])
                download_status[task_id]['progress'] = 100

            threading.Thread(target=download_task, daemon=True).start()
            return render(request, 'downloader/index.html', {'task_id': task_id})

        except Exception as e:
            return render(request, 'downloader/index.html', {'error': f'Error: {str(e)}'})

    return render(request, 'downloader/index.html')

def download_status_view(request, task_id):
    status = download_status.get(task_id, {'progress': 0, 'filename': None})
    return JsonResponse({
        'progress': status['progress'],
        'filename': status['filename'],
        'ready': status['progress'] == 100 and status['filename'] is not None
    })

def serve_file(request, task_id):
    status = download_status.get(task_id)
    if not status or not status['filename'] or not os.path.exists(status['filename']):
        return JsonResponse({'error': 'File not found'}, status=404)

    filename = status['filename']
    file_handle = open(filename, 'rb')
    response = FileResponse(file_handle, as_attachment=True, filename=os.path.basename(filename))

    # Define cleanup as a standalone function, avoiding recursion
    def cleanup():
        try:
            file_handle.close()
            if os.path.exists(filename):
                os.remove(filename)
            download_status.pop(task_id, None)
        except Exception as e:
            print(f"Cleanup error: {e}")

    response.close = cleanup  # Assign the function, not a recursive call
    return response