"""
导入服务 HTTP 入口模块，直接承载导入接口与相关接口业务逻辑。
"""
import shutil
import sys
import uuid
from datetime import datetime
from mimetypes import guess_type
from pathlib import Path

from fastapi import BackgroundTasks, FastAPI, File, UploadFile
from fastapi.responses import FileResponse
from starlette.middleware.cors import CORSMiddleware

from app.api.schema.import_schema import TaskStatusSchema, UploadSchema
from app.shared.runtime.logger import PROJECT_ROOT, logger
from app.process.import_.agent.main_graph import kb_import_app
from app.process.import_.agent.state import get_default_state, ImportGraphState, create_default_state
from app.infra.config.providers import settings
from app.shared.utils.task_utils import (
    TASK_STATUS_COMPLETED,
    TASK_STATUS_FAILED,
    TASK_STATUS_PROCESSING,
    get_done_task_list,
    get_running_task_list,
    get_task_status,
    update_task_status, add_running_task, add_done_task,
)



app = FastAPI(
    title=settings.import_app_name,
    description="企业化 RAG 导入服务，负责文件上传、导入执行与状态查询。",
    version="0.2.0",
)

# 跨域问题 CORS
# 后端 别多管闲事 -> 响应头
app.add_middleware(
    CORSMiddleware,
    # 主机:端口
    allow_origins=list(settings.cors_origins) or ["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# 1. 返回import.html文件
@app.get("/html")
def html():
    html_path_obj = PROJECT_ROOT / "app" / "resources" / "html" / "index2.html"
    return FileResponse(
        path=html_path_obj,
        media_type=guess_type(html_path_obj.name)[0]
    )


# 2. 返回task_id对应的任务状态
@app.get("/status/{task_id}")
def task_status(task_id:str):
    logger.info(f"获取任务状态接口被调用,task_id:{task_id}")
    return TaskStatusSchema(
        code=200,
        task_id=task_id,
        status= get_task_status(task_id),
        done_list= get_done_task_list(task_id),
        running_list= get_running_task_list(task_id)
    )

# 优化后的任务调用逻辑
def invoke_graph(task_id: str, local_file_path: Path, local_dir: Path):
    state = create_default_state(task_id=task_id, local_file_path=str(local_file_path), local_dir=str(local_dir))
    try:
        logger.info(f"[{task_id}] 启动 LangGraph 流程...")
        update_task_status(task_id, TASK_STATUS_PROCESSING)

        # 实际调用 LangGraph
        final_state = kb_import_app.invoke(state)

        update_task_status(task_id, TASK_STATUS_COMPLETED)
        logger.info(f"[{task_id}] 任务圆满完成")
    except Exception as e:
        # 这里建议将具体的 e 存入 Redis 或数据库，以便状态接口能查到
        update_task_status(task_id, TASK_STATUS_FAILED)
        logger.error(f"[{task_id}] 流程中断: {str(e)}")


@app.post("/upload", response_model=UploadSchema)
async def upload_and_invoke_graph(background_tasks: BackgroundTasks, files: list[UploadFile]):
    # 限制文件格式
    allowed_extensions = {".pdf", ".md", ".txt", ".docx"}
    for file in files:
        ext = Path(file.filename).suffix.lower()
        if ext not in allowed_extensions:
            raise Exception(status_code=400, detail=f"不支持的文件类型: {ext}")

    task_id = str(uuid.uuid4())
    add_running_task(task_id, "文件上传预处理")

    # 路径规划
    date_str = datetime.now().strftime("%Y%m%d")
    local_dir = PROJECT_ROOT / "output" / date_str / task_id
    local_dir.mkdir(parents=True, exist_ok=True)

    local_file_path = local_dir / files[0].filename

    # 流式写入，提高大文件稳定性
    try:
        with local_file_path.open("wb") as buffer:
            shutil.copyfileobj(files[0].file, buffer)

        add_done_task(task_id, "文件上传成功")

        # 异步启动图
        background_tasks.add_task(invoke_graph, task_id, local_file_path, local_dir)

        return UploadSchema(message="文件已入队，开始智能解析", task_ids=[task_id])
    except Exception as e:
        update_task_status(task_id, TASK_STATUS_FAILED)
        return UploadSchema(code=500, message=f"上传失败: {str(e)}", task_ids=[])

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=settings.app_host, port=settings.import_app_port)