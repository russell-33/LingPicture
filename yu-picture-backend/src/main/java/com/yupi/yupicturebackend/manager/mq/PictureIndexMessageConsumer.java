package com.yupi.yupicturebackend.manager.mq;

import com.yupi.yupicturebackend.api.ai.AiPictureIndexClient;
import com.yupi.yupicturebackend.constant.PictureIndexMqConstant;
import com.yupi.yupicturebackend.model.dto.picture.PictureIndexMessage;
import com.yupi.yupicturebackend.model.enums.PictureIndexEventTypeEnum;
import com.yupi.yupicturebackend.service.PictureIndexOutboxService;
import lombok.extern.slf4j.Slf4j;
import org.springframework.amqp.rabbit.annotation.RabbitListener;
import org.springframework.stereotype.Component;

import javax.annotation.Resource;

/**
 * 图片 AI 索引消息消费者。
 */
@Component
@Slf4j
public class PictureIndexMessageConsumer {

    @Resource
    private AiPictureIndexClient aiPictureIndexClient;

    @Resource
    private PictureIndexMessageProducer pictureIndexMessageProducer;

    @Resource
    private PictureIndexOutboxService pictureIndexOutboxService;

    @RabbitListener(queues = PictureIndexMqConstant.QUEUE)
    public void consume(PictureIndexMessage message) {
        if (message == null || message.getPictureId() == null) {
            return;
        }
        try {
            if (PictureIndexEventTypeEnum.DELETE.name().equals(message.getEventType())) {
                aiPictureIndexClient.removePictureIndex(message.getPictureId(), message.getSpaceId());
            } else if (PictureIndexEventTypeEnum.UPSERT.name().equals(message.getEventType())) {
                aiPictureIndexClient.upsertPictureIndex(
                        message.getPictureId(),
                        message.getSpaceId(),
                        message.getName(),
                        message.getIntroduction(),
                        message.getCategory(),
                        message.getTags(),
                        message.getUrl()
                );
            } else {
                log.warn("未知图片 AI 索引事件类型，eventId={}, eventType={}", message.getEventId(), message.getEventType());
            }
        } catch (Exception e) {
            handleFailure(message, e);
        }
    }

    private void handleFailure(PictureIndexMessage message, Exception e) {
        int nextRetryCount = (message.getRetryCount() == null ? 0 : message.getRetryCount()) + 1;
        message.setRetryCount(nextRetryCount);
        String errorMessage = e.getMessage() == null ? e.getClass().getSimpleName() : e.getMessage();
        if (nextRetryCount >= PictureIndexMqConstant.MAX_RETRY_COUNT) {
            log.warn("图片 AI 索引消息进入死信队列，eventId={}, pictureId={}, retryCount={}, error={}",
                    message.getEventId(), message.getPictureId(), nextRetryCount, errorMessage);
            pictureIndexOutboxService.markFailed(message.getEventId(), nextRetryCount, errorMessage);
            pictureIndexMessageProducer.publishDlq(message);
            return;
        }

        log.warn("图片 AI 索引消息消费失败，将延迟重试，eventId={}, pictureId={}, retryCount={}, error={}",
                message.getEventId(), message.getPictureId(), nextRetryCount, errorMessage);
        pictureIndexOutboxService.markRetry(message.getEventId(), nextRetryCount, errorMessage);
        pictureIndexMessageProducer.publishRetry(message);
    }
}
