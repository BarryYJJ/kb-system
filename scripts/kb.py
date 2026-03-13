#!/usr/bin/env python3
"""
本地知识库 CLI 工具
使用 ChromaDB + sentence-transformers 实现本地语义搜索
"""
import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path

# 解决 Mac 上多个 OpenMP 版本冲突问题（必须在 import 其他库之前设置）
os.environ['KMP_DUPLICATE_LIB_OK'] = 'TRUE'

import chromadb
from sentence_transformers import SentenceTransformer

# 配置
EMBEDDING_MODEL = "paraphrase-multilingual-MiniLM-L12-v2"
BASE_DIR = Path.home() / ".openclaw" / "workspace" / "knowledge_bases"

# 全局模型缓存
_model = None

def get_model():
    global _model
    if _model is None:
        print("Loading embedding model...", file=sys.stderr)
        _model = SentenceTransformer(EMBEDDING_MODEL)
        print("Model loaded", file=sys.stderr)
    return _model

def get_chroma_client(kb_name: str):
    """获取 ChromaDB 客户端"""
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

def curate(args):
    """存入知识库"""
    kb_name = args.kb
    title = args.title
    source = args.source
    content = args.content
    content_type = args.type or "text"
    
    # 确保目录存在
    docs_dir = BASE_DIR / kb_name / "documents"
    docs_dir.mkdir(parents=True, exist_ok=True)
    
    # 保存 markdown 备份
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_title = "".join(c for c in title if c.isalnum() or c in " -_")[:50]
    md_path = docs_dir / f"{safe_title}_{timestamp}.md"
    
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(f"# {title}\n\n")
        f.write(f"**来源**: {source}\n\n")
        f.write(f"**类型**: {content_type}\n\n")
        f.write(f"**入库时间**: {datetime.now().isoformat()}\n\n")
        f.write("---\n\n")
        f.write(content)
    
    # 分段处理
    chunks = split_text(content)
    
    # 获取 embedding 模型
    model = get_model()
    
    # 获取 ChromaDB
    client = get_chroma_client(kb_name)
    collection = get_collection(client, kb_name)
    
    # 生成 doc_id
    doc_id = f"doc_{timestamp}"
    
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
                "timestamp": datetime.now().isoformat(),
                "chunk_index": i,
                "total_chunks": len(chunks)
            }]
        )
    
    result = {
        "status": "success",
        "doc_id": doc_id,
        "chunks": len(chunks),
        "total_docs": collection.count(),
        "md_backup": str(md_path),
        "timestamp": datetime.now().isoformat()
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
    
    args = parser.parse_args()
    
    if args.command is None:
        parser.print_help()
        sys.exit(1)
    
    args.func(args)

if __name__ == "__main__":
    main()
