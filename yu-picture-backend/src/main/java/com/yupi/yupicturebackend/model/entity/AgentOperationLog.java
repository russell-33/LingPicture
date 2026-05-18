package com.yupi.yupicturebackend.model.entity;

import com.baomidou.mybatisplus.annotation.*;

import java.io.Serializable;
import java.util.Date;

import lombok.Data;

/**
 * Agent 业务操作记录
 *
 * @TableName agent_operation_log
 */
@TableName(value = "agent_operation_log")
@Data
public class AgentOperationLog implements Serializable {
    /**
     * id
     */
    @TableId(type = IdType.ASSIGN_ID)
    private Long id;

    /**
     * Agent 会话 id
     */
    private String sessionId;

    /**
     * 用户 id
     */
    private Long userId;

    /**
     * 空间 id
     */
    private Long spaceId;

    /**
     * 操作类型
     */
    private String operationType;

    /**
     * 工具名称
     */
    private String toolName;

    /**
     * 目标图片或资源 id JSON
     */
    private String targetIds;

    /**
     * 用户原始请求
     */
    private String requestText;

    /**
     * 执行结果摘要
     */
    private String resultSummary;

    /**
     * 状态
     */
    private String status;

    /**
     * 创建时间
     */
    private Date createTime;

    @TableField(exist = false)
    private static final long serialVersionUID = 1L;
}
