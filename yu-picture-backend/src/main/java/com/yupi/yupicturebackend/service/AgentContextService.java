package com.yupi.yupicturebackend.service;

import com.yupi.yupicturebackend.model.entity.AgentOperationLog;
import com.yupi.yupicturebackend.model.entity.AgentSession;
import com.baomidou.mybatisplus.extension.service.IService;

/**
 * @author cass.
 * @description Agent 上下文持久化服务
 * @createDate 2026-05-11
 */
public interface AgentContextService extends IService<AgentSession> {

    /**
     * 新增或更新会话摘要
     */
    void upsertSessionSummary(String sessionId, Long userId, Long spaceId, String title, String summary);

    /**
     * 查询会话摘要
     */
    AgentSession getSessionSummary(String sessionId);

    /**
     * 追加操作日志
     */
    void appendOperationLog(String sessionId, Long userId, Long spaceId, String operationType,
                            String toolName, String targetIds, String requestText,
                            String resultSummary, String status);
}
