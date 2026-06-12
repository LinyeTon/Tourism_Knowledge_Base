from app.shared.runtime.logger import node_log
from app.shared.utils.task_utils import add_done_task, add_running_task
from app.process.import_.agent.state import ImportGraphState
from app.rag.import_.doc_parse_service import parse_doc_to_markdown

@node_log("node_doc_to_md")
def node_doc_to_md(state: ImportGraphState) -> ImportGraphState:
    """
    节点: PDF转Markdown (node_doc_to_md)
    为什么叫这个名字: 核心任务是将 PDF 非结构化数据转换为 Markdown 结构化数据。
    """
    add_running_task(state["task_id"], "node_doc_to_md")
    state = parse_doc_to_markdown(state)
    add_done_task(state["task_id"], "node_doc_to_md")
    return state


if __name__ == "__main__":
    from app.shared.runtime.logger import logger,PROJECT_ROOT
    import os
    from app.process.import_.agent.state import create_default_state
    logger.info("===== 开始 node_doc_to_md 节点联调测试 =====")

    test_pdf_path = os.path.join(PROJECT_ROOT, "doc", "hak180产品安全手册.pdf")
    test_state = create_default_state(
        task_id="test_pdf2md_task_001",
        pdf_path=test_pdf_path,
        local_dir=os.path.join(PROJECT_ROOT, "output"),
    )

    result = node_doc_to_md(test_state)
    logger.info(f"md_path: {result['md_path']}")
    logger.info(f"md_content长度: {len(result['md_content'])}")
    logger.info("===== 结束 node_doc_to_md 节点联调测试 =====")