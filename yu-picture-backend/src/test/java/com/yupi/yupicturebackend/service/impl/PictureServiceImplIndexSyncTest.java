package com.yupi.yupicturebackend.service.impl;

import com.yupi.yupicturebackend.manager.mq.PictureIndexMessageProducer;
import com.yupi.yupicturebackend.model.entity.Picture;
import com.yupi.yupicturebackend.model.entity.PictureIndexOutbox;
import com.yupi.yupicturebackend.service.PictureIndexOutboxService;
import org.junit.jupiter.api.Test;
import org.springframework.test.util.ReflectionTestUtils;

import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

class PictureServiceImplIndexSyncTest {

    @Test
    void syncPictureIndexCreatesAndPublishesUpsertOutboxEvent() {
        PictureIndexOutboxService outboxService = mock(PictureIndexOutboxService.class);
        PictureIndexMessageProducer producer = mock(PictureIndexMessageProducer.class);
        PictureIndexOutbox event = new PictureIndexOutbox();
        event.setId(100L);
        Picture picture = new Picture();
        picture.setId(123L);
        when(outboxService.createUpsertEvent(picture)).thenReturn(event);

        PictureServiceImpl pictureService = new PictureServiceImpl();
        ReflectionTestUtils.setField(pictureService, "pictureIndexOutboxService", outboxService);
        ReflectionTestUtils.setField(pictureService, "pictureIndexMessageProducer", producer);

        pictureService.syncPictureIndex(picture);

        verify(outboxService).createUpsertEvent(picture);
        verify(producer).publishOutboxEvent(event);
    }
}
