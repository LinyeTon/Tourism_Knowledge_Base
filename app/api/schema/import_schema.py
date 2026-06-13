from pydantic import BaseModel, Field
from typing import List, Optional

# 上传文件的响应数据
class UploadSchema(BaseModel):
    code: int = 200
    message: str
    task_ids: List[str]

# 更加详细的任务状态模型
class TaskStatusSchema(BaseModel):
    code: int = 200
    task_id: str
    status: str  # processing, completed, failed
    progress: int = 0  # 新增：0-100 的进度估算
    message: Optional[str] = "" # 新增：异常时的错误描述
    done_list: List[str]
    running_list: List[str]