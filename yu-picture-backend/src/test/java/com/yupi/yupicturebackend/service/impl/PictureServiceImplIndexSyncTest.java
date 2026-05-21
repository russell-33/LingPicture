package com.yupi.yupicturebackend.service.impl;

import com.yupi.yupicturebackend.manager.mq.PictureIndexMessageProducer;
import com.yupi.yupicturebackend.model.dto.picture.PictureEditRequest;
import com.yupi.yupicturebackend.model.entity.Picture;
import com.yupi.yupicturebackend.model.entity.PictureIndexOutbox;
import com.yupi.yupicturebackend.service.PictureIndexOutboxService;
import org.junit.jupiter.api.Test;
import org.springframework.test.util.ReflectionTestUtils;
import org.springframework.transaction.support.TransactionCallback;
import org.springframework.transaction.support.TransactionTemplate;

import java.util.Collections;

import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.doNothing;
import static org.mockito.Mockito.doReturn;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.spy;
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

    @Test
    void editPictureInternalCreatesUpsertOutboxEventInsideTransactionAndPublishesAfterward() {
        PictureIndexOutboxService outboxService = mock(PictureIndexOutboxService.class);
        PictureIndexMessageProducer producer = mock(PictureIndexMessageProducer.class);
        TransactionTemplate transactionTemplate = mock(TransactionTemplate.class);
        PictureIndexOutbox event = new PictureIndexOutbox();
        event.setId(100L);

        Picture oldPicture = new Picture();
        oldPicture.setId(123L);
        Picture updatedPicture = new Picture();
        updatedPicture.setId(123L);
        updatedPicture.setName("updated");
        when(outboxService.createUpsertEvent(updatedPicture)).thenReturn(event);
        when(transactionTemplate.execute(any())).thenAnswer(invocation -> {
            TransactionCallback<?> callback = invocation.getArgument(0);
            return callback.doInTransaction(null);
        });

        PictureServiceImpl pictureService = spy(new PictureServiceImpl());
        ReflectionTestUtils.setField(pictureService, "pictureIndexOutboxService", outboxService);
        ReflectionTestUtils.setField(pictureService, "pictureIndexMessageProducer", producer);
        ReflectionTestUtils.setField(pictureService, "transactionTemplate", transactionTemplate);
        doReturn(oldPicture).doReturn(updatedPicture).when(pictureService).getById(123L);
        doReturn(true).when(pictureService).updateById(any(Picture.class));

        PictureEditRequest request = new PictureEditRequest();
        request.setId(123L);
        request.setTags(Collections.singletonList("赛车"));
        pictureService.editPictureInternal(request);

        verify(transactionTemplate).execute(any());
        verify(outboxService).createUpsertEvent(updatedPicture);
        verify(producer).publishOutboxEvent(event);
    }

    @Test
    void deletePictureCreatesDeleteOutboxEventInsideTransactionAndPublishesAfterward() {
        PictureIndexOutboxService outboxService = mock(PictureIndexOutboxService.class);
        PictureIndexMessageProducer producer = mock(PictureIndexMessageProducer.class);
        TransactionTemplate transactionTemplate = mock(TransactionTemplate.class);
        PictureIndexOutbox event = new PictureIndexOutbox();
        event.setId(100L);

        Picture picture = new Picture();
        picture.setId(123L);
        picture.setPicSize(1024L);
        when(outboxService.createDeleteEvent(123L, null)).thenReturn(event);
        when(transactionTemplate.execute(any())).thenAnswer(invocation -> {
            TransactionCallback<?> callback = invocation.getArgument(0);
            return callback.doInTransaction(null);
        });

        PictureServiceImpl pictureService = spy(new PictureServiceImpl());
        ReflectionTestUtils.setField(pictureService, "pictureIndexOutboxService", outboxService);
        ReflectionTestUtils.setField(pictureService, "pictureIndexMessageProducer", producer);
        ReflectionTestUtils.setField(pictureService, "transactionTemplate", transactionTemplate);
        doReturn(picture).when(pictureService).getById(123L);
        doReturn(true).when(pictureService).removeById(123L);
        doNothing().when(pictureService).clearPictureFile(picture);

        pictureService.deletePicture(123L, null);

        verify(transactionTemplate).execute(any());
        verify(outboxService).createDeleteEvent(123L, null);
        verify(producer).publishOutboxEvent(event);
        verify(pictureService).clearPictureFile(picture);
    }
}
