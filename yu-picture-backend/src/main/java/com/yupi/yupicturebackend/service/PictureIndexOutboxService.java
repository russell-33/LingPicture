package com.yupi.yupicturebackend.service;

import com.baomidou.mybatisplus.extension.service.IService;
import com.yupi.yupicturebackend.model.entity.Picture;
import com.yupi.yupicturebackend.model.entity.PictureIndexOutbox;

/**
 * 图片 AI 索引 outbox 服务。
 */
public interface PictureIndexOutboxService extends IService<PictureIndexOutbox> {

    PictureIndexOutbox createUpsertEvent(Picture picture);

    PictureIndexOutbox createDeleteEvent(Long pictureId, Long spaceId);

    void markSent(Long eventId);

    void markRetry(Long eventId, int retryCount, String errorMessage);

    void markFailed(Long eventId, int retryCount, String errorMessage);
}
