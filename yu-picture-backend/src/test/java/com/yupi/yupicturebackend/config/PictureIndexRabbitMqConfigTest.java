package com.yupi.yupicturebackend.config;

import com.yupi.yupicturebackend.constant.PictureIndexMqConstant;
import org.junit.jupiter.api.Test;
import org.springframework.amqp.core.Queue;

import static org.junit.jupiter.api.Assertions.assertEquals;

class PictureIndexRabbitMqConfigTest {

    @Test
    void pictureIndexQueueKeepsDeadLetterArgumentsForExistingBrokerQueue() {
        PictureIndexRabbitMqConfig config = new PictureIndexRabbitMqConfig();

        Queue queue = config.pictureIndexQueue();

        assertEquals(PictureIndexMqConstant.EXCHANGE, queue.getArguments().get("x-dead-letter-exchange"));
        assertEquals(PictureIndexMqConstant.DLQ_ROUTING_KEY, queue.getArguments().get("x-dead-letter-routing-key"));
    }
}
