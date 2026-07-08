"""将 data/sources/documents/ 下的文档转为 Markdown，输出到 knowledge/。"""

from pathlib import Path

from markitdown import MarkItDown

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = PROJECT_ROOT / "data" / "sources" / "documents"
OUT_DIR = PROJECT_ROOT / "knowledge"


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    if not SRC_DIR.exists():
        print(f"源目录不存在: {SRC_DIR}")
        return

    md = MarkItDown()
    for src in sorted(SRC_DIR.iterdir()):
        if not src.is_file() or src.suffix.lower() == ".md":
            continue

        out_path = OUT_DIR / f"{src.stem}.md"
        if out_path.exists():
            print(f"跳过（已存在）: {out_path.name}")
            continue

        print(f"转换: {src.name} -> {out_path.name}")
        try:
            result = md.convert(str(src))
            out_path.write_text(result.text_content or "", encoding="utf-8")
        except Exception as e:
            print(f"失败: {src.name} - {e}")

    print("完成")


if __name__ == "__main__":
    main()
