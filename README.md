# YouTube Topic Extractor

A cost-efficient, production-ready Python tool that extracts topic-wise timestamps from long YouTube videos using Google's Gemini AI.

## Features

- **Smart Transcript Acquisition**: Automatically fetches transcripts using `youtube-transcript-api` with `yt-dlp` fallback.
- **Intelligent Chunking**: splits video into time-aware segments (default 3 mins) to preserve context.
- **Cost-Optimized AI**: Uses Gemini 2.0 Flash with batch processing to minimize token costs.
- **Q&A Mode**: Ask questions about the video and get answers with specific timestamp citations.
- **Robust**: Includes auto-retry logic for API rate limits and robust fetching.

## Installation

1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

2. Set up API Key:
   - Create a `.env` file in this directory.
   - Add your Gemini API key:
     ```
     GEMINI_API_KEY=your_actual_api_key_here
     ```

## Usage

### 1. Extract Topics
Run the tool with a YouTube URL to get a table of topics and timestamps:

```bash
python main.py "https://www.youtube.com/watch?v=VIDEO_ID"
```

### 2. Ask Questions
Ask a specific question about the video content:

```bash
python main.py "https://www.youtube.com/watch?v=VIDEO_ID" --question "What is the main takeaway?"
```

### Options

- `--chunk-size`: Set the duration of each analysis segment in minutes (default: 3).
  ```bash
  python main.py "URL" --chunk-size 5
  ```

## Design Architecture

1.  **Fetcher**: robustly retrieves transcripts, handling auto-generated or translation fallbacks.
2.  **Preprocessor**: cleans raw text (removing [Music], filler) and groups into `chunk_size` slots.
3.  **AI Handler**:
    - Uses **Batch Processing** (groups 5 chunks per request) to reduce HTTP overhead and repeated system prompts.
    - Uses **Gemini 2.0 Flash** for high speed and low cost.
    - Implements **Backoff Retries** to handle API rate limits gracefully.
4.  **Merger**: Coalesces sequential chunks with the same label into a single topic entry.

## Requirements

- Python 3.8+
- A valid Google Gemini API Key
