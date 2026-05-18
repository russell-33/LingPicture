package com.yupi.yupicturebackend.service.impl;

import com.baomidou.mybatisplus.extension.service.impl.ServiceImpl;
import com.yupi.yupicturebackend.mapper.AgentOperationLogMapper;
import com.yupi.yupicturebackend.mapper.AgentSessionMapper;
import com.yupi.yupicturebackend.model.entity.AgentOperationLog;
import com.yupi.yupicturebackend.model.entity.AgentSession;
import com.yupi.yupicturebackend.service.AgentContextService;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;

import javax.annotation.Resource;
import java.util.Date;

@Service
@Slf4j
public class AgentContextServiceImpl extends ServiceImpl<AgentSessionMapper, AgentSession>
        implements AgentContextService {

    @Resource
    private AgentOperationLogMapper agentOperationLogMapper;

    @Override
    public void upsertSessionSummary(String sessionId, Long userId, Long spaceId, String title, String summary) {
        AgentSession existing = lambdaQuery()
                .eq(AgentSession::getSessionId, sessionId)
                .one();
        if (existing != null) {
            lambdaUpdate()
                    .eq(AgentSession::getSessionId, sessionId)
                    .set(AgentSession::getSummary, summary)
                    .set(AgentSession::getTitle, title)
                    .set(AgentSession::getLastMessageTime, new Date())
                    .update();
        } else {
            AgentSession session = new AgentSession();
            session.setSessionId(sessionId);
            session.setUserId(userId);
            session.setSpaceId(spaceId);
            session.setTitle(title);
            session.setSummary(summary);
            session.setLastMessageTime(new Date());
            save(session);
        }
    }

    @Override
    public AgentSession getSessionSummary(String sessionId) {
        return lambdaQuery()
                .eq(AgentSession::getSessionId, sessionId)
                .one();
    }

    @Override
    public void appendOperationLog(String sessionId, Long userId, Long spaceId, String operationType,
                                   String toolName, String targetIds, String requestText,
                                   String resultSummary, String status) {
        AgentOperationLog logEntry = new AgentOperationLog();
        logEntry.setSessionId(sessionId);
        logEntry.setUserId(userId);
        logEntry.setSpaceId(spaceId);
        logEntry.setOperationType(operationType);
        logEntry.setToolName(toolName);
        logEntry.setTargetIds(targetIds);
        logEntry.setRequestText(requestText);
        logEntry.setResultSummary(resultSummary);
        logEntry.setStatus(status);
        agentOperationLogMapper.insert(logEntry);
    }
}
