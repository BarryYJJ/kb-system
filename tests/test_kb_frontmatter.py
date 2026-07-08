"""kb.py 纯函数单元测试。

这些测试只覆盖 frontmatter 渲染、列表解析、标题归一化、旧元信息块移除等
纯逻辑，不需要下载 embedding 模型，也不需要真实 ChromaDB —— kb.py 已将重依赖
改为惰性导入，因此可直接导入模块。
"""
import importlib.util
import sys
from pathlib import Path

# 直接从脚本路径加载 kb 模块（无需安装为包）
_KB_PATH = Path(__file__).resolve().parent.parent / "scripts" / "kb.py"
_spec = importlib.util.spec_from_file_location("kb", _KB_PATH)
kb = importlib.util.module_from_spec(_spec)
sys.modules["kb"] = kb
_spec.loader.exec_module(kb)


# --------------------------------------------------------------------------
# content hash
# --------------------------------------------------------------------------

def test_content_hash_shape():
    full, short = kb.compute_content_hash("hello world")
    assert full.startswith("sha256:")
    assert len(short) == 8
    # 短哈希是完整 hex 的前 8 位
    assert full.split(":", 1)[1].startswith(short)


def test_content_hash_stable():
    a, _ = kb.compute_content_hash("同一段内容")
    b, _ = kb.compute_content_hash("同一段内容")
    c, _ = kb.compute_content_hash("不同的内容")
    assert a == b
    assert a != c


# --------------------------------------------------------------------------
# frontmatter 渲染
# --------------------------------------------------------------------------

def test_render_frontmatter_keys_present():
    fm = kb.render_frontmatter([
        ("doc_id", "kb_ai_research_20260707_165115_a1b2c3d4"),
        ("kb", "ai_research"),
        ("title", "测试标题: 含冒号"),
        ("directions", ["算力", "大模型"]),
        ("tags", []),
        ("companies", ["Credo", "STM"]),
        ("quality", ""),
        ("attachment_refs", []),
    ])
    assert fm.startswith("---\n")
    assert fm.rstrip().endswith("---")
    for key in ("doc_id:", "kb:", "title:", "directions:", "tags:", "companies:", "quality:"):
        assert key in fm, f"missing {key}"
    # 列表 flow 风格
    assert "directions: [算力, 大模型]" in fm
    assert "tags: []" in fm
    assert "companies: [Credo, STM]" in fm
    # 含冒号的标题需要加引号
    assert 'title: "测试标题: 含冒号"' in fm
    # 空字符串渲染为 ""
    assert 'quality: ""' in fm


def test_yaml_scalar_quoting():
    assert kb._yaml_scalar("plain") == "plain"
    assert kb._yaml_scalar("zh") == "zh"
    assert kb._yaml_scalar("") == '""'
    assert kb._yaml_scalar("has: colon") == '"has: colon"'
    assert kb._yaml_scalar("a,b") == '"a,b"'
    # 数字样式的字符串需加引号以保持为字符串
    assert kb._yaml_scalar("123") == '"123"'
    # 转义双引号
    assert kb._yaml_scalar('quote"inside') == '"quote\\"inside"'


def _assert_reuters_style_frontmatter(markdown: str, source_type: str):
    assert markdown.startswith("---\n")
    head = markdown.split("---\n", 2)[1]
    for key in (
        "doc_id:", "kb:", "title:", "directions:", "source_type:",
        "source:", "ingested_at:", "updated_at:", "language:", "quality:",
        "tags:", "tickers:", "companies:", "ai_initial_view_summary:",
        "privacy:", "content_hash:", "attachment_refs:",
    ):
        assert key in head, f"missing {key} for {source_type}"
    assert f"source_type: {source_type}" in head
    assert "\n**来源**:" not in markdown[:500]
    assert "\n**类型**:" not in markdown[:500]
    assert "\n**入库时间**:" not in markdown[:500]


def test_build_markdown_document_frontmatter_for_all_ingest_types():
    # 覆盖 text / webpage / pdf / image_ocr / 视频转录，避免某条入库路径退回旧格式。
    for source_type in ("text", "webpage", "pdf", "image_ocr", "video_transcript"):
        title = f"回归测试 {source_type}"
        markdown = kb.build_markdown_document(
            title=title,
            body=f"# {title}\n\n**来源**: 旧头部\n\n**类型**: text\n\n**入库时间**: 2026-07-08T20:00:00\n\n---\n\n## 核心摘要\n正文",
            doc_id=f"kb_ai_research_20260708_200000_{source_type.replace('_', '')[:8]}",
            kb_name="ai_research",
            source_type=source_type,
            source="fixture",
            ingested_at="2026-07-08T20:00:00+08:00",
            updated_at="2026-07-08T20:00:00+08:00",
            directions=["大模型"],
            tags=["regression"],
            tickers=[],
            companies=["OpenAI"],
            quality="B",
            language="zh",
            privacy="private",
            ai_initial_view_summary="fixture",
            content_hash="sha256:abc",
            attachment_refs=[],
        )
        _assert_reuters_style_frontmatter(markdown, source_type)
        assert markdown.count("# 回归测试") == 1
        assert "## 核心摘要" in markdown


# --------------------------------------------------------------------------
# 列表解析
# --------------------------------------------------------------------------

def test_parse_list_arg():
    assert kb.parse_list_arg(None) == []
    assert kb.parse_list_arg("") == []
    assert kb.parse_list_arg("算力,大模型") == ["算力", "大模型"]
    # 去空白、丢空项
    assert kb.parse_list_arg(" a , b ,, c ") == ["a", "b", "c"]
    assert kb.parse_list_arg("single") == ["single"]


# --------------------------------------------------------------------------
# 标题归一化
# --------------------------------------------------------------------------

def test_normalize_headings():
    src = "\n".join([
        "## 小八投研判断",
        "内容1",
        "## 小八判断",
        "内容2",
        "### 投研判断(小八)",
        "内容3",
        "## 投研判断（小八）",
        "内容4",
    ])
    out = kb.normalize_content_headings(src)
    assert "## AI初步判断(小八)" in out
    assert "### AI初步判断(小八)" in out  # 保留原级别
    assert "小八投研判断" not in out
    assert "小八判断" not in out
    # 非判断标题不受影响
    assert kb.normalize_content_headings("## 核心摘要") == "## 核心摘要"


def test_normalize_headings_preserves_body():
    src = "## 核心摘要\n正文提到小八判断这个词但不是标题\n## 来源事实与关键数据\n数据"
    out = kb.normalize_content_headings(src)
    assert "正文提到小八判断这个词但不是标题" in out
    assert "## 核心摘要" in out


# --------------------------------------------------------------------------
# 旧元信息块移除（保守）
# --------------------------------------------------------------------------

def test_remove_old_meta_block():
    src = "\n".join([
        "# 某标题",
        "",
        "**来源**: webpage | https://x.com",
        "",
        "**类型**: webpage",
        "",
        "**入库时间**: 2026-07-07T16:51:15",
        "",
        "---",
        "",
        "## 核心摘要",
        "真正的正文",
    ])
    out = kb.remove_duplicate_metadata_block(src)
    assert "**来源**" not in out
    assert "**类型**" not in out
    assert "**入库时间**" not in out
    assert "## 核心摘要" in out
    assert "真正的正文" in out
    assert "# 某标题" in out


def test_remove_meta_is_conservative():
    # 没有旧元信息块时原样返回
    src = "## 核心摘要\n**重点数据**: 营收增长 30%\n更多正文"
    assert kb.remove_duplicate_metadata_block(src) == src
    # 不删除非白名单的加粗行（如来源事实）
    assert "**重点数据**: 营收增长 30%" in kb.remove_duplicate_metadata_block(src)


def test_remove_meta_only_at_head():
    # 正文中部出现的 **来源** 不应被移除（本函数只处理开头块）
    src = "\n".join([
        "# 标题",
        "## 核心摘要",
        "摘要正文",
        "## 来源事实与关键数据",
        "**来源**: 这是正文里引用的来源事实，不能删",
    ])
    out = kb.remove_duplicate_metadata_block(src)
    assert "这是正文里引用的来源事实，不能删" in out


def test_remove_meta_preserves_leading_source_facts_section():
    # 如果正文一开头就是来源事实章节，下面的 **来源** 是事实，不是旧元信息块。
    src = "\n".join([
        "## 来源事实与关键数据",
        "**来源**: 九谦访谈纪要原文，不能删",
        "**核心数据**: 订单同比增长 30%",
        "## AI初步判断(小八)",
        "这才是判断。",
    ])
    out = kb.remove_duplicate_metadata_block(src)
    assert "## 来源事实与关键数据" in out
    assert "九谦访谈纪要原文，不能删" in out
    assert "**核心数据**: 订单同比增长 30%" in out


def test_remove_meta_requires_complete_legacy_block():
    # 单个 **来源** 即使在 H1 标题后出现，也不够构成旧元信息块。
    src = "# 标题\n\n**来源**: 这是正文事实\n\n## 核心摘要\n正文"
    assert kb.remove_duplicate_metadata_block(src) == src


def test_remove_leading_title_duplicates():
    title = "九谦论坛调研周度小结"
    src = f"# {title}\n\n# {title}\n\n## 核心摘要\n正文"
    out = kb.remove_leading_title_duplicates(src, title)
    assert not out.startswith("# 九谦论坛")
    assert "## 核心摘要" in out


def test_remove_leading_meta_section():
    src = "\n".join([
        "## 元信息",
        "- 来源类型：PDF扫描OCR",
        "- 文件名：jiuqian.pdf",
        "",
        "## 核心摘要",
        "正文",
    ])
    out = kb.remove_leading_meta_section(src)
    assert "## 元信息" not in out
    assert "jiuqian.pdf" not in out
    assert out.startswith("## 核心摘要")


def test_remove_meta_section_only_when_leading():
    src = "## 核心摘要\n正文\n## 元信息\n这是正文中部元信息"
    assert kb.remove_leading_meta_section(src) == src


def test_remove_meta_section_after_h1_title():
    # 旧文档 H1 与新 title 不一致时 H1 会保留，其后的 `## 元信息` 仍应被移除。
    src = "\n".join([
        "# 旧文档标题",
        "",
        "## 元信息",
        "- 来源类型：PDF扫描OCR",
        "",
        "## 核心摘要",
        "正文",
    ])
    out = kb.remove_leading_meta_section(src)
    assert "## 元信息" not in out
    assert "PDF扫描OCR" not in out
    assert "# 旧文档标题" in out
    assert "## 核心摘要" in out


def test_remove_meta_section_keeps_content_when_nothing_follows():
    # `## 元信息` 后没有任何后续章节/正文时，宁可保留也不删成空文档。
    src = "## 元信息\n- 来源类型：PDF扫描OCR\n- 文件名：x.pdf"
    assert kb.remove_leading_meta_section(src) == src

if __name__ == "__main__":

    import traceback
    funcs = [v for k, v in sorted(globals().items())
             if k.startswith("test_") and callable(v)]
    failed = 0
    for fn in funcs:
        try:
            fn()
            print(f"PASS {fn.__name__}")
        except Exception:
            failed += 1
            print(f"FAIL {fn.__name__}")
            traceback.print_exc()
    print(f"\n{len(funcs) - failed}/{len(funcs)} passed")
    sys.exit(1 if failed else 0)
