package com.yupi.yupicturebackend.service.impl;

import cn.hutool.core.util.StrUtil;
import cn.hutool.json.JSONUtil;
import com.baomidou.mybatisplus.core.toolkit.IdWorker;
import com.baomidou.mybatisplus.extension.service.impl.ServiceImpl;
import com.yupi.yupicturebackend.constant.PictureIndexMqConstant;
import com.yupi.yupicturebackend.mapper.PictureIndexOutboxMapper;
import com.yupi.yupicturebackend.model.dto.picture.PictureIndexMessage;
import com.yupi.yupicturebackend.model.entity.Picture;
import com.yupi.yupicturebackend.model.entity.PictureIndexOutbox;
import com.yupi.yupicturebackend.model.enums.PictureIndexEventTypeEnum;
import com.yupi.yupicturebackend.model.enums.PictureIndexOutboxStatusEnum;
import com.yupi.yupicturebackend.service.PictureIndexOutboxService;
import org.springframework.stereotype.Service;

import java.util.Collections;
import java.util.Date;
import java.util.List;

/**
 * 图片 AI 索引 outbox 服务实现。
 */
@Service
public class PictureIndexOutboxServiceImpl extends ServiceImpl<PictureIndexOutboxMapper, PictureIndexOutbox>
        implements PictureIndexOutboxService {

    @Override
    public PictureIndexOutbox createUpsertEvent(Picture picture) {
        if (picture == null || picture.getId() == null) {
            return null;
        }
        PictureIndexMessage message = new PictureIndexMessage();
        message.setEventType(PictureIndexEventTypeEnum.UPSERT.name());
        message.setPictureId(picture.getId());
        message.setSpaceId(picture.getSpaceId());
        message.setName(picture.getName());
        message.setIntroduction(picture.getIntroduction());
        message.setCategory(picture.getCategory());
        message.setTags(parseTags(picture.getTags()));
        message.setUrl(picture.getUrl());
        return saveEvent(message);
    }

    @Override
    public PictureIndexOutbox createDeleteEvent(Long pictureId, Long spaceId) {
        if (pictureId == null || pictureId <= 0) {
            return null;
        }
        PictureIndexMessage message = new PictureIndexMessage();
        message.setEventType(PictureIndexEventTypeEnum.DELETE.name());
        message.setPictureId(pictureId);
        message.setSpaceId(spaceId);
        return saveEvent(message);
    }

    @Override
    public void markSent(Long eventId) {
        if (eventId == null) {
            return;
        }
        PictureIndexOutbox update = new PictureIndexOutbox();
        update.setId(eventId);
        update.setStatus(PictureIndexOutboxStatusEnum.SENT.name());
        update.setLastError("");
        update.setUpdateTime(new Date());
        this.updateById(update);
    }

    @Override
    public void markRetry(Long eventId, int retryCount, String errorMessage) {
        if (eventId == null) {
            return;
        }
        if (retryCount >= PictureIndexMqConstant.MAX_RETRY_COUNT) {
            markFailed(eventId, retryCount, errorMessage);
            return;
        }
        PictureIndexOutbox update = new PictureIndexOutbox();
        update.setId(eventId);
        update.setRetryCount(retryCount);
        update.setLastError(clipError(errorMessage));
        update.setNextRetryTime(new Date(System.currentTimeMillis() + PictureIndexMqConstant.RETRY_DELAY_MILLIS));
        update.setUpdateTime(new Date());
        this.updateById(update);
    }

    @Override
    public void markFailed(Long eventId, int retryCount, String errorMessage) {
        if (eventId == null) {
            return;
        }
        PictureIndexOutbox update = new PictureIndexOutbox();
        update.setId(eventId);
        update.setStatus(PictureIndexOutboxStatusEnum.FAILED.name());
        update.setRetryCount(retryCount);
        update.setLastError(clipError(errorMessage));
        update.setUpdateTime(new Date());
        this.updateById(update);
    }

    private PictureIndexOutbox saveEvent(PictureIndexMessage message) {
        long eventId = IdWorker.getId();
        message.setEventId(eventId);
        message.setTimestamp(new Date());
        message.setRetryCount(0);

        PictureIndexOutbox event = new PictureIndexOutbox();
        event.setId(eventId);
        event.setEventType(message.getEventType());
        event.setPictureId(message.getPictureId());
        event.setSpaceId(message.getSpaceId());
        event.setStatus(PictureIndexOutboxStatusEnum.PENDING.name());
        event.setRetryCount(0);
        event.setPayload(JSONUtil.toJsonStr(message));
        event.setCreateTime(new Date());
        event.setUpdateTime(new Date());
        this.save(event);
        return event;
    }

    private List<String> parseTags(String tagsJson) {
        if (StrUtil.isBlank(tagsJson) || "null".equalsIgnoreCase(tagsJson)) {
            return Collections.emptyList();
        }
        try {
            return JSONUtil.parseArray(tagsJson).toList(String.class);
        } catch (Exception e) {
            return Collections.emptyList();
        }
    }

    private String clipError(String errorMessage) {
        if (errorMessage == null) {
            return "";
        }
        return StrUtil.subPre(errorMessage, 512);
    }
}
