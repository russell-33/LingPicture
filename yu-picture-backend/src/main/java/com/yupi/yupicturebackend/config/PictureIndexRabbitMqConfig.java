package com.yupi.yupicturebackend.config;

import com.yupi.yupicturebackend.constant.PictureIndexMqConstant;
import org.springframework.amqp.core.Binding;
import org.springframework.amqp.core.BindingBuilder;
import org.springframework.amqp.core.DirectExchange;
import org.springframework.amqp.core.Queue;
import org.springframework.amqp.core.QueueBuilder;
import org.springframework.amqp.rabbit.annotation.EnableRabbit;
import org.springframework.amqp.rabbit.config.SimpleRabbitListenerContainerFactory;
import org.springframework.amqp.rabbit.connection.ConnectionFactory;
import org.springframework.amqp.rabbit.core.RabbitTemplate;
import org.springframework.amqp.support.converter.Jackson2JsonMessageConverter;
import org.springframework.amqp.support.converter.MessageConverter;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

/**
 * 图片 AI 索引 RabbitMQ 配置。
 */
@Configuration
@EnableRabbit
public class PictureIndexRabbitMqConfig {

    @Bean
    public DirectExchange pictureIndexExchange() {
        return new DirectExchange(PictureIndexMqConstant.EXCHANGE, true, false);
    }

    @Bean
    public Queue pictureIndexQueue() {
        // RabbitMQ does not allow changing queue arguments after a queue is created.
        // Keep these DLX arguments compatible with existing local/prod queues; normal
        // business failures still use the consumer's explicit retry/DLQ flow.
        return QueueBuilder.durable(PictureIndexMqConstant.QUEUE)
                .withArgument("x-dead-letter-exchange", PictureIndexMqConstant.EXCHANGE)
                .withArgument("x-dead-letter-routing-key", PictureIndexMqConstant.DLQ_ROUTING_KEY)
                .build();
    }

    @Bean
    public Queue pictureIndexRetryQueue() {
        return QueueBuilder.durable(PictureIndexMqConstant.RETRY_QUEUE)
                .withArgument("x-message-ttl", PictureIndexMqConstant.RETRY_DELAY_MILLIS)
                .withArgument("x-dead-letter-exchange", PictureIndexMqConstant.EXCHANGE)
                .withArgument("x-dead-letter-routing-key", PictureIndexMqConstant.ROUTING_KEY)
                .build();
    }

    @Bean
    public Queue pictureIndexDlq() {
        return QueueBuilder.durable(PictureIndexMqConstant.DLQ).build();
    }

    @Bean
    public Binding pictureIndexBinding(DirectExchange pictureIndexExchange, Queue pictureIndexQueue) {
        return BindingBuilder.bind(pictureIndexQueue)
                .to(pictureIndexExchange)
                .with(PictureIndexMqConstant.ROUTING_KEY);
    }

    @Bean
    public Binding pictureIndexRetryBinding(DirectExchange pictureIndexExchange, Queue pictureIndexRetryQueue) {
        return BindingBuilder.bind(pictureIndexRetryQueue)
                .to(pictureIndexExchange)
                .with(PictureIndexMqConstant.RETRY_ROUTING_KEY);
    }

    @Bean
    public Binding pictureIndexDlqBinding(DirectExchange pictureIndexExchange, Queue pictureIndexDlq) {
        return BindingBuilder.bind(pictureIndexDlq)
                .to(pictureIndexExchange)
                .with(PictureIndexMqConstant.DLQ_ROUTING_KEY);
    }

    @Bean
    public MessageConverter rabbitMessageConverter() {
        return new Jackson2JsonMessageConverter();
    }

    @Bean
    public RabbitTemplate rabbitTemplate(ConnectionFactory connectionFactory, MessageConverter rabbitMessageConverter) {
        RabbitTemplate rabbitTemplate = new RabbitTemplate(connectionFactory);
        rabbitTemplate.setMessageConverter(rabbitMessageConverter);
        return rabbitTemplate;
    }

    @Bean
    public SimpleRabbitListenerContainerFactory rabbitListenerContainerFactory(
            ConnectionFactory connectionFactory,
            MessageConverter rabbitMessageConverter) {
        SimpleRabbitListenerContainerFactory factory = new SimpleRabbitListenerContainerFactory();
        factory.setConnectionFactory(connectionFactory);
        factory.setMessageConverter(rabbitMessageConverter);
        factory.setDefaultRequeueRejected(false);
        return factory;
    }
}
