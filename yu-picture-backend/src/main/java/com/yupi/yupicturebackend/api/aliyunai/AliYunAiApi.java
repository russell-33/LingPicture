package com.yupi.yupicturebackend.api.aliyunai;

import cn.hutool.core.util.StrUtil;
import cn.hutool.http.HttpRequest;
import cn.hutool.http.HttpResponse;
import cn.hutool.json.JSONUtil;
import com.yupi.yupicturebackend.api.aliyunai.model.CreateOutPaintingTaskRequest;
import com.yupi.yupicturebackend.api.aliyunai.model.CreateOutPaintingTaskResponse;
import com.yupi.yupicturebackend.api.aliyunai.model.GetOutPaintingTaskResponse;
import com.yupi.yupicturebackend.exception.BusinessException;
import com.yupi.yupicturebackend.exception.ErrorCode;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;

import static com.yupi.yupicturebackend.exception.ThrowUtils.throwIf;

@Slf4j
@Component
public class AliYunAiApi {
    //读取配置文件
    @Value("${aliyunAi.apiKey}")
    private String apiKey;

    private static final String CREATE_PAINTING_TASK = "https://dashscope.aliyuncs.com/api/v1/services/aigc/image2image/out-painting";
    private static final String GET_PAINTING_RESULT = "https://dashscope.aliyuncs.com/api/v1/tasks/%s";

    /**
     * 创建任务
     *
     * @param createOutPaintingTaskRequest
     * @return
     */
    public CreateOutPaintingTaskResponse createOutPaintingTaskResponse(CreateOutPaintingTaskRequest createOutPaintingTaskRequest) {
        throwIf(createOutPaintingTaskRequest == null, ErrorCode.PARAMS_ERROR, "扩图参数为空");
        HttpRequest request = HttpRequest.post(CREATE_PAINTING_TASK)
                .header("Authorization", "Bearer " + apiKey)
                .header("Content-Type", "application/json")
                .header("X-DashScope-Async", "enable")
                .body(JSONUtil.toJsonStr(createOutPaintingTaskRequest));
        try (HttpResponse response = request.execute()) {
            if (!response.isOk()) {
                log.error("请求异常:{}", response.body());
                throw new BusinessException(ErrorCode.OPERATION_ERROR, "ai扩图失败");
            }
            CreateOutPaintingTaskResponse createOutPaintingTaskResponse =
                    JSONUtil.toBean(response.body(), CreateOutPaintingTaskResponse.class);
            if (createOutPaintingTaskResponse.getCode() != null) {
                String message = createOutPaintingTaskResponse.getMessage();
                log.error("请求异常:{}", message);
                throw new BusinessException(ErrorCode.OPERATION_ERROR, "ai扩图失败" + message);
            }
            return createOutPaintingTaskResponse;
        }
    }

    /**
     * 查询创建的任务结果
     *
     * @param taskId
     * @return
     */
    public GetOutPaintingTaskResponse getOutPaintingTaskResponse(String taskId) {
        throwIf(StrUtil.isBlank(taskId), ErrorCode.PARAMS_ERROR, "任务id为空");
        String url = String.format(GET_PAINTING_RESULT, taskId);
        try (HttpResponse response = HttpRequest.get(url)
                .header("Authorization", "Bearer " + apiKey).execute()) {
            if (!response.isOk()) {
                log.error("请求异常:{}", response.body());
                throw new BusinessException(ErrorCode.OPERATION_ERROR, "获取任务失败");
            }
            GetOutPaintingTaskResponse getOutPaintingTaskResponse =
                    JSONUtil.toBean(response.body(), GetOutPaintingTaskResponse.class);
//            if(!"SUCCEEDED".equals(getOutPaintingTaskResponse.getOutput().getTaskStatus())){
//                log.error("请求异常:{}",response.body());
//                throw new BusinessException(ErrorCode.OPERATION_ERROR,"图片尚未生成完毕");
//            }
            return getOutPaintingTaskResponse;
        }
    }
}
