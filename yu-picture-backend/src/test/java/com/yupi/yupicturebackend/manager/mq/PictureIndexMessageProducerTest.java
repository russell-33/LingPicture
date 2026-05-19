package com.yupi.yupicturebackend.manager.mq;

import cn.hutool.json.JSONUtil;
import com.yupi.yupicturebackend.constant.PictureIndexMqConstant;
import com.yupi.yupicturebackend.model.dto.picture.PictureIndexMessage;
import com.yupi.yupicturebackend.model.entity.PictureIndexOutbox;
import com.yupi.yupicturebackend.model.enums.PictureIndexEventTypeEnum;
import com.yupi.yupicturebackend.service.PictureIndexOutboxService;
import org.junit.jupiter.api.Test;
import org.mockito.ArgumentCaptor;
import org.springframework.amqp.rabbit.core.RabbitTemplate;
import org.springframework.test.util.ReflectionTestUtils;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.doThrow;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.verify;

class PictureIndexMessageProducerTest {

    @Test
    void publishOutboxEventSendsMessageAndMarksSent() {
        RabbitTemplate rabbitTemplate = mock(RabbitTemplate.class);
        PictureIndexOutboxService outboxService = mock(PictureIndexOutboxService.class);
        PictureIndexMessageProducer producer = new PictureIndexMessageProducer();
        ReflectionTestUtils.setField(producer, "rabbitTemplate", rabbitTemplate);
        ReflectionTestUtils.setField(producer, "pictureIndexOutboxService", outboxService);

        PictureIndexOutbox event = buildOutboxEvent();

        producer.publishOutboxEvent(event);

        ArgumentCaptor<PictureIndexMessage> messageCaptor = ArgumentCaptor.forClass(PictureIndexMessage.class);
        verify(rabbitTemplate).convertAndSend(
                eq(PictureIndexMqConstant.EXCHANGE),
                eq(PictureIndexMqConstant.ROUTING_KEY),
                messageCaptor.capture()
        );
        assertEquals(100L, messageCaptor.getValue().getEventId());
        assertEquals(123L, messageCaptor.getValue().getPictureId());
        verify(outboxService).markSent(100L);
    }

    @Test
    void publishOutboxEventKeepsPendingWhenMqSendFails() {
        RabbitTemplate rabbitTemplate = mock(RabbitTemplate.class);
        PictureIndexOutboxService outboxService = mock(PictureIndexOutboxService.class);
        doThrow(new RuntimeException("mq down")).when(rabbitTemplate)
                .convertAndSend(eq(PictureIndexMqConstant.EXCHANGE),
                        eq(PictureIndexMqConstant.ROUTING_KEY),
                        any(PictureIndexMessage.class));

        PictureIndexMessageProducer producer = new PictureIndexMessageProducer();
        ReflectionTestUtils.setField(producer, "rabbitTemplate", rabbitTemplate);
        ReflectionTestUtils.setField(producer, "pictureIndexOutboxService", outboxService);

        PictureIndexOutbox event = buildOutboxEvent();
        producer.publishOutboxEvent(event);

        verify(outboxService).markRetry(100L, 1, "mq down");
    }

    private PictureIndexOutbox buildOutboxEvent() {
        PictureIndexMessage message = new PictureIndexMessage();
        message.setEventId(100L);
        message.setEventType(PictureIndexEventTypeEnum.UPSERT.name());
        message.setPictureId(123L);
        message.setSpaceId(456L);
        message.setName("红色赛车");

        PictureIndexOutbox event = new PictureIndexOutbox();
        event.setId(100L);
        event.setPictureId(123L);
        event.setSpaceId(456L);
        event.setPayload(JSONUtil.toJsonStr(message));
        event.setRetryCount(0);
        return event;
    }
}
