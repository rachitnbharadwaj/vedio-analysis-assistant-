import os
import time
import yt_dlp
from google import genai
from google.genai import types
from dotenv import load_dotenv
from rich.console import Console

# Load environment variables
load_dotenv()
console = Console()

class AudioChat:
    def __init__(self):
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise ValueError("GEMINI_API_KEY not found in .env file")
        self.client = genai.Client(api_key=api_key)

    def download_audio(self, youtube_url: str, output_filename: str = "temp_audio"):
        """
        Downloads audio to a local file using yt-dlp.
        Returns the filename of the downloaded audio.
        """
        console.print("[cyan]Downloading audio (this may take a moment)...[/cyan]")
        
        # Remove existing file if present
        if os.path.exists(f"{output_filename}.mp3"):
            os.remove(f"{output_filename}.mp3")

        # Try with FFmpeg conversion first
        ydl_opts = {
            'format': 'bestaudio/best',
            'outtmpl': output_filename,
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }],
            'quiet': True,
            'noplaylist': True,
        }

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([youtube_url])
                return f"{output_filename}.mp3"
        except Exception as e:
            if "ffmpeg" in str(e).lower() or "ffprobe" in str(e).lower():
                console.print("[yellow]FFmpeg not found. Falling back to raw format...[/yellow]")
                return self._download_raw(youtube_url, output_filename)
            else:
                console.print(f"[red]Error downloading video: {e}[/red]")
                raise e

    def _download_raw(self, youtube_url, output_filename):
        # Fallback if ffmpeg is missing
        ydl_opts = {
            'format': 'bestaudio/best',
            'outtmpl': output_filename + ".%(ext)s",
            'quiet': True,
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(youtube_url)
            ext = info['ext']
            return f"{output_filename}.{ext}"

    def ask(self, audio_path: str, question: str):
        """
        Sends audio file + question to Gemini 2.0 Flash (Multimodal).
        """
        try:
            with open(audio_path, "rb") as f:
                audio_data = f.read()

            # Detect mime type from extension
            ext = os.path.splitext(audio_path)[1].lower().replace('.', '')
            mime_type = "audio/mp3"
            if ext == "m4a": mime_type = "audio/mp4" # m4a is mp4 container
            if ext == "webm": mime_type = "audio/webm"
            if ext == "wav": mime_type = "audio/wav"

            console.print(f"[cyan]Sending {len(audio_data)/1024/1024:.1f}MB ({mime_type}) to Gemini...[/cyan]")
            response = self.client.models.generate_content(
                model='gemini-2.0-flash',
                contents=[
                    types.Content(
                        parts=[
                            types.Part.from_bytes(
                                data=audio_data,
                                mime_type=mime_type 
                            ),
                            types.Part.from_text(text=f"Question: {question}")
                        ]
                    )
                ]
            )
            return response.text
        except Exception as e:
            return f"Error from Gemini: {e}"

def main():
    chat = AudioChat()
    
    console.print("[bold green]YouTube Audio Chat (Powered by Gemini 2.0)[/bold green]")
    youtube_url = console.input("Enter YouTube Link: ").strip()
    
    if not youtube_url:
        return

    audio_file = None
    try:
        # 1. Download Audio Locally
        audio_file = chat.download_audio(youtube_url)
        console.print(f"[bold green]Audio downloaded to {audio_file}! Start chatting.[/bold green]\n")

        # 2. Chat Loop
        while True:
            question = console.input("[bold cyan]Ask a question (or 'exit'): [/bold cyan]")
            if question.lower() in ('exit', 'quit'):
                break
                
            with console.status("[yellow]Analyzing audio...[/yellow]"):
                answer = chat.ask(audio_file, question)
            
            console.print(f"\n[bold]Answer:[/bold]\n{answer}\n")

    except Exception as e:
        console.print(f"[red]Fatal Error: {e}[/red]")
    
    finally:
        # Cleanup option
        if audio_file and os.path.exists(audio_file):
            # Optional: os.remove(audio_file)
            print(f"(Cached audio file kept at {audio_file})")

if __name__ == "__main__":
    main()
