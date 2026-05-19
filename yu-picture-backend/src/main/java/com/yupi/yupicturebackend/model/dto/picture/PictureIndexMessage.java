package com.yupi.yupicturebackend.model.dto.picture;

import lombok.Data;

import java.io.Serializable;
import java.util.Date;
import java.util.List;

/**
 * 图片 AI 索引 MQ 消息。
 */
@Data
public class PictureIndexMessage implements Serializable {

    private Long eventId;

    private String eventType;

    private Long pictureId;

    private Long spaceId;

    private String name;

    private String introduction;

    private String category;

    private List<String> tags;

    private String url;

    private Date timestamp;

    private Integer retryCount = 0;

    private static final long serialVersionUID = 1L;
}
