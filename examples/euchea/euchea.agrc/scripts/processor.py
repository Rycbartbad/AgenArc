"""
euchea - PDF→代码生成助手 核心处理模块

功能：
1. 扫描目录中的PDF和CPP文件
2. 将PDF转换为Markdown文本
3. 读取CPP文件内容
4. 构建AI提示词
5. 解析AI响应并保存为文件
"""

import os
import re
import sys
import importlib
from pathlib import Path

# ==================== 配置 ====================
WATCH_DIR = Path(r"C:\Users\Admin\Downloads\AA")
OUTPUT_DIR = Path(r"C:\Users\Admin\Downloads\AA\project")


def _ensure_dirs():
    """确保输出目录存在"""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def _find_pdf_files():
    """查找目录中的PDF文件"""
    if not WATCH_DIR.exists():
        print(f"[euchea] 目录不存在: {WATCH_DIR}")
        return []
    return sorted(WATCH_DIR.glob("*.pdf"))


def _find_all_source_files():
    """查找所有支持的源文件"""
    if not WATCH_DIR.exists():
        return []
    all_files = []
    for ext in ["*.cpp", "*.c", "*.h", "*.hpp", "*.hxx", "*.cxx", "*.cc", "*.c++", "*.h++"]:
        all_files.extend(WATCH_DIR.glob(ext))
    return sorted(set(all_files))


def pdf_to_markdown(pdf_path):
    """将PDF转换为Markdown文本（多引擎回退）"""
    engines = []
    try:
        from markitdown import MarkItDown
        md = MarkItDown()
        result = md.convert(str(pdf_path))
        if result and result.text_content:
            return result.text_content
    except ImportError:
        pass
    except Exception as e:
        print(f"[euchea] markitdown 失败: {e}")

    try:
        import pdfplumber
        with pdfplumber.open(pdf_path) as pdf:
            pages = []
            for page in pdf.pages:
                text = page.extract_text()
                if text:
                    pages.append(text)
            return "\n\n---\n\n".join(pages)
    except ImportError:
        pass
    except Exception as e:
        print(f"[euchea] pdfplumber 失败: {e}")

    try:
        import fitz
        doc = fitz.open(str(pdf_path))
        pages = [page.get_text() for page in doc]
        doc.close()
        return "\n\n---\n\n".join(pages)
    except ImportError:
        pass
    except Exception as e:
        print(f"[euchea] PyMuPDF 失败: {e}")

    return (
        f"[PDF转换失败: {pdf_path.name}]\n"
        f"请安装依赖: uv pip install markitdown\n"
    )


def read_source_file(file_path):
    try:
        with open(file_path, "r", encoding="utf-8", errors="replace") as f:
            return f.read()
    except Exception as e:
        return f"// 读取失败: {e}"


def build_prompt():
    """构建AI提示词，返回 messages 列表"""
    _ensure_dirs()
    sections = []

    # PDF处理
    for pdf_file in _find_pdf_files():
        print(f"[euchea] 转换PDF: {pdf_file.name}")
        md_content = pdf_to_markdown(pdf_file)
        if md_content:
            sections.append(f"## 设计文档: {pdf_file.name}\n\n{md_content}")

    # 源文件处理
    source_files = _find_all_source_files()
    print(f"[euchea] 找到 {len(_find_pdf_files())} 个PDF, {len(source_files)} 个源文件")

    if source_files:
        sections.append("\n## 现有源代码\n")
        for sf in source_files:
            ext = sf.suffix.lower()
            lang = {"cpp": "cpp", "c": "c", "h": "cpp", "hpp": "cpp"}.get(ext.lstrip("."), ext.lstrip("."))
            content = read_source_file(sf)
            rel_path = sf.relative_to(WATCH_DIR) if WATCH_DIR in sf.parents else sf.name
            sections.append(f"### {rel_path}\n\n```{lang}\n{content}\n```")

    instruction = """请根据以上设计文档和现有源代码，完成或生成相应的代码实现。

重要：只输出代码，不要有任何说明文字、问候语或总结。

格式要求（每个文件）：
文件名.后缀
```语言
文件内容
```

规则：
1. 多个文件之间用空行分隔
2. 文件路径使用相对路径
3. 完整实现，可直接编译
"""
    body = "\n\n---\n\n".join(sections) if sections else "(目录中没有找到PDF或源文件)"
    full_prompt = instruction + "\n\n" + body
    print(f"[euchea] 提示词构建完成：{len(full_prompt)} 字符")
    return [{"role": "user", "content": full_prompt}]


def parse_response_and_save(response_text):
    """
    解析AI响应，提取代码块并按文件名保存。

    支持格式：
    main.cpp
    ```cpp
    content
    ```
    或
    ```cpp:main.cpp
    content
    ```
    """
    _ensure_dirs()

    saved = []
    current_filename = None
    in_block = False
    code_lines = []

    _VALID_EXTS = frozenset((
        ".cpp", ".c", ".h", ".hpp", ".cxx", ".hxx", ".cc", ".c++", ".h++", ".inl", ".ipp",
        ".py", ".java", ".js", ".ts", ".jsx", ".tsx", ".rs", ".go", ".cs",
        ".swift", ".kt", ".kts", ".gradle", ".xml", ".json", ".yaml", ".yml",
        ".toml", ".ini", ".cfg", ".cmake", ".txt", ".md", ".sh", ".bat",
        ".ps1", ".css", ".html", ".vue", ".svelte", ".sql", ".proto",
        ".sln", ".vcxproj", ".props", ".env", ".gitignore",
    ))

    def _is_file_line(text):
        if not text or "." not in text:
            return False
        t = text.strip().rstrip(":：;，,、")
        if t.startswith(("http", "www", "```", "#", "(", "[", "<", ">", "-", "*", "+")):
            return False
        if len(t) > 200:
            return False
        return Path(t).suffix.lower() in _VALID_EXTS

    def _find_filename(text):
        t = text.strip()
        if _is_file_line(t):
            return t.rstrip(":：;，,、")
        parts = t.replace("\\", "/").split("/")
        for p in reversed(parts):
            if _is_file_line(p):
                return p
        m = re.search(r'[\'"`]?([\w./\\-]+\.[a-zA-Z]+)[\'"`]?', t)
        if m and _is_file_line(m.group(1)):
            return m.group(1)
        return None

    for line in response_text.split("\n"):
        stripped = line.strip()

        # 代码块开关
        if stripped.startswith("```"):
            if in_block:
                # 关闭代码块 → 保存
                if current_filename and code_lines:
                    content = "\n".join(code_lines).strip()
                    if content:
                        fp = OUTPUT_DIR / current_filename
                        fp.parent.mkdir(parents=True, exist_ok=True)
                        fp.write_text(content + "\n", encoding="utf-8")
                        saved.append(str(fp.relative_to(OUTPUT_DIR)))
                        print(f"[euchea] 已保存: {fp}")
                current_filename = None
                code_lines = []
                in_block = False
            else:
                # 打开代码块
                in_block = True
                code_lines = []
                # ```cpp:main.cpp 或 ```cpp main.cpp
                rest = stripped[3:].strip()
                if rest:
                    for sep in (":", " ", "|"):
                        if sep in rest:
                            after = rest.split(sep, 1)[1].strip()
                            fn = _find_filename(after)
                            if fn:
                                current_filename = fn
                                break
            continue

        if in_block:
            code_lines.append(line)
            continue

        # 代码块外：检测文件名
        if not stripped or not _is_file_line(stripped):
            continue
        current_filename = _find_filename(stripped)

    # 末尾未关闭的代码块
    if in_block and current_filename and code_lines:
        content = "\n".join(code_lines).strip()
        if content:
            fp = OUTPUT_DIR / current_filename
            fp.parent.mkdir(parents=True, exist_ok=True)
            fp.write_text(content + "\n", encoding="utf-8")
            saved.append(str(fp.relative_to(OUTPUT_DIR)))
            print(f"[euchea] 已保存: {fp}")

    # 回退：纯文本格式（无 ``` 时）
    if not saved and not in_block:
        lines = response_text.split("\n")
        i = 0
        while i < len(lines):
            fn = _find_filename(lines[i])
            if fn:
                clines = []
                i += 1
                while i < len(lines) and not _find_filename(lines[i]):
                    if not lines[i].strip().startswith("```"):
                        clines.append(lines[i])
                    i += 1
                content = "\n".join(clines).strip()
                if content:
                    fp = OUTPUT_DIR / fn
                    fp.parent.mkdir(parents=True, exist_ok=True)
                    fp.write_text(content + "\n", encoding="utf-8")
                    saved.append(str(fp.relative_to(OUTPUT_DIR)))
                    print(f"[euchea] 已保存: {fn}")
            else:
                i += 1

    print(f"[euchea] 保存完成，共 {len(saved)} 个文件")
    return saved
