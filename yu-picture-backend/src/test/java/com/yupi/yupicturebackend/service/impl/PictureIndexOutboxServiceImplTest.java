package com.yupi.yupicturebackend.service.impl;

import com.yupi.yupicturebackend.model.entity.Picture;
import com.yupi.yupicturebackend.model.entity.PictureIndexOutbox;
import com.yupi.yupicturebackend.model.enums.PictureIndexEventTypeEnum;
import com.yupi.yupicturebackend.model.enums.PictureIndexOutboxStatusEnum;
import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.doAnswer;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.spy;
import static org.mockito.Mockito.verify;

class PictureIndexOutboxServiceImplTest {

    @Test
    void createUpsertEventSerializesLatestPictureMetadata() {
        PictureIndexOutboxServiceImpl service = spy(new PictureIndexOutboxServiceImpl());
        doAnswer(invocation -> {
            PictureIndexOutbox event = invocation.getArgument(0);
            return true;
        }).when(service).save(any(PictureIndexOutbox.class));

        Picture picture = new Picture();
        picture.setId(123L);
        picture.setSpaceId(456L);
        picture.setName("红色赛车");
        picture.setIntroduction("赛道上的红色赛车");
        picture.setCategory("素材");
        picture.setTags("[\"汽车\",\"运动\"]");
        picture.setUrl("https://img.test/1.webp");

        PictureIndexOutbox event = service.createUpsertEvent(picture);

        assertNotNull(event);
        assertNotNull(event.getId());
        assertEquals(PictureIndexEventTypeEnum.UPSERT.name(), event.getEventType());
        assertEquals(PictureIndexOutboxStatusEnum.PENDING.name(), event.getStatus());
        assertEquals(123L, event.getPictureId());
        assertEquals(456L, event.getSpaceId());
        assertEquals(0, event.getRetryCount());
        assertTrue(event.getPayload().contains("\"eventId\":" + event.getId()));
        assertTrue(event.getPayload().contains("\"tags\":[\"汽车\",\"运动\"]"));
        verify(service, never()).updateById(any(PictureIndexOutbox.class));
    }

    @Test
    void createDeleteEventSerializesDeleteMessage() {
        PictureIndexOutboxServiceImpl service = spy(new PictureIndexOutboxServiceImpl());
        doAnswer(invocation -> {
            PictureIndexOutbox event = invocation.getArgument(0);
            return true;
        }).when(service).save(any(PictureIndexOutbox.class));

        PictureIndexOutbox event = service.createDeleteEvent(123L, 456L);

        assertEquals(PictureIndexEventTypeEnum.DELETE.name(), event.getEventType());
        assertEquals(PictureIndexOutboxStatusEnum.PENDING.name(), event.getStatus());
        assertNotNull(event.getId());
        assertTrue(event.getPayload().contains("\"eventId\":" + event.getId()));
        assertTrue(event.getPayload().contains("\"pictureId\":123"));
        verify(service, never()).updateById(any(PictureIndexOutbox.class));
    }
}
