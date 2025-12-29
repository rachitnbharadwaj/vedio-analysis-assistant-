import os
import re
import json
import logging
import requests
import traceback
from typing import List, Dict, Optional
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
import yt_dlp
from youtube_transcript_api import YouTubeTranscriptApi
from google import genai

# Configure logging
logging.basicConfig(level=logging.ERROR)
logger = logging.getLogger(__name__)

# --- UTILS ---

class FileOperations:
    """Handles basic CRUD operations for files."""
    
    @staticmethod
    def save_text(filepath: str, content: str) -> None:
        """Create/Update: Saves text to a file."""
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)

    @staticmethod
    def read_text(filepath: str) -> Optional[str]:
        """Read: Reads text from a file."""
        if not os.path.exists(filepath):
            return None
        with open(filepath, 'r', encoding='utf-8') as f:
            return f.read()

    @staticmethod
    def save_json(filepath: str, data: Dict) -> None:
        """Create/Update: Saves data as JSON."""
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)

    @staticmethod
    def read_json(filepath: str) -> Optional[Dict]:
        """Read: Reads JSON data."""
        if not os.path.exists(filepath):
            return None
        with open(filepath, 'r', encoding='utf-8') as f:
            return json.load(f)

    @staticmethod
    def delete_file(filepath: str) -> bool:
        """Delete: Removes a file."""
        if os.path.exists(filepath):
            os.remove(filepath)
            return True
        return False

def format_time(seconds: float) -> str:
    """Converts seconds to HH:MM:SS format."""
    seconds = int(seconds)
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    secs = seconds % 60
    if hours > 0:
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"

# --- FETCHER ---

def extract_video_id(url: str) -> str:
    """Extracts the video ID from a YouTube URL."""
    patterns = [
        r'(?:v=|\/)([0-9A-Za-z_-]{11}).*',
    ]
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    if len(url) == 11:
        return url
    raise ValueError(f"Could not extract video ID from URL: {url}")

def get_raw_transcript(video_id: str) -> List[Dict]:
    """
    Fetches the transcript for a given video ID.
    Returns: List of dicts [{'text': str, 'start': float, 'duration': float}]
    """
    # 1. Try youtube-transcript-api
    try:
        transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)
        # Prefer english
        try:
            transcript = transcript_list.find_transcript(['en'])
        except:
            try:
                transcript = transcript_list.find_generated_transcript(['en'])
            except:
                transcript = transcript_list[0].translate('en')
        
        return transcript.fetch()

    except Exception as e:
        logger.warning(f"youtube-transcript-api failed ({e}). Attempting yt-dlp fallback...")
        return _get_transcript_ytdlp(video_id)

def _get_transcript_ytdlp(video_id: str) -> List[Dict]:
    """Fallback using yt-dlp to fetch subtitles."""
    url = f"https://www.youtube.com/watch?v={video_id}"
    ydl_opts = {
        'skip_download': True,
        'writesubtitles': True,
        'writeautomaticsub': True,
        'subtitleslangs': ['en'],
        'subtitlesformat': 'json3', 
        'quiet': True,
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        try:
            info = ydl.extract_info(url, download=False)
        except Exception as e:
            raise Exception(f"yt-dlp extraction failed: {e}")

        requested_subs = info.get('requested_subtitles')
        if not requested_subs or 'en' not in requested_subs:
            raise Exception("No English subtitles found via yt-dlp.")
            
        sub_url = requested_subs['en']['url']
        
        # Fetch the JSON3 content
        try:
            response = requests.get(sub_url)
            response.raise_for_status()
            data = response.json()
        except Exception as e:
             raise Exception(f"Failed to download subtitle content: {e}")

        # Parse JSON3 to standard format
        return _parse_json3(data)

def _parse_json3(data) -> List[Dict]:
    """Parses YouTube JSON3 format to simple list."""
    output = []
    events = data.get('events', [])
    for event in events:
        if 'segs' not in event:
            continue
            
        # Combine segments
        text_parts = [seg.get('utf8', '') for seg in event['segs']]
        text = ''.join(text_parts).strip()
        
        # Skip empty lines (often just newlines in json3)
        if not text or text == '\n':
            continue
            
        start = event.get('tStartMs', 0) / 1000.0
        duration = event.get('dDurationMs', 0) / 1000.0
        
        output.append({
            'text': text,
            'start': start,
            'duration': duration
        })
        
    return output

# --- PREPROCESSOR ---

def clean_text(text: str) -> str:
    """Removes noise like [Music], [Applause] and excessive whitespace."""
    text = re.sub(r'\[.*?\]', '', text)
    text = re.sub(r'\(.*?\)', '', text)
    text = ' '.join(text.split())
    return text

def chunk_transcript(transcript: List[Dict], chunk_duration_minutes: int = 3) -> List[Dict]:
    """
    Groups transcript items into time-based chunks.
    """
    chunk_duration_seconds = chunk_duration_minutes * 60
    chunks = []
    
    if not transcript:
        return chunks

    current_chunk_start = transcript[0]['start']
    current_text_buffer = []
    
    for item in transcript:
        start = item['start']
        text = clean_text(item['text'])
        
        if not text:
            continue
            
        if start - current_chunk_start >= chunk_duration_seconds:
            if current_text_buffer:
                chunks.append({
                    'start': current_chunk_start,
                    'end': start,
                    'text': ' '.join(current_text_buffer)
                })
            
            current_chunk_start = start
            current_text_buffer = [text]
        else:
            current_text_buffer.append(text)
            
    if current_text_buffer:
        last_item = transcript[-1]
        chunks.append({
            'start': current_chunk_start,
            'end': last_item['start'] + last_item['duration'],
            'text': ' '.join(current_text_buffer)
        })
        
    return chunks

# --- AI HANDLER ---

class TopicExtractor:
    def __init__(self, api_key: str):
        if not api_key:
            raise ValueError("API Key is required")
        self.client = genai.Client(api_key=api_key)

    @retry(
        retry=retry_if_exception_type(Exception), 
        stop=stop_after_attempt(5), 
        wait=wait_exponential(multiplier=2, min=5, max=120)
    )
    def _generate_with_retry(self, model, contents):
        try:
            return self.client.models.generate_content(
                model=model,
                contents=contents
            )
        except Exception as e:
            logger.debug(f"AI Retrying due to error: {e}")
            raise e

    def generate_topics_batch(self, chunks: List[Dict], batch_size: int = 5) -> List[str]:
        """
        Generates topics for chunks in batches to save tokens.
        """
        all_topics = []
        
        for i in range(0, len(chunks), batch_size):
            batch = chunks[i : i + batch_size]
            prompt = self._build_batch_prompt(batch)
            
            try:
                response = self._generate_with_retry(
                    model='gemini-2.0-flash',
                    contents=prompt
                )
                batch_topics = self._parse_response(response.text, len(batch))
                all_topics.extend(batch_topics)
            except Exception as e:
                logger.error(f"CRITICAL AI ERROR in batch {i}: {e}")
                # traceback.print_exc()
                all_topics.extend(["Unlabeled Section (AI Error)"] * len(batch))
                
        return all_topics

    def answer_question(self, chunks: List[Dict], question: str) -> str:
        """
        Answers a question based on the transcript chunks.
        """
        context = ""
        for chunk in chunks:
            timestamp = int(chunk['start'])
            minutes = timestamp // 60
            seconds = timestamp % 60
            time_str = f"[{minutes:02d}:{seconds:02d}]"
            context += f"{time_str} {chunk['text']}\n"

        prompt = (
            "You are a helpful video assistant. Answer the user's question strictly based on the provided transcript below.\n"
            "Cite the timestamp (e.g., [05:30]) where the answer is found.\n"
            "If the answer is not in the transcript, say 'I cannot find the answer in this video.'\n\n"
            f"Question: {question}\n\n"
            f"Transcript:\n{context[:100000]}"
        )

        try:
            response = self._generate_with_retry(
                model='gemini-2.0-flash',
                contents=prompt
            )
            return response.text
        except Exception as e:
            return f"Error generating answer: {e}"

    def _build_batch_prompt(self, batch: List[Dict]) -> str:
        prompt = (
            "You are a video topic extractor. Analyze the following transcript segments. "
            "For EACH segment, provide a SINGLE, CONCISE topic label (max 5 words). "
            "If a segment is purely filler, intro, or transitions without clear substance, label it 'IGNORE'.\n\n"
            "Return a numbered list matching the input segments exactly.\n"
            "Example Output:\n"
            "1. Introduction to AI\n"
            "2. Neural Network Basics\n"
            "3. IGNORE\n\n"
            "Segments:\n"
        )
        
        for idx, chunk in enumerate(batch):
            text_preview = chunk['text'][:2000] 
            prompt += f"Segment {idx+1}:\n{text_preview}\n\n"
            
        return prompt

    def _parse_response(self, response_text: str, expected_count: int) -> List[str]:
        lines = response_text.strip().split('\n')
        cleaned_lines = []
        for line in lines:
            line = line.strip()
            if not line: continue
            
            parts = line.split('.', 1)
            if len(parts) > 1 and parts[0].isdigit():
                cleaned_lines.append(parts[1].strip())
            else:
                cleaned_lines.append(line)
        
        if len(cleaned_lines) < expected_count:
            cleaned_lines.extend(["Unlabeled"] * (expected_count - len(cleaned_lines)))
        return cleaned_lines[:expected_count]
