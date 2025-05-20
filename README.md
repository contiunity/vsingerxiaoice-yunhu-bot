# 云湖机器人“Vsinger小冰”

## 技术架构

本机器人采用了模块化架构（我们称为 Aikframe），从而能够简便的维护和更新，并能在未来用于Kook等多种不同机器人。

## 部署方法

1. 在云湖端创建并配置机器人
2. 修改`config.example.toml`，并更名为`config.toml`
3. `docker-compose up -d`
4. 在云湖端配置回调接口