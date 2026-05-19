package com.yupi.yupicturebackend.constant;

/**
 * 图片 AI 索引 MQ 常量。
 */
public interface PictureIndexMqConstant {

    String EXCHANGE = "picture.index.exchange";

    String QUEUE = "picture.index.queue";

    String RETRY_QUEUE = "picture.index.retry.queue";

    String DLQ = "picture.index.dlq";

    String ROUTING_KEY = "picture.index";

    String RETRY_ROUTING_KEY = "picture.index.retry";

    String DLQ_ROUTING_KEY = "picture.index.dlq";

    int RETRY_DELAY_MILLIS = 30000;

    int MAX_RETRY_COUNT = 3;
}
