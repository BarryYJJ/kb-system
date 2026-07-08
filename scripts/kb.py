#!/usr/bin/env python3
"""
本地知识库 CLI 工具
使用 ChromaDB + sentence-transformers 实现本地语义搜索
"""
import argparse
import hashlib
import json
import os
import re
import sys
from argparse import Namespace
from datetime import datetime
from pathlib import Path

# 解决 Mac 上多个 OpenMP 版本冲突问题（必须在 import 其他库之前设置）
os.environ['KMP_DUPLICATE_LIB_OK'] = 'TRUE'

# 注意：chromadb / sentence_transformers 为重依赖，改为在实际使用时惰性导入，
# 这样纯函数（frontmatter、解析、归一化等）可在无这些依赖的环境下被导入/测试。

# 配置
EMBEDDING_MODEL = "paraphrase-multilingual-MiniLM-L12-v2"
BASE_DIR = Path.home() / ".openclaw" / "workspace" / "knowledge_bases"

# 全局模型缓存
_model = None

def get_model():
    global _model
    if _model is None:
        from sentence_transformers import SentenceTransformer
        print("Loading embedding model...", file=sys.stderr)
        _model = SentenceTransformer(EMBEDDING_MODEL)
        print("Model loaded", file=sys.stderr)
    return _model

def get_chroma_client(kb_name: str):
    """获取 ChromaDB 客户端"""
    import chromadb
    db_dir = BASE_DIR / kb_name / "chroma_db"
    db_dir.mkdir(parents=True, exist_ok=True)
    return chromadb.PersistentClient(path=str(db_dir))

def get_collection(client, kb_name: str):
    """获取或创建集合"""
    try:
        return client.get_collection(name=kb_name)
    except:
        return client.create_collection(name=kb_name, metadata={"description": f"{kb_name} knowledge base"})

def split_text(text: str, max_length: int = 6000):
    """将长文本分段"""
    if len(text) <= max_length:
        return [text]
    
    paragraphs = text.split('\n\n')
    chunks = []
    current = ""
    
    for para in paragraphs:
        if len(current) + len(para) + 2 <= max_length:
            current += para + "\n\n"
        else:
            if current:
                chunks.append(current.strip())
            current = para + "\n\n"
    
    if current:
        chunks.append(current.strip())

    return chunks

# ---------------------------------------------------------------------------
# Frontmatter / metadata helpers (stdlib only, no PyYAML dependency)
# ---------------------------------------------------------------------------

def compute_content_hash(content: str):
    """返回 (完整哈希, 短哈希8位)。完整哈希形如 'sha256:<hex>'。"""
    digest = hashlib.sha256(content.encode("utf-8")).hexdigest()
    return f"sha256:{digest}", digest[:8]

def _is_number(s: str) -> bool:
    try:
        float(s)
        return True
    except (ValueError, TypeError):
        return False

# 触发引号的 YAML 特殊字符/指示符
_YAML_SPECIAL = re.compile(r'[:#\[\]{}&*!|>%@`,\'"]')

def _yaml_scalar(value) -> str:
    """把标量安全地渲染为 YAML。仅在需要时加双引号。"""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    s = "" if value is None else str(value)
    if s == "":
        return '""'
    needs_quote = (
        s != s.strip()
        or bool(_YAML_SPECIAL.search(s))
        or s[0] in '-?:,[]{}#&*!|>\'"%@`'
        or s.lower() in ("true", "false", "null", "yes", "no", "on", "off", "~")
        or _is_number(s)
        or "\n" in s
    )
    if needs_quote:
        escaped = s.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")
        return f'"{escaped}"'
    return s

def _render_yaml_list(items) -> str:
    """以 flow 风格渲染列表，如 [算力, 大模型]。空列表为 []。"""
    if not items:
        return "[]"
    return "[" + ", ".join(_yaml_scalar(i) for i in items) + "]"

def render_frontmatter(fields) -> str:
    """fields: [(key, value), ...]。list/tuple 渲染为 flow 列表，其余为标量。"""
    lines = ["---"]
    for key, value in fields:
        if isinstance(value, (list, tuple)):
            lines.append(f"{key}: {_render_yaml_list(value)}")
        else:
            lines.append(f"{key}: {_yaml_scalar(value)}")
    lines.append("---")
    return "\n".join(lines) + "\n"

def parse_list_arg(value):
    """把逗号分隔的 CLI 字符串解析成去空后的列表。None/空 -> []。"""
    if not value:
        return []
    return [item.strip() for item in value.split(",") if item.strip()]

# 需要归一化为 AI初步判断(小八) 的旧标题（半角/全角括号都覆盖）
_AI_VIEW_HEADING_ALIASES = {
    "小八投研判断",
    "小八判断",
    "投研判断(小八)",
    "投研判断（小八）",
}
_AI_VIEW_HEADING_CANONICAL = "AI初步判断(小八)"

def normalize_content_headings(content: str) -> str:
    """把助手判断类标题统一改为 '## AI初步判断(小八)'，保留原标题级别。"""
    out = []
    for line in content.split("\n"):
        m = re.match(r"^(#{1,6})\s*(.+?)\s*$", line)
        if m and m.group(2).strip() in _AI_VIEW_HEADING_ALIASES:
            out.append(f"{m.group(1)} {_AI_VIEW_HEADING_CANONICAL}")
        else:
            out.append(line)
    return "\n".join(out)

# 旧版正文里的元信息行：**来源** / **类型** / **入库时间**
_OLD_META_LINE = re.compile(r"^\s*\*\*(来源|类型|入库时间)\*\*\s*[:：]?")

def remove_leading_title_duplicates(content: str, title: str) -> str:
    """移除正文开头与外层标题重复的 H1，避免 frontmatter 后出现多重标题。"""
    lines = content.split("\n")
    title_norm = title.strip()
    i = 0
    kept_prefix = []
    while i < len(lines) and lines[i].strip() == "":
        kept_prefix.append(lines[i])
        i += 1

    removed = False
    while i < len(lines):
        m = re.match(r"^\s*#(?!#)\s+(.+?)\s*$", lines[i])
        if not m or m.group(1).strip() != title_norm:
            break
        removed = True
        i += 1
        while i < len(lines) and lines[i].strip() == "":
            i += 1

    if not removed:
        return content
    return "\n".join(kept_prefix + lines[i:])


def remove_leading_meta_section(content: str) -> str:
    """移除正文开头的旧 `## 元信息` 小节，保留正文中部同名章节。"""
    lines = content.split("\n")
    i = 0
    kept_prefix = []
    while i < len(lines) and lines[i].strip() == "":
        kept_prefix.append(lines[i])
        i += 1

    # 允许开头保留一个 H1 标题（旧文档 H1 与新 title 不一致时不会被前一步删除），
    # 紧随其后的 `## 元信息` 仍属于文档头部的旧元信息。
    if i < len(lines) and re.match(r"^\s*#(?!#)\s+", lines[i]):
        kept_prefix.append(lines[i])
        i += 1
        while i < len(lines) and lines[i].strip() == "":
            kept_prefix.append(lines[i])
            i += 1

    if i >= len(lines) or not re.match(r"^\s*##\s+元信息\s*$", lines[i]):
        return content

    j = i + 1
    while j < len(lines):
        # 到下一个 H1/H2 章节停止；H3 视为元信息小节内部内容。
        if re.match(r"^\s*#{1,2}\s+", lines[j]):
            break
        j += 1
    # 保守守卫：若移除后没有任何实质正文（如全文只有元信息小节），原样返回。
    if not any(line.strip() for line in lines[j:]):
        return content
    while j < len(lines) and lines[j].strip() == "":
        j += 1
    while kept_prefix and kept_prefix[-1].strip() == "":
        kept_prefix.pop()
    if kept_prefix and j < len(lines):
        kept_prefix.append("")
    return "\n".join(kept_prefix + lines[j:])


def remove_duplicate_metadata_block(content: str) -> str:
    """保守地移除正文开头重复的旧元信息块。

    仅当开头（可选 H1 标题之后）确实出现完整旧元信息块时才移除，
    即至少两个 **来源**/**类型**/**入库时间** 标记，且紧跟旧版 '---' 分隔线。
    绝不删除其它加粗行或来源事实。
    """
    lines = content.split("\n")
    n = len(lines)
    kept_head = []
    i = 0

    # 保留开头空行
    while i < n and lines[i].strip() == "":
        kept_head.append(lines[i])
        i += 1

    # 保留可选的开头 H1 标题行（# ...）及其后空行。
    # 不把 H2/H3 当作标题前言，否则 `## 来源事实与关键数据` 下的 `**来源**`
    # 可能被误判成旧元信息块。
    if i < n and re.match(r"^\s*#(?!#)\s+", lines[i]):
        kept_head.append(lines[i])
        i += 1
        while i < n and lines[i].strip() == "":
            kept_head.append(lines[i])
            i += 1

    # 扫描候选元信息块。为避免误删正文事实，必须同时满足：
    # 1) 至少两个旧元信息键；2) 后面紧跟旧版 `---` 分隔线。
    j = i
    found_meta_keys = set()
    saw_separator = False
    while j < n:
        stripped = lines[j].strip()
        if stripped == "":
            j += 1
            continue
        m = _OLD_META_LINE.match(lines[j])
        if m:
            found_meta_keys.add(m.group(1))
            j += 1
            continue
        if stripped == "---":
            saw_separator = True
            j += 1  # 分隔线归入被移除块并结束
            break
        break  # 遇到真实正文，停止

    if len(found_meta_keys) < 2 or not saw_separator:
        return content  # 没有完整旧元信息块，原样返回，宁可重复不要误删

    remaining = lines[j:]
    while remaining and remaining[0].strip() == "":
        remaining.pop(0)
    while kept_head and kept_head[-1].strip() == "":
        kept_head.pop()
    if kept_head and remaining:
        kept_head.append("")  # 标题与正文之间保留一个空行
    return "\n".join(kept_head + remaining)


_XXPQ_WATERMARK_LINE = re.compile(r"^\s*(?:xxpq\s*)+$", re.IGNORECASE)
_XXPQ_WATERMARK_FRAGMENT = re.compile(r"^\s*(?:xxp|pq|x|q)\s*$", re.IGNORECASE)


def remove_known_watermark_noise(content: str, source_type: str = "") -> str:
    """Remove known source watermarks/noise from extracted text.

    Some PDF/text sources render a repeated ``xxpq`` watermark into the text layer.
    It can appear as full ``xxpq`` runs or as short wrapped fragments like ``xxp`` / ``q``.
    Remove it before hashing, markdown backup, and vectorization so retrieval is not polluted.
    """
    if not content:
        return content

    lines = content.split("\n")
    cleaned = []
    for line in lines:
        if _XXPQ_WATERMARK_LINE.fullmatch(line):
            continue
        # The one-letter fragments are mainly produced by PDF text extraction line wraps;
        # keep the rule source-scoped to avoid deleting legitimate prose in plain notes.
        if source_type in {"pdf", "pdf_ocr", "image_ocr"} and _XXPQ_WATERMARK_FRAGMENT.fullmatch(line):
            continue
        cleaned.append(line)

    text = "\n".join(cleaned)
    text = re.sub(r"(?im)(?<!\w)xxpq(?!\w)", "", text)
    text = re.sub(r"[ \t]{2,}", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def build_markdown_document(
    *,
    title: str,
    body: str,
    doc_id: str,
    kb_name: str,
    source_type: str,
    source: str,
    ingested_at: str,
    updated_at: str,
    directions=None,
    tags=None,
    tickers=None,
    companies=None,
    quality: str = "",
    language: str = "zh",
    privacy: str = "private",
    ai_initial_view_summary: str = "",
    content_hash: str = "",
    attachment_refs=None,
) -> str:
    """Build the canonical KB markdown backup with Reuters-style YAML frontmatter.

    All ingest paths (text / webpage / pdf / image_ocr / video transcript / wrappers)
    must go through this function instead of writing legacy **来源** blocks.
    """
    directions = list(directions or [])
    tags = list(tags or [])
    tickers = list(tickers or [])
    companies = list(companies or [])
    attachment_refs = list(attachment_refs or [])

    cleaned_body = remove_known_watermark_noise(body, source_type=source_type)
    cleaned_body = remove_duplicate_metadata_block(cleaned_body)
    cleaned_body = remove_leading_title_duplicates(cleaned_body, title)
    cleaned_body = remove_leading_meta_section(cleaned_body)
    cleaned_body = normalize_content_headings(cleaned_body).strip()

    frontmatter = render_frontmatter([
        ("doc_id", doc_id),
        ("kb", kb_name),
        ("title", title),
        ("directions", directions),
        ("source_type", source_type),
        ("source", source),
        ("ingested_at", ingested_at),
        ("updated_at", updated_at),
        ("language", language),
        ("quality", quality),
        ("tags", tags),
        ("tickers", tickers),
        ("companies", companies),
        ("ai_initial_view_summary", ai_initial_view_summary),
        ("privacy", privacy),
        ("content_hash", content_hash),
        ("attachment_refs", attachment_refs),
    ])
    return f"{frontmatter}# {title}\n\n{cleaned_body}\n"


def curate(args):
    """存入知识库"""
    kb_name = args.kb
    title = args.title
    source = args.source
    content_type = args.type or "text"
    content = remove_known_watermark_noise(args.content, source_type=content_type)

    # 可选元数据（xhs 等旧调用不传时用默认值，保持兼容）
    directions = parse_list_arg(getattr(args, "directions", None))
    tags = parse_list_arg(getattr(args, "tags", None))
    tickers = parse_list_arg(getattr(args, "tickers", None))
    companies = parse_list_arg(getattr(args, "companies", None))
    quality = getattr(args, "quality", None) or ""
    language = getattr(args, "language", None) or "zh"
    privacy = getattr(args, "privacy", None) or "private"
    ai_initial_view_summary = getattr(args, "ai_initial_view_summary", None) or ""

    # 确保目录存在
    docs_dir = BASE_DIR / kb_name / "documents"
    docs_dir.mkdir(parents=True, exist_ok=True)

    # 单一时间戳，保证 doc_id / frontmatter / Chroma 一致
    now = datetime.now().astimezone().replace(microsecond=0)
    timestamp = now.strftime("%Y%m%d_%H%M%S")
    now_iso = now.isoformat()

    # 内容哈希 + doc_id
    content_hash, short_hash = compute_content_hash(content)
    doc_id = f"kb_{kb_name}_{timestamp}_{short_hash}"

    # 保存 markdown 备份（frontmatter + 标题 + 正文）
    safe_title = "".join(c for c in title if c.isalnum() or c in " -_")[:50]
    md_path = docs_dir / f"{safe_title}_{timestamp}.md"

    markdown = build_markdown_document(
        title=title,
        body=content,
        doc_id=doc_id,
        kb_name=kb_name,
        source_type=content_type,
        source=source,
        ingested_at=now_iso,
        updated_at=now_iso,
        directions=directions,
        tags=tags,
        tickers=tickers,
        companies=companies,
        quality=quality,
        language=language,
        privacy=privacy,
        ai_initial_view_summary=ai_initial_view_summary,
        content_hash=content_hash,
        attachment_refs=[],
    )

    with open(md_path, "w", encoding="utf-8") as f:
        f.write(markdown)

    # 分段处理（向量化基于清洗后的正文内容，避免水印/旧头部污染检索）
    chunks = split_text(content)

    # 获取 embedding 模型
    model = get_model()

    # 获取 ChromaDB
    client = get_chroma_client(kb_name)
    collection = get_collection(client, kb_name)

    # 存入向量数据库
    for i, chunk in enumerate(chunks):
        chunk_id = f"{doc_id}_chunk_{i}"
        embedding = model.encode(chunk, normalize_embeddings=True).tolist()

        collection.add(
            ids=[chunk_id],
            embeddings=[embedding],
            documents=[chunk],
            metadatas=[{
                "doc_id": doc_id,
                "title": title,
                "source": source,
                "type": content_type,
                "timestamp": now_iso,
                "chunk_index": i,
                "total_chunks": len(chunks),
                # 新增元数据字段（仅存标量，列表字段见 frontmatter）
                "kb": kb_name,
                "source_type": content_type,
                "quality": quality,
                "content_hash": content_hash,
                "md_path": str(md_path),
            }]
        )

    result = {
        "status": "success",
        "doc_id": doc_id,
        "chunks": len(chunks),
        "total_docs": collection.count(),
        "md_backup": str(md_path),
        "timestamp": now_iso
    }

    print(json.dumps(result, ensure_ascii=False))

def query(args):
    """语义检索"""
    kb_name = args.kb
    question = args.question
    top_n = args.n or 5
    
    # 获取 embedding 模型
    model = get_model()
    
    # 获取 ChromaDB
    client = get_chroma_client(kb_name)
    collection = get_collection(client, kb_name)
    
    # 生成 query embedding
    query_embedding = model.encode(question, normalize_embeddings=True).tolist()
    
    # 搜索
    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=top_n
    )
    
    # 整理结果
    output = []
    if results["ids"] and results["ids"][0]:
        for i in range(len(results["ids"][0])):
            meta = results["metadatas"][0][i]
            doc_id = meta.get("doc_id", "unknown")
            
            # 计算相似度（余弦相似度）
            relevance = float(results["distances"][0][i])
            # 距离越小越相似，转换为 0-1 分数
            relevance = 1 - relevance
            
            output.append({
                "doc_id": doc_id,
                "title": meta.get("title", "Untitled"),
                "source": meta.get("source", "Unknown"),
                "timestamp": meta.get("timestamp", ""),
                "relevance": round(relevance, 4),
                "content_preview": results["documents"][0][i][:500]
            })
    
    # 按 relevance 排序
    output.sort(key=lambda x: x["relevance"], reverse=True)
    
    # 去重（同一个 doc_id 只显示一次）
    seen = set()
    unique_output = []
    for item in output:
        if item["doc_id"] not in seen:
            seen.add(item["doc_id"])
            unique_output.append(item)
    
    result = {
        "status": "success",
        "question": question,
        "results": unique_output
    }
    
    print(json.dumps(result, ensure_ascii=False))

def recent(args):
    """最近入库记录"""
    kb_name = args.kb
    top_n = args.n or 10
    
    # 获取 ChromaDB
    client = get_chroma_client(kb_name)
    collection = get_collection(client, kb_name)
    
    # 获取所有数据
    all_data = collection.get()
    
    if not all_data["ids"]:
        print(json.dumps({"status": "success", "documents": []}, ensure_ascii=False))
        return
    
    # 按时间排序
    docs = []
    for i in range(len(all_data["ids"])):
        meta = all_data["metadatas"][i]
        docs.append({
            "doc_id": meta.get("doc_id", "unknown"),
            "title": meta.get("title", "Untitled"),
            "source": meta.get("source", "Unknown"),
            "type": meta.get("type", "text"),
            "timestamp": meta.get("timestamp", ""),
            "chunk_index": meta.get("chunk_index", 0),
            "total_chunks": meta.get("total_chunks", 1)
        })
    
    # 按时间倒序
    docs.sort(key=lambda x: x["timestamp"], reverse=True)
    
    # 去重（同一个 doc_id 只显示一次）
    seen = set()
    unique_docs = []
    for doc in docs:
        if doc["doc_id"] not in seen:
            seen.add(doc["doc_id"])
            unique_docs.append(doc)
    
    result = {
        "status": "success",
        "documents": unique_docs[:top_n]
    }
    
    print(json.dumps(result, ensure_ascii=False))

def xhs(args):
    """抓取小红书链接，生成 Markdown 后存入知识库。"""
    repo_src = Path("/Users/yjj/projects/monorepo/research-kb/src")
    if repo_src.exists() and str(repo_src) not in sys.path:
        sys.path.insert(0, str(repo_src))

    try:
        from research_kb.extractors.xiaohongshu import (
            build_markdown,
            extract_xiaohongshu_url,
        )
    except Exception as exc:
        print(json.dumps({
            "status": "error",
            "error": f"research-kb xiaohongshu extractor unavailable: {exc}",
        }, ensure_ascii=False))
        sys.exit(1)

    if not os.environ.get("RESEARCH_KB_MEDIACRAWLER_DIR"):
        local_mc = Path.home() / ".hermes/workspace/mediacrawler_test/MediaCrawler"
        if local_mc.exists():
            os.environ["RESEARCH_KB_MEDIACRAWLER_DIR"] = str(local_mc)
    if not os.environ.get("RESEARCH_KB_XHS_WORKDIR"):
        os.environ["RESEARCH_KB_XHS_WORKDIR"] = str(Path.home() / ".hermes/workspace/xhs_media")
    if not os.environ.get("RESEARCH_KB_OCR_CMD"):
        local_ocr = Path.home() / ".openclaw/workspace/scripts/ocr_dual.sh"
        if local_ocr.exists():
            os.environ["RESEARCH_KB_OCR_CMD"] = str(local_ocr)

    extraction = extract_xiaohongshu_url(
        args.url,
        include_images=not args.no_images,
        include_video=not args.no_video,
        whisper_model=args.whisper_model,
    )
    content = build_markdown(extraction)
    curate(Namespace(
        kb=args.kb,
        title=args.title or extraction.title,
        source=args.source or args.url,
        content=content,
        type="xiaohongshu",
    ))


def main():
    parser = argparse.ArgumentParser(description="本地知识库 CLI")
    subparsers = parser.add_subparsers(dest="command", help="子命令")
    
    # curate 命令
    curate_parser = subparsers.add_parser("curate", help="存入知识库")
    curate_parser.add_argument("--kb", required=True, help="知识库名称 (ai_research/personal)")
    curate_parser.add_argument("--title", required=True, help="标题")
    curate_parser.add_argument("--source", required=True, help="来源")
    curate_parser.add_argument("--content", required=True, help="内容")
    curate_parser.add_argument("--type", help="内容类型 (pdf/image_ocr/video/xiaohongshu/webpage/text)")
    curate_parser.add_argument("--directions", help="投研方向，逗号分隔 (如 '算力,大模型')")
    curate_parser.add_argument("--tags", help="标签，逗号分隔")
    curate_parser.add_argument("--tickers", help="股票代码，逗号分隔")
    curate_parser.add_argument("--companies", help="涉及公司，逗号分隔")
    curate_parser.add_argument("--quality", default="", help="质量等级 (如 A/B/C，默认空)")
    curate_parser.add_argument("--language", default="zh", help="语言，默认 zh")
    curate_parser.add_argument("--privacy", default="private", help="隐私级别，默认 private")
    curate_parser.add_argument("--ai-initial-view-summary", dest="ai_initial_view_summary",
                               default="", help="AI 初步判断摘要（写入 frontmatter），默认空")
    curate_parser.set_defaults(func=curate)
    
    # query 命令
    query_parser = subparsers.add_parser("query", help="语义检索")
    query_parser.add_argument("--kb", required=True, help="知识库名称")
    query_parser.add_argument("--question", required=True, help="问题")
    query_parser.add_argument("--n", type=int, default=5, help="返回结果数")
    query_parser.set_defaults(func=query)
    
    # recent 命令
    recent_parser = subparsers.add_parser("recent", help="最近入库")
    recent_parser.add_argument("--kb", required=True, help="知识库名称")
    recent_parser.add_argument("--n", type=int, default=10, help="返回结果数")
    recent_parser.set_defaults(func=recent)
    
    # xhs 命令
    xhs_parser = subparsers.add_parser("xhs", help="抓取小红书链接并入库")
    xhs_parser.add_argument("--kb", required=True, help="知识库名称 (ai_research/personal)")
    xhs_parser.add_argument("--url", required=True, help="小红书链接，支持 xhslink.com / xiaohongshu.com")
    xhs_parser.add_argument("--title", help="覆盖标题")
    xhs_parser.add_argument("--source", help="覆盖来源，默认使用 URL")
    xhs_parser.add_argument("--no-images", action="store_true", help="跳过图片 OCR")
    xhs_parser.add_argument("--no-video", action="store_true", help="跳过视频转写")
    xhs_parser.add_argument("--whisper-model", default=None, help="Whisper 模型，默认 medium")
    xhs_parser.set_defaults(func=xhs)
    
    args = parser.parse_args()
    
    if args.command is None:
        parser.print_help()
        sys.exit(1)
    
    args.func(args)

if __name__ == "__main__":
    main()
