# Docker Compose 優化設計 (方案 B)

## 目標

改善 docker-compose.yml 的可維護性與安全性，同時讓 Ollama URL 可透過環境變數設定。

## 變更範圍

### docker-compose.yml
- 移除棄用的 `version: "3.8"`
- 加入 named network `pet-network`（兩個 service 都加入）
- web service 加入環境變數：`OLLAMA_URL`, `FLASK_APP`, `FLASK_DEBUG=0`
- web service 加入 health check

### model_connector.py
- 將 hardcoded `url` 改為讀取 `OLLAMA_URL` 環境變數，保留原始 IP 作為預設值

### .env.example
- 加入 `OLLAMA_URL` 欄位
