from argparse import ArgumentParser
from pathlib import Path

from dotenv import load_dotenv


def main() -> None:
    parser = ArgumentParser(description="生成 Email Agent 的 LangGraph 流程图")

    parser.add_argument(
        "--output",
        default="artifacts/email-agent-graph.png",
        help="PNG 输出路径",
    )

    args = parser.parse_args()

    # 确保创建模型前加载环境变量
    load_dotenv()

    from email_agent.agent_server import create_graph

    output_path = Path(args.output).resolve()
    output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    mermaid_path = output_path.with_suffix(".mmd")

    graph = create_graph()
    drawable_graph = graph.get_graph(xray=True)

    # Mermaid 源码可以离线生成
    mermaid_text = drawable_graph.draw_mermaid()

    mermaid_path.write_text(
        mermaid_text,
        encoding="utf-8",
    )

    print(f"Mermaid 文件已生成：{mermaid_path}")

    try:
        drawable_graph.draw_mermaid_png(
            output_file_path=str(output_path),
            background_color="white",
            padding=20,
            max_retries=3,
        )
    except (ValueError, ImportError, OSError) as exc:
        print("PNG 生成失败，但 Mermaid 文件已保留。")
        print(f"失败原因：{exc}")
        return

    print(f"PNG 流程图已生成：{output_path}")


if __name__ == "__main__":
    main()
