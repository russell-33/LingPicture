package com.yupi.yupicturebackend.manager.mq;

import cn.hutool.json.JSONUtil;
import com.yupi.yupicturebackend.constant.PictureIndexMqConstant;
import com.yupi.yupicturebackend.model.dto.picture.PictureIndexMessage;
import com.yupi.yupicturebackend.model.entity.PictureIndexOutbox;
import com.yupi.yupicturebackend.service.PictureIndexOutboxService;
import lombok.extern.slf4j.Slf4j;
import org.springframework.amqp.rabbit.core.RabbitTemplate;
import org.springframework.stereotype.Component;

import javax.annotation.Resource;

/**
 * 图片 AI 索引消息生产者。
 */
@Component
@Slf4j
public class PictureIndexMessageProducer {

    @Resource
    private RabbitTemplate rabbitTemplate;

    @Resource
    private PictureIndexOutboxService pictureIndexOutboxService;

    public void publishOutboxEvent(PictureIndexOutbox event) {
        if (event == null || event.getId() == null || !JSONUtil.isTypeJSON(event.getPayload())) {
            return;
        }
        int retryCount = event.getRetryCount() == null ? 0 : event.getRetryCount();
        try {
            PictureIndexMessage message = JSONUtil.toBean(event.getPayload(), PictureIndexMessage.class);
            message.setEventId(event.getId());
            publish(message, PictureIndexMqConstant.ROUTING_KEY);
            pictureIndexOutboxService.markSent(event.getId());
        } catch (Exception e) {
            log.warn("发送图片 AI 索引消息失败，eventId={}, pictureId={}, error={}",
                    event.getId(), event.getPictureId(), e.getMessage());
            pictureIndexOutboxService.markRetry(event.getId(), retryCount + 1, e.getMessage());
        }
    }

    public void publishRetry(PictureIndexMessage message) {
        publish(message, PictureIndexMqConstant.RETRY_ROUTING_KEY);
    }

    public void publishDlq(PictureIndexMessage message) {
        publish(message, PictureIndexMqConstant.DLQ_ROUTING_KEY);
    }

    private void publish(PictureIndexMessage message, String routingKey) {
        rabbitTemplate.convertAndSend(PictureIndexMqConstant.EXCHANGE, routingKey, message);
    }
}
