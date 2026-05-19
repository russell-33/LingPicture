package com.yupi.yupicturebackend.manager.mq;

import com.yupi.yupicturebackend.api.ai.AiPictureIndexClient;
import com.yupi.yupicturebackend.model.dto.picture.PictureIndexMessage;
import com.yupi.yupicturebackend.model.enums.PictureIndexEventTypeEnum;
import com.yupi.yupicturebackend.service.PictureIndexOutboxService;
import org.junit.jupiter.api.Test;
import org.springframework.test.util.ReflectionTestUtils;

import java.util.List;

import static org.mockito.Mockito.doThrow;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.verify;

class PictureIndexMessageConsumerTest {

    @Test
    void consumeUpsertCallsAiBuildIndexClient() {
        AiPictureIndexClient client = mock(AiPictureIndexClient.class);
        PictureIndexMessageConsumer consumer = buildConsumer(client, mock(PictureIndexMessageProducer.class),
                mock(PictureIndexOutboxService.class));
        PictureIndexMessage message = buildUpsertMessage();

        consumer.consume(message);

        verify(client).upsertPictureIndex(
                123L,
                456L,
                "红色赛车",
                "赛道上的红色赛车",
                "素材",
                List.of("汽车"),
                "https://img.test/1.webp"
        );
    }

    @Test
    void consumeDeleteCallsAiDeleteIndexClient() {
        AiPictureIndexClient client = mock(AiPictureIndexClient.class);
        PictureIndexMessageConsumer consumer = buildConsumer(client, mock(PictureIndexMessageProducer.class),
                mock(PictureIndexOutboxService.class));
        PictureIndexMessage message = new PictureIndexMessage();
        message.setEventId(100L);
        message.setEventType(PictureIndexEventTypeEnum.DELETE.name());
        message.setPictureId(123L);
        message.setSpaceId(456L);

        consumer.consume(message);

        verify(client).removePictureIndex(123L, 456L);
    }

    @Test
    void consumeFailurePublishesRetryBeforeMaxRetryCount() {
        AiPictureIndexClient client = mock(AiPictureIndexClient.class);
        doThrow(new RuntimeException("ai down")).when(client)
                .upsertPictureIndex(123L, 456L, "红色赛车", "赛道上的红色赛车",
                        "素材", List.of("汽车"), "https://img.test/1.webp");
        PictureIndexMessageProducer producer = mock(PictureIndexMessageProducer.class);
        PictureIndexOutboxService outboxService = mock(PictureIndexOutboxService.class);
        PictureIndexMessageConsumer consumer = buildConsumer(client, producer, outboxService);
        PictureIndexMessage message = buildUpsertMessage();

        consumer.consume(message);

        verify(outboxService).markRetry(100L, 1, "ai down");
        verify(producer).publishRetry(message);
    }

    @Test
    void consumeFailurePublishesDlqAfterMaxRetryCount() {
        AiPictureIndexClient client = mock(AiPictureIndexClient.class);
        doThrow(new RuntimeException("ai down")).when(client)
                .upsertPictureIndex(123L, 456L, "红色赛车", "赛道上的红色赛车",
                        "素材", List.of("汽车"), "https://img.test/1.webp");
        PictureIndexMessageProducer producer = mock(PictureIndexMessageProducer.class);
        PictureIndexOutboxService outboxService = mock(PictureIndexOutboxService.class);
        PictureIndexMessageConsumer consumer = buildConsumer(client, producer, outboxService);
        PictureIndexMessage message = buildUpsertMessage();
        message.setRetryCount(2);

        consumer.consume(message);

        verify(outboxService).markFailed(100L, 3, "ai down");
        verify(producer).publishDlq(message);
    }

    private PictureIndexMessageConsumer buildConsumer(AiPictureIndexClient client,
                                                      PictureIndexMessageProducer producer,
                                                      PictureIndexOutboxService outboxService) {
        PictureIndexMessageConsumer consumer = new PictureIndexMessageConsumer();
        ReflectionTestUtils.setField(consumer, "aiPictureIndexClient", client);
        ReflectionTestUtils.setField(consumer, "pictureIndexMessageProducer", producer);
        ReflectionTestUtils.setField(consumer, "pictureIndexOutboxService", outboxService);
        return consumer;
    }

    private PictureIndexMessage buildUpsertMessage() {
        PictureIndexMessage message = new PictureIndexMessage();
        message.setEventId(100L);
        message.setEventType(PictureIndexEventTypeEnum.UPSERT.name());
        message.setPictureId(123L);
        message.setSpaceId(456L);
        message.setName("红色赛车");
        message.setIntroduction("赛道上的红色赛车");
        message.setCategory("素材");
        message.setTags(List.of("汽车"));
        message.setUrl("https://img.test/1.webp");
        message.setRetryCount(0);
        return message;
    }
}
