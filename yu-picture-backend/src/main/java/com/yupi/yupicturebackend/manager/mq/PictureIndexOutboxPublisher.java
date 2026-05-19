package com.yupi.yupicturebackend.manager.mq;

import com.baomidou.mybatisplus.core.conditions.query.QueryWrapper;
import com.yupi.yupicturebackend.model.entity.PictureIndexOutbox;
import com.yupi.yupicturebackend.model.enums.PictureIndexOutboxStatusEnum;
import com.yupi.yupicturebackend.service.PictureIndexOutboxService;
import lombok.extern.slf4j.Slf4j;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Component;

import javax.annotation.Resource;
import java.util.Date;
import java.util.List;

/**
 * 图片 AI 索引 outbox 补发任务。
 */
@Component
@Slf4j
public class PictureIndexOutboxPublisher {

    private static final int BATCH_SIZE = 50;

    @Resource
    private PictureIndexOutboxService pictureIndexOutboxService;

    @Resource
    private PictureIndexMessageProducer pictureIndexMessageProducer;

    @Scheduled(fixedDelay = 10000)
    public void publishPendingEvents() {
        QueryWrapper<PictureIndexOutbox> queryWrapper = new QueryWrapper<>();
        queryWrapper.eq("status", PictureIndexOutboxStatusEnum.PENDING.name())
                .and(wrapper -> wrapper.isNull("nextRetryTime").or().le("nextRetryTime", new Date()))
                .orderByAsc("createTime")
                .last("limit " + BATCH_SIZE);
        List<PictureIndexOutbox> events = pictureIndexOutboxService.list(queryWrapper);
        if (events == null || events.isEmpty()) {
            return;
        }
        for (PictureIndexOutbox event : events) {
            pictureIndexMessageProducer.publishOutboxEvent(event);
        }
    }
}
