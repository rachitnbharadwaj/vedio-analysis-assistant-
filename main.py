import os
import sys
import argparse
from dotenv import load_dotenv
from rich.console import Console
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.markdown import Markdown
from rich.prompt import Prompt
from rich.panel import Panel

from core import (
    extract_video_id, 
    get_raw_transcript, 
    chunk_transcript, 
    TopicExtractor, 
    format_time
)

# Load environment variables
load_dotenv()

console = Console()

def merge_topics(chunks, topics):
    """
    Merges consecutive chunks with the same topic.
    Returns list of dicts: {'topic': str, 'start': float}
    """
    results = []
    
    if len(chunks) != len(topics):
        console.print(f"[yellow]Warning: Mismatch between chunks ({len(chunks)}) and topics ({len(topics)}). truncation may occur.[/yellow]")
        limit = min(len(chunks), len(topics))
        chunks = chunks[:limit]
        topics = topics[:limit]

    last_topic = None
    
    for chunk, topic in zip(chunks, topics):
        topic = topic.strip()
        if topic.upper() == "IGNORE":
            continue
            
        if topic == last_topic:
            continue
            
        results.append({
            'topic': topic,
            'start': chunk['start']
        })
        last_topic = topic
        
    return results

def main():
    console.print(Panel("[bold cyan]YouTube Learning Assistant[/bold cyan]", expand=False))
    
    parser = argparse.ArgumentParser(description="YouTube Topic Extractor")
    parser.add_argument("url", nargs="?", help="YouTube Video URL")
    parser.add_argument("--chunk-size", type=int, default=3, help="Chunk size in minutes (default: 3)")
    args = parser.parse_args()

    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        console.print("[red]Error: GEMINI_API_KEY not found in environment variables.[/red]")
        console.print("Please create a .env file with GEMINI_API_KEY=your_key_here")
        return

    # 1. Get URL
    url = args.url
    if not url:
        url = Prompt.ask("[bold green]Enter YouTube URL[/bold green]")
        
    if not url:
        console.print("[red]No URL provided. Exiting.[/red]")
        return

    video_id = ""
    transcript_raw = []

    # 2. Fetch
    try:
        with console.status("[bold green]Fetching transcript...[/bold green]"):
            video_id = extract_video_id(url)
            transcript_raw = get_raw_transcript(video_id)
        console.print(f"[green]SUCCESS:[/green] Transcript fetched ({len(transcript_raw)} lines)")
    except Exception as e:
        console.print(f"[red]Error fetching transcript: {e}[/red]")
        return

    # 3. Process
    with console.status("[bold green]Processing text...[/bold green]"):
        chunks = chunk_transcript(transcript_raw, chunk_duration_minutes=args.chunk_size)
    console.print(f"[green]SUCCESS:[/green] Text processed into {len(chunks)} chunks")

    if not chunks:
        console.print("[red]No transcription content found.[/red]")
        return

    extractor = TopicExtractor(api_key)

    # 4. Extract Topics
    topics = []
    
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        transient=True
    ) as progress:
        task = progress.add_task("[cyan]Analyzing topics with Gemini...", total=len(chunks))
        
        batch_size = 5
        for i in range(0, len(chunks), batch_size):
            batch = chunks[i : i + batch_size]
            batch_result = extractor.generate_topics_batch(batch, batch_size=batch_size)
            topics.extend(batch_result)
            progress.advance(task, len(batch))

    # 5. Review Topics
    final_results = merge_topics(chunks, topics)

    console.print("\n[bold]Video Overview[/bold]")
    table = Table(show_header=True, header_style="bold magenta", border_style="cyan")
    table.add_column("Timestamp", style="dim", width=12)
    table.add_column("Topic")

    for item in final_results:
        timestamp_str = format_time(item['start'])
        link = f"https://youtu.be/{video_id}?t={int(item['start'])}"
        topic_text = f"[link={link}]{item['topic']}[/link]"
        table.add_row(timestamp_str, topic_text)

    console.print(table)
    console.print("\n[dim]Tip: Ctrl+Click topics to open video at timestamp[/dim]\n")

    # 6. Interactive Q&A
    console.print(Panel("[bold green]Chat Mode Enabled[/bold green]\nAsk questions about the video. Type 'exit' to quit.", expand=False))
    
    while True:
        question = Prompt.ask("\n[bold cyan]Ask a question[/bold cyan]")
        
        if question.lower() in ('exit', 'quit', 'q'):
            console.print("[yellow]Goodbye![/yellow]")
            break
            
        if not question.strip():
            continue
            
        with console.status("[cyan]Thinking...[/cyan]"):
            answer = extractor.answer_question(chunks, question)
        
        console.print("\n[bold green]Answer:[/bold green]")
        console.print(Markdown(answer))

if __name__ == "__main__":
    main()
