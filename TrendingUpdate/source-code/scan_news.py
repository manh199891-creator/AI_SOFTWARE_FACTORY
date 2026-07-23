import os
import sys
import json
import time
import requests
import arxiv
from datetime import datetime

# Configure search queries for Semantic Scholar (These journals are indexed here)
SS_QUERIES = [
    '"AI agent" "BIM"',
    '"Revit API" "AI"',
    '"Generative design" "BIM"',
    '"structural" "BIM" "interoperability" "AI"',
    '"multi-agent" "construction" BIM'
]

# Configure broader search queries for arXiv to get more results
ARXIV_QUERIES = [
    'all:BIM AND (all:"large language model" OR all:LLM OR all:"multi-agent" OR all:"generative design" OR all:"artificial intelligence")',
    'all:BIM AND all:structural AND (all:interoperability OR all:coordination)',
    'all:"generative design" AND all:construction'
]

# Year filter
START_YEAR = 2023

# Ollama configuration
OLLAMA_URL = "http://localhost:11434/api/generate"
OLLAMA_MODEL = "llama3" 

def get_papers_semantic_scholar(query):
    print(f"Searching Semantic Scholar for: {query}...")
    url = "https://api.semanticscholar.org/graph/v1/paper/search"
    params = {
        "query": query,
        "limit": 10,
        "fields": "title,year,citationCount,tldr,abstract,url,externalIds,authors"
    }
    
    # Introduce delay to avoid 429 rate limit
    time.sleep(3)
    
    try:
        response = requests.get(url, params=params, timeout=15)
        if response.status_code == 200:
            return response.json().get("data", [])
        elif response.status_code == 429:
            print("Received 429 (Too Many Requests) from Semantic Scholar. Rate limited.")
            return []
        else:
            print(f"Error searching for '{query}': {response.status_code}")
            return []
    except Exception as e:
        print(f"Connection error searching for '{query}': {e}")
        return []

def get_papers_arxiv(query):
    print(f"Searching arXiv for: {query}...")
    papers = []
    try:
        search = arxiv.Search(
            query=query,
            max_results=10,
            sort_by=arxiv.SortCriterion.Relevance
        )
        for result in arxiv.Client().results(search):
            authors = [{"name": author.name} for author in result.authors]
            paper = {
                "paperId": result.entry_id.split("/")[-1],
                "title": result.title,
                "year": result.published.year,
                "url": result.entry_id,
                "citationCount": 0,
                "abstract": result.summary,
                "tldr": {"text": result.summary[:200] + "..."},
                "authors": authors
            }
            papers.append(paper)
    except Exception as e:
        print(f"Error searching arXiv: {e}")
    return papers

def summarize_with_ollama(title, abstract, tldr):
    prompt = f"""
Bạn là một trợ lý nghiên cứu khoa học chuyên ngành xây dựng (BIM & AI).
Hãy tóm tắt và dịch bài báo sau sang tiếng Việt cho kỹ sư phát triển phần mềm BIM.

Tiêu đề: {title}
Tóm tắt gốc: {abstract if abstract else tldr if tldr else 'Không có abstract'}

Yêu cầu tóm tắt ngắn gọn:
1. **Tiêu đề tiếng Việt**: (Dịch tiêu đề chính xác)
2. **Ý tưởng cốt lõi (Core Idea)**: (Giải thích ngắn gọn 2-3 câu bằng tiếng Việt về phương pháp AI và ứng dụng BIM của bài báo)
3. **Giá trị thực tiễn**: (Lợi ích cho kỹ sư lập trình Revit API/Navisworks C#)

Chỉ trả về nội dung tóm tắt bằng tiếng Việt, định dạng rõ ràng bằng Markdown. Không chào hỏi hay giải thích thêm.
"""
    data = {
        "model": OLLAMA_MODEL,
        "prompt": prompt,
        "stream": False
    }
    try:
        response = requests.post(OLLAMA_URL, json=data, timeout=30)
        if response.status_code == 200:
            return response.json().get("response", "").strip()
    except requests.exceptions.ConnectionError:
        print("Ollama is not running locally. Skipping AI summarization.")
    except Exception as e:
        print(f"Error calling Ollama: {e}")
    return None

def markdown_to_html_paragraphs(text):
    """Simple parser to convert AI markdown output to HTML paragraphs for the newsletter template."""
    if not text:
        return ""
    lines = text.split("\n")
    html_lines = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        if line.startswith("###") or line.startswith("### "):
            html_lines.append(f"<h4>{line.replace('###', '').strip()}</h4>")
        elif line.startswith("##") or line.startswith("## "):
            html_lines.append(f"<h3>{line.replace('##', '').strip()}</h3>")
        elif line.startswith("- ") or line.startswith("* "):
            html_lines.append(f"<li>{line[2:]}</li>")
        elif line.startswith("1. ") or line.startswith("2. ") or line.startswith("3. "):
            html_lines.append(f"<p><strong>{line[:3]}</strong> {line[3:]}</p>")
        else:
            # Simple bold parsing
            if "**" in line:
                parts = line.split("**")
                for i in range(1, len(parts), 2):
                    parts[i] = f"<strong>{parts[i]}</strong>"
                line = "".join(parts)
            html_lines.append(f"<p>{line}</p>")
            
    # Wrap list items
    final_html = []
    in_list = False
    for item in html_lines:
        if item.startswith("<li>"):
            if not in_list:
                final_html.append("<ul>")
                in_list = True
            final_html.append(item)
        else:
            if in_list:
                final_html.append("</ul>")
                in_list = False
            final_html.append(item)
    if in_list:
        final_html.append("</ul>")
        
    return "\n".join(final_html)

def main():
    all_papers = {}
    
    # Try Semantic Scholar first
    for q in SS_QUERIES:
        papers = get_papers_semantic_scholar(q)
        for p in papers:
            paper_id = p.get("paperId")
            year = p.get("year")
            year_val = year if year is not None else 0
            if paper_id and year_val >= START_YEAR:
                all_papers[paper_id] = p
                
    # Also fetch from arXiv
    for q in ARXIV_QUERIES:
        papers = get_papers_arxiv(q)
        for p in papers:
            paper_id = p.get("paperId")
            year = p.get("year")
            year_val = year if year is not None else 0
            if paper_id and paper_id not in all_papers and year_val >= START_YEAR:
                all_papers[paper_id] = p

    if not all_papers:
        print("No papers found on both Semantic Scholar and arXiv.")
        return

    print(f"Found {len(all_papers)} unique papers from {START_YEAR} onwards.")

    os.makedirs("newsletters", exist_ok=True)
    today_str = datetime.today().strftime('%Y-%m-%d')
    output_md_path = os.path.join("newsletters", f"BIM_AI_Update_{today_str}.md")
    output_html_path = os.path.join("newsletters", f"BIM_AI_Update_{today_str}.html")

    # Generate Markdown Content
    markdown_content = f"# Bản Tin BIM & AI Academic Update - {today_str}\n*Tự động quét từ Semantic Scholar/arXiv và tóm tắt bởi Ollama ({OLLAMA_MODEL})*\n\n---\n\n"

    # Generate HTML Content (Premium Styled Newsletter)
    html_content = f"""<!DOCTYPE html>
<html lang="vi">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Bản Tin BIM & AI Academic Update - {today_str}</title>
    <style>
        :root {{
            --bg-color: #0f172a;
            --card-bg: #1e293b;
            --text-main: #f8fafc;
            --text-muted: #94a3b8;
            --accent: #38bdf8;
            --accent-hover: #7dd3fc;
            --border-color: #334155;
        }}
        body {{
            font-family: 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
            background-color: var(--bg-color);
            color: var(--text-main);
            margin: 0;
            padding: 40px 20px;
            line-height: 1.6;
        }}
        .container {{
            max-width: 900px;
            margin: 0 auto;
        }}
        header {{
            text-align: center;
            margin-bottom: 40px;
            padding-bottom: 20px;
            border-bottom: 1px solid var(--border-color);
        }}
        h1 {{
            color: var(--accent);
            margin-bottom: 10px;
        }}
        .meta {{
            color: var(--text-muted);
            font-size: 0.9em;
        }}
        .paper-card {{
            background-color: var(--card-bg);
            border: 1px solid var(--border-color);
            border-radius: 12px;
            padding: 24px;
            margin-bottom: 30px;
            box-shadow: 0 4px 6px -1px rgb(0 0 0 / 0.1), 0 2px 4px -2px rgb(0 0 0 / 0.1);
            transition: transform 0.2s ease, border-color 0.2s ease;
        }}
        .paper-card:hover {{
            transform: translateY(-2px);
            border-color: var(--accent);
        }}
        .paper-title {{
            margin-top: 0;
            color: var(--text-main);
            font-size: 1.3em;
            line-height: 1.4;
        }}
        .paper-meta {{
            font-size: 0.85em;
            color: var(--text-muted);
            margin-bottom: 15px;
        }}
        .read-link {{
            display: inline-block;
            background-color: var(--accent);
            color: var(--bg-color);
            padding: 6px 16px;
            border-radius: 6px;
            text-decoration: none;
            font-weight: 600;
            font-size: 0.85em;
            transition: background-color 0.2s;
        }}
        .read-link:hover {{
            background-color: var(--accent-hover);
        }}
        .summary-box {{
            margin-top: 20px;
            padding: 15px;
            background-color: rgba(56, 189, 248, 0.05);
            border-left: 4px solid var(--accent);
            border-radius: 0 8px 8px 0;
        }}
        .summary-box h4 {{
            margin-top: 0;
            color: var(--accent);
            margin-bottom: 10px;
        }}
        blockquote {{
            margin: 20px 0 0 0;
            padding-left: 15px;
            border-left: 4px solid var(--text-muted);
            color: var(--text-muted);
            font-style: italic;
        }}
        p, li {{
            font-size: 0.95em;
            color: #cbd5e1;
        }}
        ul {{
            padding-left: 20px;
        }}
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>Bản Tin BIM & AI Academic Update</h1>
            <div class="meta">Ngày phát hành: {today_str} | Trợ lý Ollama: {OLLAMA_MODEL}</div>
        </header>
        <main>
"""

    count = 1
    for paper_id, p in all_papers.items():
        title = p.get("title").replace("\n", " ")
        year = p.get("year")
        url = p.get("url")
        citations = p.get("citationCount", 0)
        abstract = p.get("abstract")
        tldr_dict = p.get("tldr")
        tldr = tldr_dict.get("text") if tldr_dict else None
        
        authors_list = p.get("authors", [])
        authors_str = ", ".join([a.get("name", "") for a in authors_list[:3]])
        if len(authors_list) > 3:
            authors_str += " et al."

        print(f"\n[{count}] Processing: {title}")

        ai_summary = summarize_with_ollama(title, abstract, tldr)

        # Append to Markdown
        markdown_content += f"## {count}. {title}\n"
        markdown_content += f"- **Tác giả:** {authors_str} | **Năm:** {year} | **Trích dẫn:** {citations}\n"
        markdown_content += f"- **Nguồn đọc:** [Link]({url})\n\n"

        if ai_summary:
            markdown_content += "### 💡 Tóm tắt thông minh (Ollama):\n"
            markdown_content += f"{ai_summary}\n\n"
        else:
            markdown_content += "### 📝 Tóm tắt gốc (TLDR):\n"
            markdown_content += f"> {tldr if tldr else abstract if abstract else 'No abstract available.'}\n\n"
        markdown_content += "---\n\n"

        # Append to HTML
        html_content += f"""
            <section class="paper-card">
                <h2 class="paper-title">{count}. {title}</h2>
                <div class="paper-meta">
                    <strong>Tác giả:</strong> {authors_str} | 
                    <strong>Năm:</strong> {year} | 
                    <strong>Trích dẫn:</strong> {citations}
                </div>
                <a href="{url}" target="_blank" class="read-link">Đọc bài báo gốc ↗</a>
        """

        if ai_summary:
            formatted_ai_summary = markdown_to_html_paragraphs(ai_summary)
            html_content += f"""
                <div class="summary-box">
                    <h4>💡 Tóm tắt thông minh (Ollama)</h4>
                    {formatted_ai_summary}
                </div>
            """
        else:
            html_content += f"""
                <blockquote>
                    <strong>Tóm tắt gốc (TLDR):</strong><br>
                    {tldr if tldr else abstract if abstract else 'No abstract available.'}
                </blockquote>
            """
            
        html_content += "\n            </section>"
        count += 1

    html_content += """
        </main>
    </div>
</body>
</html>
"""

    # Write both files
    with open(output_md_path, "w", encoding="utf-8") as f:
        f.write(markdown_content)
        
    with open(output_html_path, "w", encoding="utf-8") as f:
        f.write(html_content)

    print(f"\nNewsletter successfully generated at:")
    print(f" - Markdown: {output_md_path}")
    print(f" - HTML: {output_html_path}")

if __name__ == "__main__":
    main()
