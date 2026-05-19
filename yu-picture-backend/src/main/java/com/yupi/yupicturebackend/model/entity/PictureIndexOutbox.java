package com.yupi.yupicturebackend.model.entity;

import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableField;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableName;
import lombok.Data;

import java.io.Serializable;
import java.util.Date;

/**
 * 图片 AI 索引 outbox 事件。
 *
 * @TableName picture_index_outbox
 */
@TableName(value = "picture_index_outbox")
@Data
public class PictureIndexOutbox implements Serializable {

    /**
     * id
     */
    @TableId(type = IdType.ASSIGN_ID)
    private Long id;

    /**
     * 事件类型：UPSERT / DELETE
     */
    private String eventType;

    /**
     * 图片 id
     */
    private Long pictureId;

    /**
     * 空间 id
     */
    private Long spaceId;

    /**
     * 索引消息 JSON
     */
    private String payload;

    /**
     * 状态：PENDING / SENT / FAILED
     */
    private String status;

    /**
     * 重试次数
     */
    private Integer retryCount;

    /**
     * 最近错误
     */
    private String lastError;

    /**
     * 下次补发时间
     */
    private Date nextRetryTime;

    /**
     * 创建时间
     */
    private Date createTime;

    /**
     * 更新时间
     */
    private Date updateTime;

    @TableField(exist = false)
    private static final long serialVersionUID = 1L;
}
