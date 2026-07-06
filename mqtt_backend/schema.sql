-- ===================================================
-- 设备数据管理后端 — 数据库建表脚本
-- 数据库: mqtt_device_db
-- 引擎:  InnoDB, 字符集: utf8mb4
-- ===================================================

CREATE DATABASE IF NOT EXISTS `mqtt_device_db`
  DEFAULT CHARACTER SET utf8mb4
  COLLATE utf8mb4_0900_ai_ci;
USE `mqtt_device_db`;

-- ---------------------------------------------------
-- 1. 用户基础信息表
-- ---------------------------------------------------
CREATE TABLE `user_info` (
  `user_id`       varchar(50)  NOT NULL COMMENT '用户唯一ID（登录账号）',
  `user_password` varchar(255) NOT NULL COMMENT '加密后密码(bcrypt/argon2)',
  `status`        tinyint      NOT NULL DEFAULT 1 COMMENT '1=启用 0=禁用',
  `create_time`   datetime     NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '注册时间',
  PRIMARY KEY (`user_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='用户基础信息表';

-- ---------------------------------------------------
-- 2. 设备基础信息表
-- ---------------------------------------------------
CREATE TABLE `device_info` (
  `device_id`         varchar(50)  NOT NULL COMMENT '设备唯一ID（对应EMQX设备账号）',
  `device_name`       varchar(50)  NOT NULL Comment '设备名称',
  `device_desc`       text         DEFAULT NULL COMMENT '设备描述（安装位置/型号等）',
  `config_json`       json         DEFAULT NULL COMMENT '设备配置模板定义（控制用户前端配置页表单）',
  `field_labels`      json         DEFAULT NULL COMMENT '遥测字段中文映射: {"temperature":"温度","humidity":"湿度",...}',
  `current_config`    json         DEFAULT NULL COMMENT '设备上报的当前配置值',
  `is_online`         tinyint      NOT NULL DEFAULT 0 COMMENT '0=离线 1=在线',
  `last_online_time`  datetime(3)  DEFAULT NULL COMMENT '最后上线时间',
  `last_offline_time` datetime(3)  DEFAULT NULL COMMENT '最后离线时间',
  `create_time`       datetime     NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '设备注册时间',
  PRIMARY KEY (`device_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='设备基础信息表';

-- ---------------------------------------------------
-- 3. 用户-设备绑定关系表
-- ---------------------------------------------------
CREATE TABLE `user_device_bind` (
  `user_id`   varchar(50) NOT NULL COMMENT '用户ID',
  `device_id` varchar(50) NOT NULL COMMENT '设备ID',
  `bind_time` datetime    NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '绑定时间',
  PRIMARY KEY (`user_id`, `device_id`),
  KEY `fk_bind_device` (`device_id`),
  CONSTRAINT `fk_bind_user`   FOREIGN KEY (`user_id`)   REFERENCES `user_info` (`user_id`)     ON DELETE CASCADE,
  CONSTRAINT `fk_bind_device` FOREIGN KEY (`device_id`) REFERENCES `device_info` (`device_id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='用户-设备绑定关系表';

-- ---------------------------------------------------
-- 4. 设备历史数据表
-- ---------------------------------------------------
CREATE TABLE `device_data` (
  `id`           bigint       NOT NULL AUTO_INCREMENT,
  `device_id`    varchar(50)  NOT NULL COMMENT '关联设备ID',
  `message_type` varchar(20)  NOT NULL DEFAULT 'telemetry' COMMENT '消息类型: telemetry/alert',
  `raw_json`     json         NOT NULL COMMENT '设备上传的JSON数据(自动校验)',
  `upload_time`  datetime(3)  NOT NULL DEFAULT CURRENT_TIMESTAMP(3) COMMENT '数据上传时间(毫秒精度)',
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_device_time` (`device_id`, `upload_time`),
  KEY `idx_upload_time` (`upload_time`),
  KEY `idx_device_id` (`device_id`),
  CONSTRAINT `fk_data_device` FOREIGN KEY (`device_id`) REFERENCES `device_info` (`device_id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='设备历史数据表';

-- ---------------------------------------------------
-- 5. 设备录音表
-- ---------------------------------------------------
CREATE TABLE `device_recording` (
  `id`           bigint      NOT NULL AUTO_INCREMENT,
  `device_id`    varchar(50) NOT NULL COMMENT '关联设备ID',
  `format`       varchar(10) NOT NULL DEFAULT 'amr' COMMENT '音频格式',
  `data`         mediumblob  NOT NULL COMMENT '原始音频二进制',
  `upload_time`  datetime(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3) COMMENT '上传时间',
  PRIMARY KEY (`id`),
  KEY `idx_recording_device` (`device_id`),
  CONSTRAINT `fk_recording_device` FOREIGN KEY (`device_id`) REFERENCES `device_info` (`device_id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='设备录音表';
