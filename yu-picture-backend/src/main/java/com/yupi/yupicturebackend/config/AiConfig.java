package com.yupi.yupicturebackend.config;

import lombok.Data;
import org.springframework.boot.context.properties.ConfigurationProperties;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.web.client.RestTemplate;

@Configuration
@ConfigurationProperties(prefix = "ai.service")
@Data
public class AiConfig {
    private String url = System.getenv().getOrDefault("AI_SERVICE_URL", "http://localhost:8000");
    private String internalToken = System.getenv().getOrDefault("AI_INTERNAL_TOKEN", "");

    @Bean
    public RestTemplate aiRestTemplate() {
        return new RestTemplate();
    }
}
